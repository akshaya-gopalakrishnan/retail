import json
import unittest
from unittest.mock import Mock, patch

import frappe

from retail.manufacturing_access import prepare_user


class TestManufacturingAccess(unittest.TestCase):
    def user(self, *, allowed=True, blocked=False, previous=None):
        data = frappe._dict(
            user_type="System User", roles=[], block_modules=[],
            retail_sidebar_permissions=json.dumps({"version": 1, "allowed":
                ["workspace:manufacturing", "workspace:bom"] if allowed else []}),
        )
        doc = Mock()
        doc.get.side_effect = data.get
        doc.get_doc_before_save.return_value = previous
        doc.get_blocked_modules.return_value = ["Manufacturing"] if blocked else []
        return doc, data

    @patch("retail.delegated_access.manages", return_value=False)
    @patch("retail.access_control.is_super_admin", return_value=True)
    def test_removing_super_admin_keeps_functional_access(self, *_):
        old = frappe._dict(roles=[frappe._dict(role="Super Admin")], block_modules=[])
        doc, data = self.user(previous=old)
        old.retail_sidebar_permissions = data.retail_sidebar_permissions
        prepare_user(doc)
        doc.append_roles.assert_called_once_with("Manufacturing User")

    @patch("retail.delegated_access.manages", return_value=False)
    @patch("retail.access_control.is_super_admin", return_value=True)
    def test_both_explicit_controls_are_required(self, *_):
        for allowed, blocked in ((False, False), (True, True)):
            doc, _ = self.user(allowed=allowed, blocked=blocked)
            prepare_user(doc)
            doc.append_roles.assert_not_called()
        for value in (None, "broken", "[]", '{"version":2,"allowed":[]}',
                      '{"version":1,"allowed":["workspace:manufacturing"]}'):
            doc, data = self.user()
            data.retail_sidebar_permissions = value
            prepare_user(doc)
            doc.append_roles.assert_not_called()

    @patch("retail.delegated_access.manages", return_value=False)
    @patch("retail.access_control.is_super_admin", return_value=False)
    def test_ordinary_user_cannot_gain_role_by_saving_profile(self, *_):
        doc, _ = self.user()
        prepare_user(doc)
        doc.append_roles.assert_not_called()

    @patch("retail.delegated_access.manages", return_value=True)
    @patch("retail.access_control.is_super_admin", return_value=False)
    def test_managed_user_assignment_uses_native_role(self, *_):
        doc, _ = self.user()
        prepare_user(doc)
        doc.append_roles.assert_called_once_with("Manufacturing User")

    @patch("retail.delegated_access.manages", return_value=False)
    @patch("retail.access_control.is_super_admin", return_value=True)
    def test_unchanged_access_does_not_add_roles(self, *_):
        doc, data = self.user()
        doc.get_doc_before_save.return_value = data.copy()
        prepare_user(doc)
        doc.append_roles.assert_not_called()
