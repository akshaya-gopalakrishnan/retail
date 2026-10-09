import unittest
from unittest.mock import Mock, patch

import frappe
from retail import module_access as access
from retail import workspace_permissions as sidebar


class TestModuleAccess(unittest.TestCase):
	def setUp(self):
		frappe.local.session = frappe._dict(user="operator@example.test")
		self.patch(frappe.local, "flags", new=frappe._dict(), create=True)
		frappe.local.form_dict = frappe._dict()
		frappe.local.request = frappe._dict(path="/api/method/frappe.client.get_list")
		self.patch(access, "_", side_effect=lambda message: message)
		self.roles = self.patch(frappe, "get_roles", return_value=["System Manager"])
		self.user = Mock()
		self.user.get_blocked_modules.return_value = []
		self.patch(frappe, "get_cached_doc", return_value=self.user)
		self.patch(frappe, "throw", side_effect=frappe.PermissionError)

	def patch(self, target, name, **kwargs):
		patcher = patch.object(target, name, **kwargs)
		self.addCleanup(patcher.stop)
		return patcher.start()

	def test_role_and_module_matrix_including_system_manager(self):
		for module, roles in access.MODULE_ROLES.items():
			for role in roles:
				for system_manager in (False, True):
					for assigned in (False, True):
						for blocked in (False, True):
							with self.subTest(module=module, role=role, system_manager=system_manager, assigned=assigned, blocked=blocked):
								self.roles.return_value = ([role] if assigned else []) + (["System Manager"] if system_manager else [])
								self.user.get_blocked_modules.return_value = [module] if blocked else []
								self.assertEqual(access.allowed(module), assigned and not blocked)
								self.assertEqual(sidebar._workspace_sidebar_is_allowed({"title": module}, set(), None), assigned and not blocked)

	def test_administrator_retains_framework_superuser_access(self):
		self.assertTrue(access.allowed("POS", "Administrator"))
		self.assertTrue(access.allowed("Van Sales", "Administrator"))

	def test_protected_documents_and_normal_sales(self):
		for doc in [frappe._dict(doctype="POS Invoice"), frappe._dict(doctype="Van Session"), frappe._dict(doctype="Sales Invoice", custom_is_van_sale=1), frappe._dict(doctype="Payment Entry", external_pos_reference="POS-1")]:
			self.assertFalse(access.has_permission(doc))
		self.assertIsNone(access.has_permission(frappe._dict(doctype="Sales Invoice")))
		self.roles.return_value = ["POS User", "Van Sales User"]
		self.assertIsNone(access.has_permission(frappe._dict(doctype="POS Invoice")))

	def test_lists_hide_protected_transactions(self):
		self.patch(frappe.local, "db", new=Mock(has_column=Mock(return_value=True)), create=True)
		self.assertEqual(access.query_conditions(doctype="POS Invoice"), "1=0")
		self.assertEqual(access.query_conditions(doctype="Van Session"), "1=0")
		condition = access.query_conditions(doctype="Sales Invoice")
		self.assertIn("custom_is_van_sale", condition)
		self.assertIn("is_pos", condition)
		self.assertEqual(access.query_conditions(doctype="Item"), "")

	def test_removing_flags_cannot_bypass_write_gate(self):
		doc = Mock(doctype="Sales Invoice")
		doc.get.return_value = 0
		doc.get_doc_before_save.return_value = frappe._dict(doctype="Sales Invoice", custom_is_van_sale=1)
		with self.assertRaises(frappe.PermissionError):
			access.validate_document(doc)

	def test_direct_http_targets_are_denied(self):
		requests = [
			("/api/method/retail.api.pos_sync.pull_items", {}),
			("/api/resource/POS%20Invoice", {}),
			("/api/v1/method/erpnext.selling.page.point_of_sale.point_of_sale.get_items", {}),
			("/api/v2/document/Van%20Session", {}),
			("/api/method/frappe.desk.desk_page.getpage", {"name": "van-stock-view"}),
			("/api/method/frappe.desk.desk_page.getpage", {"name": "point-of-sale"}),
			("/api/method/frappe.desk.desktop.get_desktop_page", {"page": '{"name":"Van Sales"}'}),
			("/api/method/frappe.desk.query_report.run", {"report_name": "Cashier Wise Sales"}),
			("/api/method/retail.retail_app.retail_dashboard.get_pos_sales_by_counter", {}),
			("/api/method/frappe.client.get_list", {"doctype": "Van Session"}),
		]
		for path, data in requests:
			with self.subTest(path=path, data=data):
				frappe.local.request.path = path
				frappe.local.form_dict = frappe._dict(data)
				with self.assertRaises(frappe.PermissionError):
					access.guard_request()

	def test_unrelated_requests_remain_accessible(self):
		frappe.local.form_dict = frappe._dict(doctype="Item")
		access.guard_request()

	def test_driver_uses_standard_permissions_even_when_van_sales_is_hidden(self):
		for roles in (["Fleet Manager"], ["Van Sales User"]):
			for blocked in ([], ["Van Sales"]):
				with self.subTest(roles=roles, blocked=blocked):
					self.roles.return_value = roles
					self.user.get_blocked_modules.return_value = blocked
					self.assertIsNone(access.has_permission(frappe._dict(doctype="Driver")))
					self.assertEqual(access.query_conditions(doctype="Driver"), "")
					for path in ("/api/resource/Driver", "/api/v2/document/Driver", "/api/method/frappe.client.get_list"):
						frappe.local.request.path = path
						frappe.local.form_dict = frappe._dict(doctype="Driver")
						access.guard_request()
					self.assertEqual(
						sidebar._workspace_sidebar_is_allowed({"title": "Van Sales Driver Link"}, set(blocked), None),
						"Van Sales User" in roles and not blocked,
					)

	def test_van_setup_does_not_manage_driver_permissions(self):
		from retail import van_sales_setup as setup
		self.patch(frappe.local, "db", new=Mock(), create=True)
		custom_perms = self.patch(setup, "setup_custom_perms")
		ensure = self.patch(setup, "ensure_custom_docperm")
		self.patch(frappe, "clear_cache")
		setup.ensure_van_sales_standard_permissions()
		self.assertNotIn("Driver", [call.args[0] for call in custom_perms.call_args_list])
		self.assertNotIn("Driver", [call.args[0] for call in ensure.call_args_list])
		self.assertIn("Sales Invoice", [call.args[0] for call in ensure.call_args_list])

	def test_chart_gate_runs_before_cached_result(self):
		cached = Mock(return_value={"cached": True})
		wrapped = access.requires("POS")(cached)
		with self.assertRaises(frappe.PermissionError):
			wrapped()
		cached.assert_not_called()
		self.roles.return_value = ["POS User"]
		self.assertEqual(wrapped(), {"cached": True})
