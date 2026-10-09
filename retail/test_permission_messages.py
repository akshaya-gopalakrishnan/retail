import json
import unittest
from unittest.mock import Mock, patch

from werkzeug.wrappers import Response

import frappe
from retail import permission_messages as messages


class TestPermissionMessages(unittest.TestCase):
    def setUp(self):
        self.patch(frappe.local, "session", new=frappe._dict(user="cashier@example.com"), create=True)
        self.patch(frappe.local, "flags", new=frappe._dict(), create=True)
        self.patch(frappe.local, "form_dict", new=frappe._dict(doctype="Sales Invoice", name="INV-1"), create=True)
        self.patch(frappe.local, "db", new=Mock(exists=Mock(return_value=True)), create=True)
        self.patch(messages, "_", side_effect=lambda s:s)
        self.super_admin = self.patch(messages, "is_super_admin", return_value=False)
        self.patch(messages, "is_protected_user", return_value=False)
        self.roles = self.patch(frappe, "get_roles", return_value=["Sales User"])
        self.patch(frappe, "get_meta", return_value=frappe._dict(module="Accounts"))
        self.admins = self.patch(frappe, "get_all", return_value=["company-admin@example.com"])
        self.permission = self.patch(frappe, "has_permission", autospec=True, return_value=True)
        self.request = frappe._dict(path="/api/resource/Sales%20Invoice/INV-1", method="PUT")

    def patch(self, target, name, **kwargs):
        patcher = patch.object(target, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def response(self, payload=None):
        return Response(json.dumps(payload or {"exc_type": "PermissionError", "exception": "Only Super Admin", "exc": "internal stack: Super Admin", "_server_messages": '["Only Super Admin"]'}), status=403, mimetype="application/json")

    def test_business_denial_directs_to_capable_company_administrator(self):
        response = self.response()
        messages.after_request(response, self.request)
        self.assertIn("contact your company administrator", response.get_data(as_text=True))
        self.assertNotIn("Super Admin", response.get_data(as_text=True))
        self.permission.assert_called_once_with("Sales Invoice", "write", doc="INV-1", user="company-admin@example.com", throw=False)
        self.assertEqual(response.status_code, 403)

    def test_technical_denial_always_directs_to_software_team(self):
        frappe.flags.retail_technical_permission_denied = True
        response = self.response()
        messages.after_request(response, self.request)
        self.assertIn("contact the software team", response.get_data(as_text=True))
        self.permission.assert_not_called()

    def test_no_capable_administrator_falls_back_to_software_team(self):
        self.permission.return_value = False
        response = self.response()
        messages.after_request(response, self.request)
        self.assertIn("contact the software team", response.get_data(as_text=True))

    def test_no_assigned_administrator_does_not_send_user_to_nonexistent_contact(self):
        self.admins.return_value = []
        self.assertFalse(messages.company_administrator_can_help(self.request))
        self.permission.assert_not_called()

    def test_company_administrator_is_not_directed_back_to_themselves(self):
        self.roles.return_value = [messages.CUSTOMER_ADMIN]
        self.assertFalse(messages.company_administrator_can_help(self.request))

    def test_protected_account_and_configuration_remain_software_team_tasks(self):
        for dt in ("Role Profile", "Module Profile", "User"):
            with self.subTest(doctype=dt):
                frappe.local.form_dict = frappe._dict(doctype=dt, name="internal-user@example.com")
                self.request.path = "/api/method/frappe.client.get"
                with patch.object(messages, "is_protected_user", return_value=True):
                    self.assertFalse(messages.company_administrator_can_help(self.request))

    def test_v2_preserves_native_error_schema_without_internal_role_details(self):
        response = self.response({"errors": [{"type": "PermissionError", "message": "Only Super Admin", "exception": "stack"}]})
        messages.after_request(response, self.request)
        result = response.get_json()
        self.assertEqual(result["errors"][0]["type"], "PermissionError")
        self.assertIn("company administrator", result["errors"][0]["message"])
        self.assertNotIn("exception", result["errors"][0])

    def test_other_errors_and_developer_responses_are_unchanged(self):
        for payload, privileged in (({"exc_type": "CSRFTokenError"}, False), ({"exc_type": "PermissionError", "exc": "debug trace"}, True)):
            self.super_admin.return_value = privileged
            response = self.response(payload)
            before = response.get_data()
            messages.after_request(response, self.request)
            self.assertEqual(response.get_data(), before)

    def test_native_submit_action_is_checked_as_submit(self):
        self.request.path = "/api/method/frappe.desk.form.save.savedocs"
        frappe.local.form_dict = frappe._dict(action="Submit", doc='{"doctype":"Sales Invoice","name":"INV-1"}')
        self.assertEqual(messages.request_target(self.request), ("Sales Invoice", "INV-1", "submit"))
