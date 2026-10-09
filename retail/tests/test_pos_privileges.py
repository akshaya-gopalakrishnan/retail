import unittest
from unittest.mock import patch
from uuid import uuid4

import frappe

from retail.api.pos_sync import _operator_master_rows
from retail.pos_privileges import add_operator_privileges, profile_privileges, validate_employee_assignment


class TestPOSPrivileges(unittest.TestCase):
	def setUp(self):
		frappe.db.savepoint("pos_privileges_test")
		self.profile = frappe.get_doc({
			"doctype": "POS Operator Privilege", "profile_name": "Test POS " + uuid4().hex,
			"change_qty": 1, "warranty_lookup": 1,
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback(save_point="pos_privileges_test")

	def test_default_deny_and_corrected_code(self):
		permissions = profile_privileges(None)
		self.assertEqual(len(permissions), 37)
		self.assertFalse(any(permissions.values()))
		self.assertIn("WARRANTY_LOOKUP", permissions)
		self.assertNotIn("WARRENTY_LOOKUP", permissions)

	def test_selected_permissions_and_disabled_profile(self):
		permissions = profile_privileges(self.profile.name)
		self.assertTrue(permissions["CHANGE_QTY"])
		self.assertFalse(permissions["CHANGE_PRICE"])
		self.profile.disabled = 1
		self.profile.save(ignore_permissions=True)
		self.assertFalse(any(profile_privileges(self.profile.name).values()))

	def test_disabled_operator(self):
		rows = add_operator_privileges([frappe._dict(pos_operator_privilege=self.profile.name, disabled=1)])
		self.assertFalse(any(rows[0].privileges.values()))

	def test_assignment_requires_system_manager(self):
		doc = frappe.new_doc("Employee")
		doc.pos_operator_privilege = self.profile.name
		with patch("retail.pos_privileges.frappe.get_roles", return_value=["Employee"]):
			with self.assertRaises(frappe.PermissionError):
				validate_employee_assignment(doc)
		with patch("retail.pos_privileges.frappe.get_roles", return_value=["System Manager"]):
			validate_employee_assignment(doc)

	def test_profile_changes_refresh_operator_sync(self):
		employee = frappe.db.get_value("Employee", {}, "name")
		if not employee:
			self.skipTest("Requires an existing Employee")
		frappe.db.set_value("Employee", employee, {
			"pos_operator_privilege": self.profile.name, "pos_login_enabled": 1, "status": "Active",
			"modified": "2000-01-01 00:00:00",
		}, update_modified=False)
		self.profile.change_price = 1
		self.profile.save(ignore_permissions=True)
		rows = {row.name: row for row in _operator_master_rows(modified_after="2001-01-01")}
		self.assertIn(employee, rows)
		self.assertTrue(rows[employee].privileges["CHANGE_PRICE"])
		self.assertEqual(rows[employee].privilege_profile, self.profile.name)
		frappe.db.set_value("Employee", employee, "status", "Left")
		rows = {row.name: row for row in _operator_master_rows(modified_after="2001-01-01")}
		self.assertEqual(rows[employee].disabled, 1)
		self.assertFalse(any(rows[employee].privileges.values()))

	def test_employee_tab_placement(self):
		fields = frappe.get_meta("Employee").fields
		names = [field.fieldname for field in fields]
		start = names.index("pos_settings_tab")
		end = next((i for i in range(start + 1, len(fields)) if fields[i].fieldtype == "Tab Break"), len(fields))
		for field in ("pos_login_enabled", "pos_login_user", "pos_login_id", "pos_quick_pin", "pos_operator_privilege", "pos_privileges_preview"):
			self.assertTrue(start < names.index(field) < end, field)
		self.assertLess(names.index("create_user_permission"), start)
