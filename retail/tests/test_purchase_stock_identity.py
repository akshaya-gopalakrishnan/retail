"""Purchase grid defaults and native draft bundle creation; all writes roll back."""

import json
import unittest
from unittest.mock import patch
from uuid import uuid4

import frappe

from retail.grid_view_settings import _get_user_settings, _save_user_settings, get_fixture_path
from retail.patches import show_purchase_stock_identity as upgrade


class TestPurchaseStockIdentity(unittest.TestCase):
	def setUp(self):
		self.user = frappe.session.user
		frappe.set_user("Administrator")
		self.token = "purchase-identity-" + uuid4().hex
		frappe.db.savepoint("purchase_identity_test")

	def tearDown(self):
		frappe.db.rollback(save_point="purchase_identity_test")
		for parent in upgrade.DOCTYPES:
			frappe.cache.hdel("_user_settings", f"{parent}::{self.token}")
		frappe.set_user(self.user)

	def test_defaults_and_upgrade_preserve_preferences(self):
		defaults = json.loads(get_fixture_path().read_text())
		for parent in upgrade.DOCTYPES:
			fields = [c["fieldname"] for c in defaults[parent][parent + " Item"]]
			self.assertEqual(fields[:4], ["item_code", "item_name", "serial_no", "batch_no"])
			selection = [{"fieldname": "item_code", "columns": 2, "width_px": 213}, {"fieldname": "qty", "columns": 1}]
			_save_user_settings(self.token, parent, {
				"GridView": {parent + " Item": selection},
				"RetailScrollableGrid": {"items": selection}, "last_view": "List",
			})
		with patch.object(upgrade.frappe, "get_all", return_value=[self.token]):
			upgrade.execute()
			first = [_get_user_settings(self.token, p) for p in upgrade.DOCTYPES]
			upgrade.execute()
			self.assertEqual(first, [_get_user_settings(self.token, p) for p in upgrade.DOCTYPES])
		for settings in first:
			self.assertEqual(settings["last_view"], "List")
			for columns in (settings["RetailScrollableGrid"]["items"], next(iter(settings["GridView"].values()))):
				self.assertEqual([c["fieldname"] for c in columns], ["item_code", "serial_no", "batch_no", "qty"])
				self.assertEqual(columns[0]["width_px"], 213)
		for selection in (None, [], [{"fieldname": "qty"}]):
			self.assertEqual(upgrade.add_columns(selection), selection)

	def insert(self, doctype, suffix, **values):
		doc = frappe.get_doc(dict(doctype=doctype, name=self.token + suffix, **values))
		doc.db_insert()
		return doc

	def test_native_manual_fields_create_draft_bundles(self):
		warehouse = frappe.db.get_value("Warehouse", {"is_group": 0, "disabled": 0}, ["name", "company"], as_dict=True)
		self.assertTrue(warehouse, "Requires an existing warehouse")
		for index, parent in enumerate(upgrade.DOCTYPES):
			item = self.insert("Item", f"-item-{index}", item_name="Purchase identity test", stock_uom="Nos",
				is_stock_item=1, has_serial_no=1, has_batch_no=1, valuation_method="FIFO")
			batch = self.insert("Batch", f"-batch-{index}", item=item.name, batch_id=self.token + str(index))
			doc = self.insert(parent, f"-doc-{index}", company=warehouse.company, posting_date="2026-10-28",
				posting_time="12:00:00", update_stock=1, docstatus=0)
			serials = [self.token + f"-serial-{index}-{n}" for n in range(2)]
			row = doc.append("items", dict(item_code=item.name, item_name=item.item_name, qty=2, stock_qty=2,
				conversion_factor=1, warehouse=warehouse.name, serial_no="\n".join(serials), batch_no=batch.name,
				use_serial_batch_fields=0, stock_uom="Nos", uom="Nos", rate=10))
			row.db_insert()
			doc.make_bundle_using_old_serial_batch_fields()
			self.assertEqual(row.use_serial_batch_fields, 1)
			self.assertTrue(row.serial_and_batch_bundle)
			bundle = frappe.get_doc("Serial and Batch Bundle", row.serial_and_batch_bundle)
			self.assertEqual(bundle.docstatus, 0)
			self.assertEqual({r.serial_no for r in bundle.entries}, set(serials))
			self.assertEqual({r.batch_no for r in bundle.entries}, {batch.name})
			self.assertFalse(frappe.db.exists("Stock Ledger Entry", {"voucher_no": doc.name}))
