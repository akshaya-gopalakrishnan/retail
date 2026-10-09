import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import frappe

from retail.licensing import enforcement as e
from retail.licensing import test_signature


class TestEnforcement(unittest.TestCase):
    def setUp(self):
        flags = patch.object(frappe.local, "flags", frappe._dict(), create=True)
        flags.start()
        self.addCleanup(flags.stop)

    def test_offline_signature(self):
        from retail.licensing.signature import verify_response
        fixture = test_signature.TestSignature()
        fixture.setUp()
        def verify(now=2000):
            return verify_response(fixture.token(), fixture.keys, "installation-1", now, offline=True)
        self.assertEqual(verify()["rules"]["allowed_users"], 5)
        for now in (999, 87400, 90000):
            with self.assertRaises(ValueError):
                verify(now)
        fixture.claims["rules"]["status"] = "Revoked"
        fixture.claims["exp"] = 1000
        with self.assertRaises(ValueError):
            verify()

    def test_access_and_reduced_limit(self):
        with patch.object(e, "local_rules", return_value={"allowed_users": 1}), patch.object(e, "assigned_users", return_value=["a", "b"]), patch.object(e.frappe, "throw", side_effect=frappe.PermissionError):
            e.check_user("a")
            for user in ("b", "unassigned", "Guest"):
                with self.assertRaises(frappe.PermissionError):
                    e.check_user(user)

    def test_recovery_does_not_require_license(self):
        with patch.object(e, "local_rules", side_effect=AssertionError):
            e.check_user("Administrator")
            with patch("retail.access_control.frappe.get_roles", return_value=["Super Admin"]):
                with self.assertRaises(AssertionError):
                    e.check_user("recovery@example.com")

    def test_full_seats_duplicates_and_removal(self):
        def doc(*users):
            return {"licensed_users": [frappe._dict(user=u) for u in users]}
        with patch.object(e, "assigned_users", return_value=["a"]), patch.object(e, "local_rules", return_value={"allowed_users": 1}) as rules, patch.object(e.frappe, "throw", side_effect=frappe.ValidationError):
            for users in (("a", "b"), ("a", "a"), ("Administrator",), ("Guest",)):
                with self.assertRaises(frappe.ValidationError):
                    e.validate_assignments(doc(*users))
            rules.reset_mock()
            e.validate_assignments(doc())
            rules.assert_not_called()

    def test_signed_rules_are_authority_and_login_never_uses_network(self):
        fixture = test_signature.TestSignature()
        fixture.setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config = {"celesta_license_public_keys": fixture.keys, "celesta_license_state_path": str(Path(directory.name) / "state.json")}
        # Display date is past; only the signed exp controls authorization.
        fixture.claims["rules"]["expiry_date"] = "1970-01-01"
        settings = {"verified_token": fixture.token(), "installation_id": "installation-1",
                    "allowed_users": 999, "status": "Active", "offline_valid_until": "2099-01-01"}
        from unittest.mock import Mock
        with patch.object(e.frappe, "get_roles", return_value=[]), \
                patch.object(e.frappe.local, "db", Mock(), create=True), \
                patch.object(e.frappe, "conf", config), \
                patch.object(e.time, "time", return_value=2000) as clock, \
                patch.object(e, "assigned_users", return_value=["cashier"]), \
                patch.object(e.frappe, "throw", side_effect=frappe.PermissionError), \
                patch("retail.licensing.client.requests.post", side_effect=AssertionError("Network on login")):
            e.frappe.db.get_singles_dict.return_value = settings
            from retail.licensing.state import verify_protected
            verify_protected(fixture.token(), fixture.keys, "installation-1", 1001)
            self.assertEqual(e.local_rules()["allowed_users"], 5)
            e.on_login(frappe._dict(user="cashier"))
            clock.return_value = 87400
            with self.assertRaises(frappe.PermissionError):
                e.check_user("cashier")
            clock.return_value = 2000
            settings["verified_token"] += "tampered"
            with self.assertRaises(frappe.PermissionError):
                e.check_user("cashier")

    def test_super_admin_has_no_denial_or_seat_bypass(self):
        with patch('retail.access_control.frappe.get_roles', return_value=['Super Admin']), patch.object(e, 'local_rules', side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):
                e.check_user('super-admin@example.com')
            e.check_user('Administrator')
        with patch('retail.access_control.frappe.get_roles', return_value=['Super Admin']), patch.object(e, 'local_rules', return_value={'allowed_users': 0}), patch.object(e, 'assigned_users', return_value=['super-admin@example.com']), patch.object(e.frappe, 'throw', side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):
                e.check_user('super-admin@example.com')

    def test_exact_recovery_allowlist(self):
        allowed = [(e.RECOVERY_METHOD, 'GET'), (e.RECOVERY_METHOD, 'POST'),
                   ('retail.licensing.client.activate', 'POST'),
                   ('retail.licensing.client.verify', 'POST'), ('login', 'POST'), ('logout', 'POST')]
        for name, method in allowed:
            path = '/api/method/' + name
            self.assertTrue(e.recovery_request_allowed(path, method, {}))
            self.assertTrue(e.recovery_request_allowed(path, method, {'cmd': name}))
            self.assertFalse(e.recovery_request_allowed(path, method, {'cmd': 'frappe.client.insert'}))
            for suffix in ('/extra', '/', '.extra'):
                self.assertFalse(e.recovery_request_allowed(path + suffix, method, {}))
            self.assertFalse(e.recovery_request_allowed(path, 'DELETE', {}))
        for path in ('/api/resource/Sales Invoice', '/api/v2/document/Sales Invoice',
                     '/api/method/frappe.client.get', '/api/method/frappe.client.insert',
                     '/api/method/frappe.client.save', '/api/method/frappe.client.set_value',
                     '/api/method/frappe.desk.query_report.run', '/api/method/run_doc_method',
                     '/api/method/frappe.desk.form.save.savedocs', '/app/sales-invoice',
                     '/api/v1/method/' + e.RECOVERY_METHOD, '/api/v2/method/' + e.RECOVERY_METHOD):
            self.assertFalse(e.recovery_request_allowed(path, 'POST', {}), path)
        self.assertFalse(e.recovery_request_allowed('/app/sales-invoice', 'POST', {'cmd': 'logout'}))

    def test_recovery_login_only_when_invalid(self):
        with patch.object(e.frappe, 'get_roles', return_value=['Super Admin']), \
                patch.object(e, 'local_rules', side_effect=frappe.PermissionError), \
                patch.object(e.frappe, 'clear_messages'):
            e.on_login(frappe._dict(user='recovery@example.com'))
            with self.assertRaises(frappe.PermissionError):
                e.check_user('recovery@example.com')
        with patch.object(e.frappe, 'get_roles', return_value=['Super Admin']), \
                patch.object(e, 'local_rules', return_value={'allowed_users': 1}), \
                patch.object(e, 'assigned_users', return_value=[]), \
                patch.object(e.frappe, 'throw', side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):
                e.on_login(frappe._dict(user='recovery@example.com'))

    def test_normal_requests_never_validate_license_or_seats(self):
        from unittest.mock import Mock
        paths = ['/app/sales-invoice', '/api/resource/Item',
                 '/api/method/frappe.desk.query_report.run',
                 '/api/method/frappe.desk.form.save.savedocs', '/api/method/logout']
        with patch.object(e.frappe.local, 'session', frappe._dict(user='cashier', data=frappe._dict()), create=True), \
                patch.object(e.frappe.local, 'form_dict', frappe._dict(), create=True), \
                patch.object(e.frappe.local, 'request', Mock(), create=True), \
                patch.object(e, 'local_rules', side_effect=AssertionError('Request validation')), \
                patch.object(e, 'assigned_users', side_effect=AssertionError('Request seats')):
            for path in paths:
                e.frappe.request.path = path
                e.frappe.request.method = 'GET'
                e.guard_request()
            e.frappe.session.data.celesta_recovery_user = 'cashier'
            e.frappe.request.path = '/api/method/logout'
            e.guard_request()
            e.frappe.request.path = '/app/sales-invoice'
            with patch.object(e.frappe, 'throw', side_effect=frappe.PermissionError):
                with self.assertRaises(frappe.PermissionError):
                    e.guard_request()

    def test_recovery_admission_persisted_without_revalidation(self):
        from unittest.mock import Mock
        with patch.object(e.frappe.local, 'session', frappe._dict(user='repair', data=frappe._dict()), create=True), \
                patch.object(e.frappe.local, 'session_obj', Mock(), create=True), \
                patch.object(e, 'local_rules', side_effect=AssertionError):
            e.frappe.flags.celesta_recovery_user = 'repair'
            e.on_session_creation(frappe._dict(user='repair'))
            self.assertTrue(e.recovery_login())
            e.frappe.local.session_obj.update.assert_called_once_with(force=True)
            e.frappe.flags.celesta_recovery_user = None
            e.on_session_creation(frappe._dict(user='repair'))
            self.assertFalse(e.recovery_login())

    def test_hooks_keep_login_recovery_and_hourly_sync(self):
        from retail import hooks
        self.assertEqual(hooks.on_login, 'retail.licensing.enforcement.on_login')
        self.assertEqual(hooks.on_session_creation, 'retail.licensing.enforcement.on_session_creation')
        self.assertEqual(hooks.auth_hooks.count('retail.licensing.enforcement.guard_request'), 1)
        self.assertIn('retail.licensing.client.scheduled_sync', hooks.scheduler_events['hourly'])

    def test_logout_guest_transition_never_checks_license_or_seats(self):
        from frappe.auth import LoginManager
        from unittest.mock import Mock
        manager = object.__new__(LoginManager)
        manager.user = 'cashier'
        with patch.object(e.frappe.local, 'session', frappe._dict(user='cashier', sid='test-logout', data=frappe._dict()), create=True), \
                patch.object(e.frappe.local, 'request', Mock(), create=True), \
                patch.object(e.frappe.local, 'session_obj', Mock(), create=True), \
                patch.object(e, 'local_rules', side_effect=AssertionError('Logout license check')), \
                patch.object(e, 'assigned_users', side_effect=AssertionError('Logout seat check')), \
                patch('frappe.auth.delete_session'), \
                patch.object(LoginManager, 'clear_cookies'), \
                patch.object(LoginManager, 'run_trigger'), \
                patch.object(LoginManager, 'post_login', side_effect=lambda *args: e.on_login(manager)):
            manager.logout()
            self.assertEqual(manager.user, 'Guest')
            e.on_session_creation(manager)
            e.frappe.local.session_obj.update.assert_not_called()
