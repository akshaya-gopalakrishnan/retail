"""Integration tests use an initialized site and roll back all settings writes."""
import time
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import frappe

from retail.licensing import client
from retail.licensing import test_signature


class TestClient(unittest.TestCase):
    def setUp(self):
        if not getattr(frappe.local, "db", None):
            self.skipTest("Requires initialized retail-test.localhost")
        frappe.set_user("Administrator")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config = patch.dict(frappe.conf, {"celesta_license_state_path": str(Path(directory.name) / "state.json")})
        self.config.start()

    def tearDown(self):
        frappe.db.rollback()
        frappe.set_user("Administrator")
        self.config.stop()

    def test_settings_and_activation(self):
        doc = frappe.get_doc(client.DOCTYPE)
        doc.license_key = "test-only-license-key"
        doc.save()
        installation = doc.installation_id
        self.assertTrue(installation)
        self.assertEqual(doc.get_password("license_key"), "test-only-license-key")
        doc.installation_id = "forged-id"
        doc.allowed_users = 999
        doc.save()
        self.assertEqual(doc.installation_id, installation)
        self.assertNotEqual(doc.allowed_users, 999)
        fixture = test_signature.TestSignature()
        fixture.setUp()
        now = int(time.time())
        fixture.claims.update(sub=installation, iat=now, nbf=now, exp=now + 86400)
        frappe.conf.celesta_license_server_url = "https://licenses.example.com"
        frappe.conf.celesta_license_public_keys = fixture.keys
        response = Mock(status_code=200, content=b"{}")
        response.json.return_value = {"message": {"token": fixture.token(), "allowed_users": 999}}
        with patch.object(client.requests, "post", return_value=response):
            self.assertEqual(client.activate()["status"], "Active")
        self.assertEqual(frappe.get_doc(client.DOCTYPE).allowed_users, 5)
        from retail.licensing import enforcement
        # User onboarding jobs are unrelated to seat authorization.
        with patch.object(frappe, "enqueue"):
            user = frappe.get_doc({"doctype": "User", "email": "seat-test@example.com",
                                   "first_name": "Seat Test", "enabled": 1,
                                   "send_welcome_email": 0}).insert()
        doc = frappe.get_doc(client.DOCTYPE)
        doc.set("licensed_users", [{"user": user.name}])
        doc.save()
        self.assertEqual(client.used_users(), 1)
        enforcement.check_user(user.name)
        with self.assertRaises(frappe.PermissionError):
            enforcement.check_user("unassigned@example.com")
        doc.verified_token = "forged"
        doc.save()
        enforcement.check_user(user.name)
        doc.set("licensed_users", [])
        doc.save()
        with self.assertRaises(frappe.PermissionError):
            enforcement.check_user(user.name)
        with patch.object(client.requests, "post", side_effect=RuntimeError("network failure")):
            with self.assertRaises(frappe.ValidationError):
                client.verify()
        self.assertEqual(frappe.get_doc(client.DOCTYPE).allowed_users, 5)
        doc = frappe.get_doc(client.DOCTYPE)
        doc.license_key = "replacement-key"
        doc.save()
        self.assertFalse(doc.status)
        self.assertEqual(doc.installation_id, installation)

    def test_permissions(self):
        for role in ("Customer Administrator", "System Manager", "Sales User"):
            with patch("retail.access_control.frappe.get_roles", return_value=[role]):
                self.assertFalse(frappe.has_permission(client.DOCTYPE, "read", user="license-test@example.com"))
        frappe.set_user("Guest")
        for action in (client.activate, client.verify):
            with self.assertRaises(frappe.PermissionError):
                action()

    def test_scheduler_registration_mechanism(self):
        from frappe.core.doctype.scheduled_job_type.scheduled_job_type import insert_single_event
        method = 'retail.licensing.client.scheduled_sync'
        insert_single_event('Hourly', method)
        insert_single_event('Hourly', method)
        rows = frappe.get_all('Scheduled Job Type', filters={'method': method}, fields=['frequency', 'stopped'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].frequency, 'Hourly')
        self.assertFalse(rows[0].stopped)

    def test_restricted_recovery_requests_and_restoration(self):
        """Real DB/users/passwords/signatures; central HTTPS response alone is mocked."""
        import uuid
        from werkzeug.exceptions import HTTPException
        from werkzeug.test import EnvironBuilder
        from werkzeug.wrappers import Request
        from frappe.auth import LoginManager
        from frappe.handler import execute_cmd
        from frappe.utils.password import update_password
        from retail.licensing import enforcement as e

        tag = uuid.uuid4().hex[:10]
        super_user = f'recovery-{tag}@example.com'
        normal_user = f'normal-{tag}@example.com'
        password = uuid.uuid4().hex
        with patch.object(frappe, 'enqueue'):
            for user, roles in ((super_user, ['Super Admin']), (normal_user, ['Stock User'])):
                frappe.get_doc({'doctype': 'User', 'email': user, 'first_name': 'Recovery Test',
                                'enabled': 1, 'send_welcome_email': 0,
                                'roles': [{'role': role} for role in roles]}).insert()
                update_password(user, password)
        self.addCleanup(lambda: [frappe.clear_cache(user=u) for u in (super_user, normal_user)])
        fixture = test_signature.TestSignature()
        fixture.setUp()
        now = int(time.time())
        fixture.claims.update(iat=now, nbf=now, exp=now + 86400)
        with patch.dict(frappe.conf, {'celesta_license_server_url': 'https://licenses.example.com',
                                     'celesta_license_public_keys': fixture.keys}), \
                patch.object(frappe.local, 'request', None, create=True), \
                patch.object(frappe.local, 'form_dict', frappe._dict(), create=True), \
                patch.object(frappe.local, 'request_ip', '127.0.0.1', create=True), \
                patch('frappe.sessions.get_csrf_token', return_value='test-csrf'), \
                patch.object(e, 'recovery_login', side_effect=lambda: frappe.session.user == recovery_user):
            recovery_user = None
            def request(path, method='GET', **form):
                frappe.local.request = Request(EnvironBuilder(path=path, method=method).get_environ())
                frappe.local.form_dict = frappe._dict(form)
                e.guard_request()

            def rpc(name, **form):
                request('/api/method/' + name, 'POST', **form)
                return execute_cmd(name)

            business = [('/app/sales-invoice', 'GET', {}),
                        ('/api/resource/Item', 'GET', {}),
                        ('/api/v2/document/Item', 'GET', {}),
                        ('/api/method/frappe.client.get', 'GET', {'doctype': 'Item'}),
                        ('/api/method/frappe.client.insert', 'POST', {'doc': '{"doctype":"Sales Invoice"}'}),
                        ('/api/method/frappe.client.save', 'POST', {'doc': '{"doctype":"Sales Invoice"}'}),
                        ('/api/method/frappe.client.set_value', 'POST', {'doctype': 'Item'}),
                        ('/api/method/frappe.desk.query_report.run', 'GET', {}),
                        ('/api/method/frappe.desk.form.load.getdoc', 'GET', {'doctype': client.DOCTYPE}),
                        ('/api/method/frappe.desk.form.save.savedocs', 'POST', {'doc': '{"doctype":"Sales Invoice"}'}),
                        ('/api/method/run_doc_method', 'POST', {}),
                        ('/app/celesta-license-settings', 'GET', {'cmd': 'frappe.client.get'}),
                        ('/api/method/' + e.RECOVERY_METHOD, 'POST', {'cmd': 'frappe.client.insert'}),
                        ('/private/files/secret.csv', 'GET', {})]
            for status in ('Missing', 'Invalid', 'Expired', 'Suspended', 'Revoked', 'Deadline'):
                with self.subTest(status=status):
                    frappe.set_user('Administrator')
                    doc = frappe.get_doc(client.DOCTYPE)
                    doc.license_key = 'temporary-test-key'
                    doc.save()
                    fixture.claims['sub'] = doc.installation_id
                    fixture.claims['license_version'] += 1
                    fixture.claims['rules']['status'] = 'Active' if status in ('Missing', 'Invalid', 'Deadline') else status
                    fixture.claims['exp'] = now + 86400 if status in ('Missing', 'Invalid') else now
                    response = Mock(status_code=200, content=b'{}')
                    response.json.return_value = {'message': {'token': fixture.token()}}
                    with patch.object(client.requests, 'post', return_value=response):
                        client.verify()
                    if status in ('Missing', 'Invalid'):
                        frappe.db.set_single_value(client.DOCTYPE, 'verified_token', '' if status == 'Missing' else 'tampered')
                    for path, method, form in business:
                        request(path, method, **form)  # Administrator bypasses licensing.
                    for user in (super_user, normal_user):
                        frappe.local.form_dict = frappe._dict()
                        manager = object.__new__(LoginManager)
                        manager.authenticate(user, password)
                        self.assertEqual(manager.user, user)
                        if user == normal_user:
                            with self.assertRaises(frappe.PermissionError):
                                e.on_login(manager)
                        else:
                            e.on_login(manager)
                    recovery_user = super_user
                    frappe.set_user(super_user)
                    request('/api/method/login', 'POST')
                    self.assertEqual(frappe.response['home_page'], e.RECOVERY_ROUTE)
                    with self.assertRaises(HTTPException) as page:
                        request(e.RECOVERY_ROUTE)
                    self.assertEqual(page.exception.response.status_code, 200)
                    self.assertIn('Celesta License Settings', page.exception.response.get_data(as_text=True))
                    with self.assertRaises(HTTPException) as redirect:
                        request('/app')
                    self.assertEqual(redirect.exception.response.location, e.RECOVERY_ROUTE)
                    request('/api/method/logout', 'POST')
                    for path, method, form in business:
                        with self.assertRaises(frappe.PermissionError, msg=path):
                            request(path, method, **form)
                    self.assertTrue(frappe.has_permission(client.DOCTYPE, 'read'))
                    rpc(e.RECOVERY_METHOD, users=[normal_user])
                    rpc(e.RECOVERY_METHOD, users=[])
                    rpc(e.RECOVERY_METHOD, users=[super_user, normal_user], license_key='temporary-test-key')
                    self.assertEqual(e.assigned_users(), [super_user, normal_user])
                    frappe.set_user(normal_user)
                    for path in (e.RECOVERY_ROUTE, '/api/method/' + e.RECOVERY_METHOD,
                                 '/api/method/retail.licensing.client.activate', '/app/sales-invoice'):
                        request(path)  # No authenticated-request license validation.
                    frappe.set_user(super_user)
                    with patch.object(client.requests, 'post', return_value=response):
                        # Both repair operations execute even when central still denies access.
                        rpc('retail.licensing.client.activate')
                        if status in ('Missing', 'Invalid'):
                            frappe.db.set_single_value(client.DOCTYPE, 'verified_token', 'tampered')
                        rpc('retail.licensing.client.verify')
                    fixture.claims['license_version'] += 1
                    fixture.claims['rules'].update(status='Active', allowed_users=1)
                    fixture.claims['exp'] = now + 86400
                    response.json.return_value = {'message': {'token': fixture.token()}}
                    with patch.object(client.requests, 'post', return_value=response):
                        rpc('retail.licensing.client.verify')
                    with self.assertRaises(frappe.PermissionError):
                        request('/api/method/frappe.client.get', 'GET', doctype='Item')
                    e.on_login(frappe._dict(user=super_user))
                    recovery_user = None
                    request('/api/method/frappe.client.get', 'GET', doctype='Item')
                    # Reordering the seats removes Super Admin's effective seat.
                    frappe.set_user('Administrator')
                    doc = frappe.get_doc(client.DOCTYPE)
                    doc.set('licensed_users', [{'user': normal_user}, {'user': super_user}])
                    doc.save()
                    frappe.set_user(super_user)
                    for path in (e.RECOVERY_ROUTE, '/api/method/' + e.RECOVERY_METHOD, '/api/method/retail.licensing.client.verify', '/app/sales-invoice'):
                        request(path)  # Seat changes apply only at the next login.
                    with self.assertRaises(frappe.PermissionError):
                        e.on_login(frappe._dict(user=super_user))

    def test_key_regeneration_renewal_and_database_restore(self):
        import json
        from retail.licensing import enforcement
        doc = frappe.get_doc(client.DOCTYPE)
        doc.license_key = 'temporary-renewal-test'
        doc.save()
        fixture = test_signature.TestSignature()
        fixture.setUp()
        now = int(time.time())
        fixture.claims.update(sub=doc.installation_id, iat=now, nbf=now, exp=now + 86400, license_version=5)
        with patch.dict(frappe.conf, {'celesta_license_server_url': 'https://licenses.example.com',
                                     'celesta_license_public_keys': fixture.keys}):
            def response(*args, **kwargs):
                request = kwargs['json']
                self.assertIn(request['current_license_id'], (None, fixture.claims['license_id']))
                result = Mock(status_code=200, content=b'{}')
                result.json.return_value = {'message': {'token': fixture.token()}}
                return result
            with patch.object(client.requests, 'post', side_effect=response):
                client.activate()
                original = frappe.db.get_singles_dict(client.DOCTYPE)
                protected = Path(frappe.conf.celesta_license_state_path)
                floor = protected.read_bytes()
                # A regenerated credential clears DB display/token data only.
                doc = frappe.get_doc(client.DOCTYPE)
                doc.license_key = 'temporary-regenerated-key'
                doc.save()
                self.assertFalse(doc.verified_token)
                self.assertEqual(protected.read_bytes(), floor)
                fixture.claims.update(license_version=6)
                client.verify()
                self.assertEqual(enforcement.local_rules()['status'], 'Active')
                protected = Path(frappe.conf.celesta_license_state_path)
                saved = protected.read_bytes()
                self.assertEqual(json.loads(saved)['highest_license_version'], 6)
                self.assertEqual(json.loads(saved)['license_id'], fixture.claims['license_id'])
                for counter in ('highest_license_version', 'highest_accepted_iat', 'highest_trusted_time'):
                    self.assertGreaterEqual(json.loads(saved)[counter], json.loads(floor)[counter])
                # Restore actual singleton rows, including the old signed token and iat.
                frappe.db.set_single_value(client.DOCTYPE, dict(original))
                with self.assertRaises(frappe.PermissionError):
                    enforcement.local_rules()
                self.assertEqual(protected.read_bytes(), saved)
