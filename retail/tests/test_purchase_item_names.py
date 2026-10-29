"""Purchase layout upgrade checks with rolled-back synthetic user settings."""

import copy
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

import frappe

from retail.grid_view_settings import _get_user_settings, _save_user_settings, get_fixture_path
from retail.patches import show_purchase_item_names as upgrade


class TestPurchaseItemNames(unittest.TestCase):
	def test_shipped_purchase_defaults(self):
		defaults = json.loads(get_fixture_path().read_text())
		for parent in upgrade.PURCHASE_DOCTYPES:
			fields = [c["fieldname"] for c in defaults[parent][parent + " Item"]]
			self.assertEqual(fields[fields.index("item_code") + 1], "item_name")

	def test_upgrade_preserves_columns_widths_and_is_idempotent(self):
		user = "purchase-columns-test-" + uuid4().hex
		frappe.db.savepoint("purchase_columns_test")
		try:
			for parent in upgrade.PURCHASE_DOCTYPES:
				settings = {
					"GridView": {parent + " Item": [
						{"fieldname": "qty", "columns": 1},
						{"fieldname": "item_code", "columns": 3},
					]},
					"RetailScrollableGrid": {"items": [
						{"fieldname": "item_name", "columns": 4, "width_px": 287},
						{"fieldname": "item_code", "columns": 2, "width_px": 199},
						{"fieldname": "qty", "columns": 1},
					]},
					"last_view": "List",
				}
				_save_user_settings(user, parent, settings)
				cached = copy.deepcopy(settings)
				cached["other_preference"] = "keep"
				frappe.cache.hset("_user_settings", f"{parent}::{user}", json.dumps(cached))
			with patch.object(upgrade.frappe, "get_all", return_value=[user]):
				upgrade.execute()
				before = [_get_user_settings(user, p) for p in upgrade.PURCHASE_DOCTYPES]
				upgrade.execute()
				self.assertEqual(before, [_get_user_settings(user, p) for p in upgrade.PURCHASE_DOCTYPES])
			for settings in before:
				self.assertEqual(settings["last_view"], "List")
				self.assertEqual(settings["other_preference"], "keep")
				columns = settings["RetailScrollableGrid"]["items"]
				self.assertEqual([c["fieldname"] for c in columns], ["item_code", "item_name", "qty"])
				self.assertEqual(columns[1]["width_px"], 287)
				self.assertEqual(columns[0]["width_px"], 199)
				columns = next(iter(settings["GridView"].values()))
				self.assertEqual([c["fieldname"] for c in columns], ["qty", "item_code", "item_name"])
		finally:
			frappe.db.rollback(save_point="purchase_columns_test")
			for parent in upgrade.PURCHASE_DOCTYPES:
				frappe.cache.hdel("_user_settings", f"{parent}::{user}")

	def test_explicit_resets_and_unrelated_layouts_are_preserved(self):
		for columns in (None, [], [{"fieldname": "qty", "columns": 1}]):
			self.assertEqual(upgrade.add_item_name(columns), columns)


class TestPurchaseGridRepair(unittest.TestCase):
	def test_repair_persists_once_and_invalidates_cached_layouts(self):
		from retail.patches import repair_purchase_grid_defaults as repair

		user = "purchase-repair-" + uuid4().hex
		frappe.db.savepoint("purchase_repair_test")
		try:
			for parent in upgrade.PURCHASE_DOCTYPES:
				frappe.cache.hset("_user_settings", f"{parent}::{user}", json.dumps({
					"RetailScrollableGrid": {"items": []}, "other_preference": "keep"}))
			with patch.object(repair.frappe, "get_all", return_value=[user]):
				repair.execute()
				first = [_get_user_settings(user, p) for p in upgrade.PURCHASE_DOCTYPES]
				repair.execute()
				self.assertEqual(first, [_get_user_settings(user, p) for p in upgrade.PURCHASE_DOCTYPES])
			for settings in first:
				self.assertEqual(settings["other_preference"], "keep")
				self.assertIn("item_name", [c["fieldname"] for c in settings["RetailScrollableGrid"]["items"]])
		finally:
			frappe.db.rollback(save_point="purchase_repair_test")
			for parent in upgrade.PURCHASE_DOCTYPES:
				frappe.cache.hdel("_user_settings", f"{parent}::{user}")

	def test_missing_empty_and_saved_layouts(self):
		from retail.patches.repair_purchase_grid_defaults import repair_settings

		defaults = json.loads(get_fixture_path().read_text())
		for parent in upgrade.PURCHASE_DOCTYPES:
			for original in ({}, {"RetailScrollableGrid": {"items": []}}, {"GridView": None}):
				repaired = repair_settings(parent, original, defaults)
				fields = [c["fieldname"] for c in repaired["RetailScrollableGrid"]["items"]]
				self.assertIn("item_name", fields)
				if parent != "Purchase Order":
					self.assertIn("serial_no", fields)
					self.assertIn("batch_no", fields)
				self.assertEqual(repair_settings(parent, repaired, defaults), repaired)
			selection = [{"fieldname": "item_code", "width_px": 219, "columns": 3},
				{"fieldname": "qty", "width_px": 87, "columns": 1}]
			original = {"GridView": {parent + " Item": selection},
				"RetailScrollableGrid": {"items": []}, "other_preference": "keep"}
			before = copy.deepcopy(original)
			repaired = repair_settings(parent, original, defaults)
			self.assertEqual(original, before)
			self.assertEqual(repaired["other_preference"], "keep")
			columns = repaired["RetailScrollableGrid"]["items"]
			self.assertEqual(columns[0], selection[0])
			self.assertEqual(columns[-1], selection[1])
			self.assertEqual(repair_settings(parent, repaired, defaults), repaired)
