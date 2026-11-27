from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from retail.login_sales_person import on_session_creation, get_login_access


class TestLoginSalesPerson(TestCase):
	def test_session_identity(self):
		person = frappe._dict(name="SP-1 - Ahmed", custom_document_code="SP-1", sales_person_name="SP-1 - Ahmed", custom_display_name="Ahmed")
		cases = (
			("sales@example.com", [["EMP-1"], [person]], ("SP-1", "Ahmed")),
			("sales@example.com", [[]], (None, None)),
			("sales@example.com", [["EMP-1", "EMP-2"]], (None, None)),
			("sales@example.com", [["EMP-1"], []], (None, None)),
			("sales@example.com", [["EMP-1"], [person, person]], (None, None)),
			("Guest", [], (None, None)),
		)
		for user, results, expected in cases:
			with self.subTest(user=user, results=results):
				response = {"message": "Logged In", "full_name": "Existing Name"}
				with patch.object(frappe.local, "response", response, create=True), patch.object(
					frappe, "get_all", side_effect=results,
				) as get_all, patch("retail.login_sales_person.get_login_access", return_value={
					"roles": [], "permissions": {"sales": False, "van_sales": False},
				}):
					on_session_creation(SimpleNamespace(user=user))
					expected_response = {
						"message": "Logged In", "full_name": "Existing Name",
						"sales_person_id": expected[0], "sales_person_name": expected[1],
					}
					if user != "Guest":
						expected_response.update(roles=[], permissions={"sales": False, "van_sales": False})
					self.assertEqual(response, expected_response)
					if user == "Guest":
						get_all.assert_not_called()
					else:
						self.assertEqual(get_all.call_args_list[0].kwargs["filters"], {
							"user_id": user, "status": "Active",
						})
						if len(results) == 2:
							self.assertEqual(get_all.call_args_list[1].kwargs["filters"], {
							"employee": "EMP-1", "enabled": 1, "is_group": 0,
							})


class TestLoginAreaAccess(TestCase):
	def test_flags_follow_roles_saved_area_selection_and_module_blocks(self):
		groups = [dict(workspace=title, id=identifier, children=[]) for title, identifier in
			(("Sales", "workspace:sales"), ("Van Sales", "workspace:van_sales"))]
		cases = (
			(["Van Sales User"], None, [], (False, True)),
			(["Sales User"], None, [], (True, False)),
			(["Sales User", "Van Sales User"], None, [], (True, True)),
			(["Sales User", "Van Sales User"], {"workspace:sales"}, [], (True, False)),
			(["Sales User", "Van Sales User"], set(), [], (False, False)),
			(["Sales User", "Van Sales User"], None, ["Selling", "Van Sales"], (False, False)),
			(["Sales User", "Van Sales User"], {"workspace:sales", "workspace:van_sales"},
				["Selling", "Van Sales"], (True, True)),
			([], None, [], (False, False)),
		)
		for roles, selected, blocked, expected in cases:
			with self.subTest(roles=roles, selected=selected, blocked=blocked), \
				patch.object(frappe.local, "session", frappe._dict(user="sample@example.com"), create=True), \
				patch.object(frappe, "get_roles", return_value=roles), \
				patch.object(frappe, "get_cached_doc", return_value=SimpleNamespace(get_blocked_modules=lambda: blocked)), \
				patch("retail.sidebar_permissions.selection", return_value=selected), \
				patch("retail.sidebar_registry.registry", return_value=groups):
				result = get_login_access()
				self.assertEqual(result["roles"], sorted(set(roles)))
				self.assertEqual(result["permissions"], dict(sales=expected[0], van_sales=expected[1]))

	def test_guest_never_gets_previous_users_roles_or_enabled_flags(self):
		with patch.object(frappe.local, "session", frappe._dict(user="Guest"), create=True), \
			patch.object(frappe, "get_roles") as roles:
			self.assertEqual(get_login_access(), {"roles": [], "permissions": {"sales": False, "van_sales": False}})
		roles.assert_not_called()


class TestGuestLoginMetadata(TestCase):
	def test_initial_guest_session_leaves_token_rpc_response_unchanged(self):
		response={"message": "pong"}
		with patch.object(frappe.local, "response", response, create=True), \
			patch("retail.login_sales_person.get_login_access") as access:
			on_session_creation(SimpleNamespace(user="Guest"))
			access.assert_not_called()
		self.assertNotIn("roles", response)
		self.assertNotIn("permissions", response)

	def test_logout_does_not_keep_previous_authenticated_access_flags(self):
		response={"roles": ["Sales User"], "permissions": {"sales": True, "van_sales": True}}
		with patch.object(frappe.local, "response", response, create=True), \
			patch.object(frappe.local, "session", frappe._dict(user="Guest"), create=True):
			on_session_creation(SimpleNamespace(user="Guest"))
		self.assertEqual(response["roles"], [])
		self.assertEqual(response["permissions"], {"sales": False, "van_sales": False})
