import unittest
from unittest.mock import Mock, patch

import frappe
from retail import van_assignment as access
from retail import van_permissions


class TestVanAssignment(unittest.TestCase):
	def test_erp_roles_do_not_bypass_assignment(self):
		with patch.object(frappe, "get_roles", return_value=["Van Sales User", "Sales Manager", "Accounts User"]):
			self.assertTrue(access.is_operator("operator@example.com"))

	def test_managers_are_not_operator_scoped(self):
		for role in ("Van Sales Manager", "System Manager"):
			with patch.object(frappe, "get_roles", return_value=["Van Sales User", role]):
				self.assertFalse(access.is_operator("manager@example.com"))

	def test_session_read_denies_other_salesperson(self):
		with patch.object(access, "is_operator", return_value=True):
			self.assertIs(access.has_session_permission(frappe._dict(custom_salesperson="other@example.com"), user="operator@example.com"), False)
			self.assertIsNone(access.has_session_permission(frappe._dict(custom_salesperson="operator@example.com"), user="operator@example.com"))

	def test_unassigned_session_is_not_visible(self):
		with patch.object(access, "is_operator", return_value=True):
			self.assertIs(access.has_session_permission(frappe._dict(), user="operator@example.com"), False)

	def test_transaction_requires_session(self):
		with patch.object(access, "is_operator", return_value=True):
			self.assertFalse(access.check_transaction(frappe._dict(), "operator@example.com"))

	def test_fleet_uses_session_assignment(self):
		with patch.object(access, "is_operator", return_value=True), patch.object(access, "assigned_sessions", return_value=[frappe._dict(van="VAN-A")]):
			self.assertIsNone(access.has_fleet_permission(frappe._dict(name="VAN-A"), user="operator@example.com"))
			self.assertIs(access.has_fleet_permission(frappe._dict(name="VAN-B"), user="operator@example.com"), False)

	def test_operator_cannot_create_self_assignment(self):
		doc = Mock()
		doc.get_doc_before_save.return_value = None
		doc.is_new.return_value = True
		with patch.object(access, "is_operator", return_value=True), patch.object(access, "_", side_effect=lambda text: text), patch.object(frappe, "throw", side_effect=frappe.PermissionError):
			with self.assertRaises(frappe.PermissionError):
				access.validate_session(doc)

	def test_historical_van_cannot_be_reassigned(self):
		doc = Mock()
		doc.get_doc_before_save.return_value = frappe._dict(docstatus=1, status="Closed", van="VAN-A")
		doc.get.side_effect = lambda field: "VAN-B" if field == "van" else None
		with patch.object(access, "_", side_effect=lambda text: text), patch.object(frappe, "throw", side_effect=frappe.ValidationError):
			with self.assertRaises(frappe.ValidationError):
				access.validate_session(doc)

	def test_draft_session_can_be_submitted_after_assignment_values_change(self):
		doc = Mock()
		doc.status = "Open"
		doc.custom_salesperson = "driver@example.com"
		doc.get_doc_before_save.return_value = frappe._dict(
			docstatus=0,
			status="Open",
			van="VAN-A",
			van_warehouse="WH-A",
			driver="DRIVER-A",
			session_date="2026-09-09",
			custom_salesperson="driver@example.com",
		)
		doc.get.side_effect = lambda field: {
			"van": "VAN-B",
			"van_warehouse": "WH-B",
			"driver": "DRIVER-B",
			"session_date": "2026-09-10",
			"custom_salesperson": "driver@example.com",
		}.get(field)

		database = Mock()
		database.get_value.return_value = 1
		database.exists.return_value = None
		with (
			patch.object(access, "is_operator", return_value=False),
			patch.object(frappe, "db", database),
			patch.object(frappe, "get_roles", return_value=["Van Sales User"]),
		):
			access.validate_session(doc)

	def test_direct_transaction_access_uses_salesperson(self):
		database = Mock()
		database.get_value.return_value = "operator-a@example.com"
		with patch.object(access, "is_operator", return_value=True), patch.object(frappe, "db", database):
			doc = frappe._dict(custom_van_session="SESSION-A")
			self.assertTrue(access.check_transaction(doc, "operator-a@example.com"))
			self.assertFalse(access.check_transaction(doc, "operator-b@example.com"))


