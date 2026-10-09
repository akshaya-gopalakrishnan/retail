"""Site-backed regressions for Guest entry; run on the development/test site.

Mail delivery and signed-license inputs use fixtures; authentication, password
verification, session creation, CSRF, routing and login rendering remain real.
"""
import json
import re
import unittest
import uuid
from urllib.parse import urlencode, urlsplit
from unittest.mock import patch

import frappe
from frappe.app import application
from frappe.website.page_renderers.template_page import TemplatePage
from werkzeug.test import Client, EnvironBuilder
from werkzeug.wrappers import Response, Request

from retail import guest_entry
from retail.licensing import enforcement


class TestGuestEntry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = frappe.local.site
        cls.sites_path = frappe.local.sites_path
        cls.username = 'guestentry' + uuid.uuid4().hex[:12]
        cls.email = cls.username + '@example.invalid'
        cls.password = uuid.uuid4().hex + 'Aa1!'
        frappe.set_user('Administrator')
        frappe.get_doc(dict(doctype='User', email=cls.email, username=cls.username,
                            first_name='Guest Entry Regression', send_welcome_email=0,
                            new_password=cls.password, user_type='System User',
                            roles=[dict(role='System Manager')])).insert(ignore_permissions=True)
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        frappe.init(site=cls.site, sites_path=cls.sites_path)
        frappe.connect()
        frappe.set_user('Administrator')
        from frappe.sessions import clear_sessions
        clear_sessions(cls.email)
        frappe.delete_doc('User', cls.email, ignore_permissions=True, force=True)
        frappe.db.commit()

    def make_client(self):
        return Client(application, Response, use_cookies=True)

    def setUp(self):
        frappe.init(site=self.site, sites_path=self.sites_path)
        frappe.connect()
        self.client = self.make_client()
        self.base_url = 'http://' + self.site
        # Give each test its own fixture identity; repeated runs must not consume
        # the live site's localhost password-reset/email-link rate limits.
        identity = uuid.uuid4().hex[:24]
        self.request_ip = '2001:db8:' + ':'.join(identity[i:i + 4] for i in range(0, 24, 4))

    def request(self, path, method='GET', **kwargs):
        headers = dict(kwargs.pop('headers', {}))
        headers['X-Forwarded-For'] = self.request_ip
        kwargs['headers'] = headers
        response = self.client.open(path, method=method, base_url=self.base_url, **kwargs)
        response.get_data()
        response.close()
        return response

    def login(self, username=False):
        # Mock signed configuration only. The real on_login/check_user and all
        # authentication hooks execute; no license assignment is saved.
        with patch.object(enforcement, 'local_rules', return_value={'allowed_users': 1}), \
             patch.object(enforcement, 'assigned_users', return_value=[self.email]), \
             patch.object(enforcement, 'on_login', wraps=enforcement.on_login) as license_hook:
            response = self.request('/login', 'POST', data={'cmd': 'login',
                                    'usr': self.username if username else self.email,
                                    'pwd': self.password})
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:500])
            self.assertEqual(response.json['message'], 'Logged In')
            license_hook.assert_called_once()
        return response

    def test_guest_login_standard_render_and_no_desk_discovery(self):
        with patch('frappe.apps.get_apps', side_effect=AssertionError('Desk discovery')), \
             patch('frappe.website.utils.get_apps', side_effect=AssertionError('Desk discovery')), \
             patch('frappe.desk.desktop.get_workspace_sidebar_items', side_effect=AssertionError('Workspace discovery')):
            response = self.request('/login')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for marker in ('id="login_email"', 'id="login_password"', 'form-forgot',
                       'frappe.core.doctype.user.user.reset_password', 'frappe.www.login.send_login_link',
                       'frappe.csrf_token', 'CELESTA', 'retail_website.bundle', 'frappe-web.bundle'):
            self.assertIn(marker, html)
        boot = json.JSONDecoder().raw_decode(html.split('frappe.boot = ', 1)[1].lstrip())[0]
        self.assertEqual(boot['apps_data'], {'apps': [], 'is_desk_apps': 1, 'default_path': ''})
        self.assertNotIn('allowed_workspaces', boot)
        self.assertNotIn('reports', boot)

    def test_guest_app_redirects_before_website_settings(self):
        for path in ('/app', '/app/business-home'):
            with self.subTest(path=path), patch(
                'frappe.website.page_renderers.base_template_page.get_website_settings',
                side_effect=AssertionError('Website context initialized')
            ), patch('frappe.desk.desktop.get_workspace_sidebar_items', side_effect=AssertionError('Discovery')):
                response = self.request(path)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response.headers['Location'], '/login?' + urlencode({'redirect-to': path}))
                self.assertIn('no-store', response.headers['Cache-Control'])
                self.assertEqual(response.get_data(), b'')

    def test_password_and_username_login(self):
        original = frappe.db.get_single_value
        with patch('frappe.database.database.Database.get_single_value',
                   side_effect=lambda doctype, field, *args, **kwargs: 1 if (doctype, field) == ('System Settings', 'allow_login_using_user_name') else original(doctype, field, *args, **kwargs)):
            self.login(username=True)

    def test_authenticated_desk_routes_use_standard_renderer_and_permissions(self):
        self.login()
        for path in ('/app', '/app/business-home'):
            with self.subTest(path=path), patch.object(
                guest_entry, 'get_guest_login_settings', side_effect=AssertionError('Guest context for user')
            ), patch('frappe.sessions.get', wraps=frappe.sessions.get) as boot:
                response = self.request(path)
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:500])
                boot.assert_called_once()
                self.assertIn('frappe.boot', response.get_data(as_text=True))

    def test_authenticated_login_redirect_destinations(self):
        self.login()
        for path in ('/app', '/app/business-home'):
            response = self.request('/login?' + urlencode({'redirect-to': path}))
            self.assertEqual(response.status_code, 301)
            self.assertEqual(response.headers['Location'], self.base_url + path)

    def test_guest_login_preserves_redirect_query_handling(self):
        for path in ('/app', '/app/business-home'):
            response = self.request('/login?' + urlencode({'redirect-to': path}))
            self.assertEqual(response.status_code, 200)
            self.assertIn('frappe.utils.get_url_arg("redirect-to")', response.get_data(as_text=True))

    def test_settings_and_boot_parity_with_standard_frappe(self):
        from frappe.website.doctype.website_settings import website_settings
        from frappe.website import utils
        frappe.set_user('Guest')
        frappe.local.request = Request(EnvironBuilder(path='/login', base_url=self.base_url).get_environ())
        with patch.object(utils, 'get_apps', return_value=[]), patch.object(utils, 'get_default_path', return_value=None):
            standard = website_settings.get_website_settings()
        optimized = guest_entry.get_guest_login_settings()
        self.assertEqual(optimized, standard)

    def test_social_ldap_and_email_configuration_still_reaches_standard_controller(self):
        from frappe.www import login
        frappe.set_user('Guest')
        frappe.local.request = Request(EnvironBuilder(path='/login?redirect-to=/app/business-home', base_url=self.base_url).get_environ())
        context = guest_entry.get_guest_login_settings()
        original = frappe.get_system_settings
        provider = frappe._dict(name='test-provider', client_id='test-id', base_url='https://example.invalid', provider_name='Custom', icon=None)
        with patch('frappe.www.login.frappe.get_all', return_value=[provider]), \
             patch.object(login, 'get_decrypted_password', return_value='test-secret'), \
             patch.object(login, 'get_oauth_keys', return_value={'client_id': 'test-id'}), \
             patch.object(login, 'get_oauth2_authorize_url', return_value='https://example.invalid/auth') as oauth, \
             patch('frappe.db.get_value', return_value=1), \
             patch('frappe.integrations.doctype.ldap_settings.ldap_settings.LDAPSettings.get_ldap_client_settings', return_value={'enabled': 1}), \
             patch('frappe.get_system_settings', side_effect=lambda key: 1 if key == 'login_with_email_link' else original(key)):
            login.get_context(context)
        self.assertTrue(context.login_with_email_link)
        self.assertTrue(context.ldap_settings['enabled'])
        self.assertEqual(context.provider_logins[0]['name'], 'test-provider')
        oauth.assert_called_once_with('test-provider', self.base_url + '/app/business-home')
        context.base_template_path = 'templates/base.html'
        context._context_dict = context
        context.title = 'Login'
        context.dev_server = 0
        html = frappe.render_template('www/login.html', context)
        self.assertIn('form-login-with-email-link', html)
        self.assertIn('https://example.invalid/auth', html)
        self.assertIn('btn-ldap-login', html)

    def test_email_link_and_forgot_password_endpoints(self):
        original = frappe.get_system_settings
        with patch('frappe.get_system_settings', side_effect=lambda key: 1 if key == 'login_with_email_link' else original(key)), \
             patch('frappe.sendmail') as mail:
            response = self.request('/api/method/frappe.www.login.send_login_link', 'POST', data={'email': self.email})
            self.assertEqual(response.status_code, 200)
            mail.assert_called_once()
            link = mail.call_args.kwargs['args']['link']
            self.assertIn('/api/method/frappe.www.login.login_via_key?key=', link)
        destination = urlsplit(link)
        with patch.object(enforcement, 'local_rules', return_value={'allowed_users': 1}), \
             patch.object(enforcement, 'assigned_users', return_value=[self.email]):
            response = self.request(destination.path + '?' + destination.query)
            self.assertIn(response.status_code, (301, 302))
        response = self.request('/api/method/frappe.auth.get_logged_user')
        self.assertEqual(response.json['message'], self.email)
        self.client = self.make_client()
        with patch('frappe.core.doctype.user.user.User.password_reset_mail') as mail:
            response = self.request('/api/method/frappe.core.doctype.user.user.reset_password', 'POST', data={'user': self.email})
            self.assertEqual(response.status_code, 200)
            mail.assert_called_once()

    def test_no_authentication_permission_or_license_bypass(self):
        response = self.request('/api/method/frappe.apps.get_apps')
        self.assertIn(response.status_code, (403, 401))
        response = self.request('/api/method/frappe.desk.desktop.get_workspace_sidebar_items')
        self.assertIn(response.status_code, (403, 401))
        response = self.request('/login', 'POST', data={'cmd': 'login', 'usr': self.email, 'pwd': 'wrong-password'})
        self.assertEqual(response.status_code, 401)
        with patch.object(enforcement, 'local_rules', return_value={'allowed_users': 0}), \
             patch.object(enforcement, 'assigned_users', return_value=[]):
            response = self.request('/login', 'POST', data={'cmd': 'login', 'usr': self.email, 'pwd': self.password})
            self.assertEqual(response.status_code, 403)
        response = self.request('/app')
        self.assertEqual(response.status_code, 301)

    def test_session_csrf_lifecycle_and_language(self):
        self.login()
        response = self.request('/app')
        self.assertEqual(response.status_code, 200)
        with patch('frappe.auth.HTTPRequest.validate_csrf_token', wraps=None) as validation:
            # Prove the lifecycle still reaches the framework validator.
            self.request('/api/method/frappe.auth.get_logged_user')
            validation.assert_called_once()
        response = self.request('/api/method/frappe.auth.get_logged_user', 'POST', headers={'X-Frappe-CSRF-Token': 'invalid'})
        self.assertEqual(response.status_code, 400)
        response = self.request('/api/method/frappe.auth.get_logged_user')
        self.assertEqual(response.json['message'], self.email)
        self.client = self.make_client()
        response = self.request('/login?_lang=ar')
        self.assertEqual(response.status_code, 200)
        self.assertIn('<html lang="ar">', response.get_data(as_text=True))

    def test_renderer_rejects_authenticated_other_routes_and_page_overrides(self):
        frappe.local.request = Request(EnvironBuilder(path='/login', base_url=self.base_url).get_environ())
        frappe.set_user(self.email)
        self.assertFalse(guest_entry.GuestLoginPage('login').can_render())
        frappe.set_user('Guest')
        self.assertFalse(guest_entry.GuestLoginPage('apps').can_render())
        page = guest_entry.GuestLoginPage('login')
        page.app = 'retail'
        self.assertFalse(page.can_render())

    def test_authenticated_resolution_delegates_without_guest_controller(self):
        frappe.set_user(self.email)
        for path in ('app', 'app/business-home', 'login'):
            frappe.local.request = Request(EnvironBuilder(path='/' + path, base_url=self.base_url).get_environ())
            with patch.object(guest_entry, 'resolve_path', return_value='standard-endpoint') as resolve, \
                 patch('frappe.www.app.get_context', side_effect=AssertionError('Early Guest controller')):
                self.assertEqual(guest_entry.resolve_guest_entry(path), 'standard-endpoint')
                resolve.assert_called_once_with(path)
        with patch.object(TemplatePage, 'set_template_path', side_effect=AssertionError('Extra template discovery')):
            self.assertFalse(guest_entry.GuestLoginPage('login').can_render())

    def test_invalid_authorization_is_rejected_before_guest_routing(self):
        with patch.object(guest_entry, 'resolve_guest_entry', wraps=guest_entry.resolve_guest_entry) as resolve:
            response = self.request('/app', headers={'Authorization': 'token invalid:invalid'})
            self.assertEqual(response.status_code, 401)
            self.assertTrue(all(call.args[0] != 'app' for call in resolve.call_args_list))
