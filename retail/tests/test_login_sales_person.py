from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from retail.login_sales_person import on_session_creation


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
				) as get_all:
					on_session_creation(SimpleNamespace(user=user))
					self.assertEqual(response, {
						"message": "Logged In", "full_name": "Existing Name",
						"sales_person_id": expected[0], "sales_person_name": expected[1],
					})
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