class TestVanRolePermissions(unittest.TestCase):
	def setUp(self):
		self.db = Mock()
		self.db.has_column.return_value = True
		self.db.escape.side_effect = lambda value: f"'{value}'"

	def permission_condition(self, doctype, roles, user="user@example.com"):
		with (
			patch.object(frappe, "db", self.db),
			patch.object(frappe, "get_roles", return_value=roles),
		):
			return van_permissions.get_van_partition_permission_query_conditions(doctype, user=user)

	def document_permission(self, doc, doctype, roles, user="user@example.com", assigned=True):
		with (
			patch.object(frappe, "get_roles", return_value=roles),
			patch.object(access, "check_transaction", return_value=assigned),
		):
			return van_permissions.has_van_partition_permission(doc, doctype, user=user)

	def test_van_only_user_is_limited_to_assigned_van_transactions(self):
		condition = self.permission_condition("Sales Invoice", ["Van Sales User"])

		self.assertIn("`tabSales Invoice`.`custom_is_van_sale` = 1", condition)
		self.assertIn("custom_salesperson = 'user@example.com'", condition)
		self.assertNotIn("ifnull(`tabSales Invoice`.`custom_is_van_sale`, 0) = 0", condition)

	def test_normal_sales_user_is_limited_to_non_van_transactions(self):
		condition = self.permission_condition("Sales Invoice", ["Sales User"])

		self.assertEqual(
			condition,
			"ifnull(`tabSales Invoice`.`custom_is_van_sale`, 0) = 0",
		)

	def test_mixed_van_and_sales_user_can_read_normal_and_assigned_van_transactions(self):
		condition = self.permission_condition("Sales Invoice", ["Van Sales User", "Sales User"])

		self.assertIn("ifnull(`tabSales Invoice`.`custom_is_van_sale`, 0) = 0", condition)
		self.assertIn("`tabSales Invoice`.`custom_is_van_sale` = 1", condition)
		self.assertIn("custom_salesperson = 'user@example.com'", condition)
		self.assertIn(" or ", condition)

	def test_van_customer_partition_uses_role_only_because_customers_have_no_session(self):
		condition = self.permission_condition("Customer", ["Van Sales User"])

		self.assertEqual(condition, "`tabCustomer`.`custom_is_van_customer` = 1")

	def test_system_users_are_not_partitioned(self):
		with patch.object(frappe, "get_roles", return_value=["System Manager"]):
			self.assertEqual(
				van_permissions.get_van_partition_permission_query_conditions("Sales Invoice", user="manager@example.com"),
				"",
			)

		with patch.object(frappe, "get_roles", return_value=[]):
			self.assertEqual(
				van_permissions.get_van_partition_permission_query_conditions("Sales Invoice", user="Administrator"),
				"",
			)

	def test_document_permission_denies_van_doc_without_van_role(self):
		doc = frappe._dict(custom_is_van_sale=1, custom_van_session="SESSION-A")

		self.assertFalse(self.document_permission(doc, "Sales Invoice", ["Sales User"]))

	def test_document_permission_denies_unassigned_van_doc_for_van_user(self):
		doc = frappe._dict(custom_is_van_sale=1, custom_van_session="SESSION-B")

		self.assertFalse(self.document_permission(doc, "Sales Invoice", ["Van Sales User"], assigned=False))

	def test_document_permission_denies_normal_doc_for_van_only_user(self):
		doc = frappe._dict(custom_is_van_sale=0)

		self.assertFalse(self.document_permission(doc, "Sales Invoice", ["Van Sales User"]))

	def test_document_permission_allows_mixed_role_user_to_read_normal_doc(self):
		doc = frappe._dict(custom_is_van_sale=0)

		self.assertIsNone(self.document_permission(doc, "Sales Invoice", ["Van Sales User", "Sales User"]))


def verify_live_queries():
	"""Exercise assignment SQL on the site without creating users or transactions."""
	from retail.van_permissions import get_van_partition_permission_query_conditions
	from retail.retail_app.report.van_sales_report_utils import common_filters_sql, filter_values, normalize_filters

	with patch.object(access, "is_operator", return_value=True):
		frappe.db.sql("select name from `tabVan Session` where " + access.session_condition())
		frappe.db.sql("select name from `tabVan Fleet` where " + access.fleet_condition())
		for doctype in ("Sales Invoice", "Stock Entry", "Payment Entry", "Material Request"):
			condition = access.transaction_condition(doctype)
			frappe.db.sql(f"select name from `tab{doctype}` where {condition} limit 1")
		filters = filter_values(normalize_filters())
		frappe.db.sql("select si.name from `tabSales Invoice` si where 1=1 " + common_filters_sql("si") + " limit 1", filters)
	with patch.object(frappe, "get_roles", return_value=["Van Sales User", "Sales User"]):
		condition = get_van_partition_permission_query_conditions("Sales Invoice", user="assignment-test@example.invalid")
		assert "custom_salesperson" in condition and " or " in condition
		frappe.db.sql("select name from `tabSales Invoice` where " + condition + " limit 1")
	return "Assignment query checks passed; no records changed."
