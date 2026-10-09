"""Database-backed column preference checks; synthetic identities, rolled back."""

import json
import unittest
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.model.utils.user_settings import get_user_settings

from retail import column_preferences as columns
from retail import grid_view_settings as defaults


class TestColumnPreferences(unittest.TestCase):
	def setUp(self):
		self.original_user = frappe.session.user
		self.users = ["column-test-" + uuid4().hex, "column-test-" + uuid4().hex]
		frappe.session.user = self.users[0]
		frappe.db.savepoint("column_preferences_test")
		self.permission = patch.object(frappe, "has_permission", return_value=True)
		self.permission.start()
		self.selection = [{"fieldname": "item_code", "columns": 2}, {"fieldname": "qty", "columns": 1}]

	def tearDown(self):
		self.permission.stop()
		frappe.db.rollback(save_point="column_preferences_test")
		for user in self.users:
			for doctype in ("Purchase Invoice", "Sales Invoice"):
				frappe.cache.hdel("_user_settings", f"{doctype}::{user}")
		frappe.session.user = self.original_user

	def read_db(self, doctype="Purchase Invoice", user=None):
		return defaults._get_user_settings(user or frappe.session.user, doctype)

	def save(self, doctype="Purchase Invoice", key="GridView", value=None):
		return columns.save(doctype, key, json.dumps(value))

	def test_standard_and_scrollable_columns_are_in_database_before_sync(self):
		for key, table in (("GridView", "Purchase Invoice Item"), ("RetailScrollableGrid", "items")):
			self.save(key=key, value={table: self.selection})
			self.assertEqual(self.read_db()[key][table], self.selection)
			# Losing the entire preference cache entry must reload the same DB layout.
			frappe.cache.hdel("_user_settings", f"Purchase Invoice::{frappe.session.user}")
			self.assertEqual(json.loads(get_user_settings("Purchase Invoice"))[key][table], self.selection)

	def test_users_and_doctypes_remain_separate(self):
		self.save(value={"Purchase Invoice Item": self.selection})
		self.save(doctype="Sales Invoice", value={"Sales Invoice Item": self.selection[:1]})
		frappe.session.user = self.users[1]
		self.save(value={"Purchase Invoice Item": self.selection[1:]})
		self.assertEqual(self.read_db()["GridView"]["Purchase Invoice Item"], self.selection[1:])
		self.assertEqual(self.read_db(user=self.users[0])["GridView"]["Purchase Invoice Item"], self.selection)
		self.assertEqual(self.read_db("Sales Invoice", self.users[0])["GridView"]["Sales Invoice Item"], self.selection[:1])

	def test_other_settings_and_other_tables_are_preserved(self):
		existing = {"List": {"filters": [["docstatus", "=", 0]]},
			"GridView": {"Purchase Taxes and Charges": [{"fieldname": "rate", "columns": 1}]}}
		frappe.cache.hset("_user_settings", f"Purchase Invoice::{frappe.session.user}", json.dumps(existing))
		self.save(value={"Purchase Invoice Item": self.selection})
		saved = self.read_db()
		self.assertEqual(saved["List"], existing["List"])
		self.assertEqual(saved["GridView"]["Purchase Taxes and Charges"], existing["GridView"]["Purchase Taxes and Charges"])

	def test_explicit_resets_survive_default_installation(self):
		fixture = {"Purchase Invoice": {"Purchase Invoice Item": self.selection}}
		self.save(value=None)
		defaults.apply_default_grid_view_settings_for_user(frappe.session.user, defaults=fixture)
		self.assertIsNone(self.read_db()["GridView"])
		self.save(value={"Purchase Invoice Item": []})
		defaults.apply_default_grid_view_settings_for_user(frappe.session.user, defaults=fixture)
		self.assertEqual(self.read_db()["GridView"]["Purchase Invoice Item"], [])

	def test_migration_defaults_keep_personal_layouts(self):
		self.save(value={"Purchase Invoice Item": self.selection})
		self.save(key="RetailScrollableGrid", value={"items": self.selection[::-1]})
		defaults.apply_default_grid_view_settings_for_user(frappe.session.user, defaults={
			"Purchase Invoice": {"Purchase Invoice Item": self.selection[:1]}})
		self.assertEqual(self.read_db()["GridView"]["Purchase Invoice Item"], self.selection)
		self.assertEqual(self.read_db()["RetailScrollableGrid"]["items"], self.selection[::-1])

	def test_endpoint_rejects_unrelated_preferences_and_forms(self):
		for doctype, key, value in (
			("Purchase Invoice", "List", {"filters": []}),
			("DocType", "GridView", {}),
			("Purchase Invoice", "GridView", {"Sales Invoice Item": self.selection}),
			("Purchase Invoice", "RetailScrollableGrid", {"missing_table": self.selection}),
			("Purchase Invoice", "GridView", {"Purchase Invoice Item": [{"fieldname": "missing"}]}),
		):
			with self.assertRaises(frappe.ValidationError):
				self.save(doctype, key, value)
		self.assertEqual(self.read_db(), {})

	def test_permission_and_guest_checks(self):
		with patch.object(frappe, "has_permission", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				self.save(value={"Purchase Invoice Item": self.selection})
		frappe.session.user = "Guest"
		with self.assertRaises(frappe.PermissionError):
			self.save(value={"Purchase Invoice Item": self.selection})

	def test_failed_database_write_does_not_publish_new_columns(self):
		before = {"GridView": {"Purchase Invoice Item": self.selection[:1]}}
		cache_key = f"Purchase Invoice::{frappe.session.user}"
		frappe.cache.hset("_user_settings", cache_key, json.dumps(before))
		with patch.object(frappe.db, "multisql", side_effect=RuntimeError("write failed")):
			with self.assertRaisesRegex(RuntimeError, "write failed"):
				self.save(value={"Purchase Invoice Item": self.selection})
		self.assertEqual(json.loads(frappe.cache.hget("_user_settings", cache_key)), before)
		self.assertEqual(self.read_db(), {})
