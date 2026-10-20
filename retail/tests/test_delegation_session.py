"""Browser session context must survive permission cascades and failures."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from retail.delegated_access import _staff_sync_administrator, sync_children


class TestDelegationSession(unittest.TestCase):
    def setUp(self):
        self.fields = ('session', 'session_obj', 'cache', 'form_dict', 'jenv',
                       'role_permissions', 'new_doc_templates', 'user_perms')
        self.missing = object()
        self.saved = {key: getattr(frappe.local, key, self.missing) for key in self.fields}
        self.addCleanup(self.restore)
        self.session = frappe._dict(user='client@example.com', sid='synthetic-session-id',
            data=frappe._dict(user='client@example.com', csrf_token='synthetic-csrf',
                              session_expiry='72:00:00', celesta_recovery_user=None))
        frappe.local.session = self.session
        frappe.local.session_obj = SimpleNamespace(data=self.session)
        for key in self.fields[2:]:
            setattr(frappe.local, key, {'original': key})
        self.originals = {key: getattr(frappe.local, key) for key in self.fields}
        self.contents = copy.deepcopy(self.session)

    def restore(self):
        for key, value in self.saved.items():
            if value is self.missing:
                if hasattr(frappe.local, key):
                    delattr(frappe.local, key)
            else:
                setattr(frappe.local, key, value)

    def assert_preserved(self):
        for key, original in self.originals.items():
            self.assertIs(getattr(frappe.local, key), original, key)
        self.assertEqual(self.session, self.contents)
        self.assertIs(frappe.local.session_obj.data, self.session)

    def test_success_preserves_session_and_request_objects(self):
        with _staff_sync_administrator():
            self.assertEqual(frappe.session.user, 'Administrator')
            self.assertIsNot(frappe.local.session, self.session)
            self.assertEqual(self.session, self.contents)
        self.assert_preserved()

    def test_failure_restores_original_context(self):
        with self.assertRaisesRegex(RuntimeError, 'simulated failure'):
            with _staff_sync_administrator():
                raise RuntimeError('simulated failure')
        self.assert_preserved()

    def test_nested_cascades_restore_each_context(self):
        with _staff_sync_administrator():
            temporary = frappe.local.session
            with _staff_sync_administrator():
                self.assertIsNot(frappe.local.session, temporary)
            self.assertIs(frappe.local.session, temporary)
        self.assert_preserved()

    def test_real_hook_without_children_preserves_session(self):
        doc = frappe._dict(name='synthetic-staff', roles=[frappe._dict(role='Stock User')],
                          block_modules=[], user_emails=[])
        doc.get_doc_before_save = lambda: frappe._dict(roles=[], block_modules=[], user_emails=[])
        with patch('frappe.clear_cache'), patch('frappe.get_all', return_value=[]), patch('frappe.get_roles', return_value=[]):
            sync_children(doc)
        self.assert_preserved()

    def test_real_hook_error_preserves_session(self):
        doc = frappe._dict(name='synthetic-staff', roles=[frappe._dict(role='Stock User')],
                          block_modules=[], user_emails=[])
        doc.get_doc_before_save = lambda: frappe._dict(roles=[], block_modules=[], user_emails=[])
        with patch('frappe.clear_cache', side_effect=RuntimeError('simulated failure')):
            with self.assertRaises(RuntimeError):
                sync_children(doc)
        self.assert_preserved()
