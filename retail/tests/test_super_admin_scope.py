"""Super Admin changes permission-editor authority, not business authority."""
import unittest
from unittest.mock import Mock, patch

import frappe
from retail import access_control, module_access, sidebar_permissions


class TestSuperAdminScope(unittest.TestCase):
    def test_software_role_does_not_grant_business_document_permissions(self):
        with patch.object(access_control, 'is_super_admin', return_value=True):
            for doctype in ('Sales Invoice', 'Purchase Invoice', 'POS Invoice', 'Stock Entry', 'Payment Entry'):
                for action in ('read', 'write', 'create', 'submit', 'cancel'):
                    with self.subTest(doctype=doctype, action=action):
                        self.assertIsNone(access_control.has_permission(frappe._dict(doctype=doctype), action))
            self.assertTrue(access_control.has_permission(frappe._dict(doctype='Role'), 'write'))
            self.assertTrue(access_control.has_permission(frappe._dict(doctype='User'), 'write'))

    def test_saving_software_role_does_not_append_system_manager(self):
        doc = Mock()
        doc.get.side_effect = lambda field: [frappe._dict(role='Super Admin')] if field == 'roles' else None
        with patch.object(access_control, 'is_super_admin', return_value=True), patch('retail.manufacturing_access.prepare_user'):
            access_control.prepare_super_user(doc)
        doc.append_roles.assert_not_called()

    def test_software_role_alone_does_not_grant_pos_or_van_access(self):
        with patch.object(frappe, 'get_roles', return_value=['Super Admin']), \
                patch.object(sidebar_permissions, 'selection', return_value=None):
            for module in module_access.MODULE_ROLES:
                self.assertFalse(module_access.allowed(module, 'software@example.test'))

    def test_adding_software_role_preserves_explicit_business_access(self):
        with patch.object(sidebar_permissions, 'selection', return_value={'workspace:pos'}):
            for roles in (['POS User'], ['POS User', 'Super Admin']):
                with patch.object(frappe, 'get_roles', return_value=roles):
                    self.assertTrue(module_access.allowed('POS', 'operator@example.test'))
                    self.assertFalse(module_access.allowed('Van Sales', 'operator@example.test'))

    def test_software_role_does_not_grant_emergency_payload_correction(self):
        from retail.pos_admin_recovery import require_recovery_administrator
        with patch.object(frappe.local, 'session', new=frappe._dict(user='software@example.test'), create=True), \
                patch.object(access_control, 'deny_technical_access', side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):
                require_recovery_administrator()
