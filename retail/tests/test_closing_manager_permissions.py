import unittest
from unittest.mock import patch

import frappe
from retail.core_compat import closing_permissions as closing


class TestClosingManagerPermissions(unittest.TestCase):
    def test_native_permissions_and_cached_rules_are_preserved(self):
        import frappe.permissions as permissions
        from frappe.core.doctype.user_permission import user_permission as rules
        saved = frappe._dict(Employee=[frappe._dict(doc='E-7')], Company=[frappe._dict(doc='nesto')])
        def check(doc, **kwargs):
            return rules.get_user_permissions('manager')
        with patch.object(permissions, 'has_user_permission', check), \
                patch.object(rules, 'get_user_permissions', return_value=saved), \
                patch.object(frappe, 'get_installed_apps', return_value=['retail']):
            closing.install()
            for role in closing.MANAGER_ROLES:
                with self.subTest(role=role), patch.object(frappe, 'get_roles', return_value=[role]):
                    result = permissions.has_user_permission(frappe._dict(doctype='POS Branch Day Closing'), user='manager')
                    self.assertNotIn('Employee', result)
                    self.assertEqual(result.Company, saved.Company)
            with patch.object(frappe, 'get_roles', return_value=['POS Manager']):
                self.assertIn('Employee', permissions.has_user_permission(frappe._dict(doctype='POS Branch Day Closing'), user='manager'))
            with patch.object(frappe, 'get_roles', return_value=['Admin']):
                self.assertIn('Employee', permissions.has_user_permission(frappe._dict(doctype='Sales Invoice'), user='manager'))
            self.assertIn('Employee', saved)
            self.assertIn('Employee', rules.get_user_permissions('manager'))
            self.assertIsNone(closing._employee_exemption.get())
