import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch
import frappe
from retail.pos_privileges import require_employee_pos_management
# Load modules before patching their imported access helpers.
from retail import delegated_access, module_access, sidebar_permissions


class TestPOSDelegation(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in (
            ('retail.access_control.is_super_admin', False),
            ('retail.access_control.is_protected_user', False),
            ('retail.delegated_access.is_customer_admin', True),
            ('retail.delegated_access.manages', True),
            ('retail.module_access.require', None),
            ('retail.sidebar_permissions.target_allowed', True),
        ):
            self.stack.enter_context(patch(name, return_value=value))
        self.doc = Mock()
        self.doc.name = 'employee'
        self.doc.owner = frappe.session.user
        self.doc.is_new.return_value = False
        self.doc.get_doc_before_save.return_value = self.doc
        self.doc.get.side_effect = lambda key: {'user_id': 'staff@example.com'}.get(key)
        self.stack.enter_context(patch('frappe.get_doc', return_value=Mock()))

    def test_customer_can_manage_owned_staff(self):
        require_employee_pos_management(self.doc)
        self.doc.check_permission.assert_called_with('write')

    def test_unrelated_staff_denied(self):
        with patch('retail.delegated_access.manages', return_value=False):
            with self.assertRaises(frappe.PermissionError):
                require_employee_pos_management(self.doc)

    def test_protected_staff_denied(self):
        with patch('retail.access_control.is_protected_user', return_value=True):
            with self.assertRaises(frappe.PermissionError):
                require_employee_pos_management(self.doc)

    def test_hidden_employee_menu_denied(self):
        with patch('retail.sidebar_permissions.target_allowed', return_value=False):
            with self.assertRaises(frappe.PermissionError):
                require_employee_pos_management(self.doc)

    def test_system_manager_alone_denied(self):
        with patch('retail.delegated_access.is_customer_admin', return_value=False):
            with self.assertRaises(frappe.PermissionError):
                require_employee_pos_management(self.doc)

    def test_saved_links_checked_before_relink(self):
        previous = Mock()
        previous.get.return_value = 'other@example.com'
        self.doc.get_doc_before_save.return_value = previous
        with patch('retail.delegated_access.manages', return_value=False):
            with self.assertRaises(frappe.PermissionError):
                require_employee_pos_management(self.doc)
