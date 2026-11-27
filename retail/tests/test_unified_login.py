import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response
from retail.api import auth


class TestUnifiedLogin(TestCase):
    def setUp(self):
        def fail(message, exc=frappe.ValidationError, **kwargs):
            raise exc(message)
        self.throw = patch.object(frappe, 'throw', side_effect=fail)
        self.sidebar = patch.object(auth, 'get_retail_sidebar_permissions', return_value={'Sales': True, 'Sales Orders': True})
        self.sidebar.start()
        self.addCleanup(self.sidebar.stop)
        self.throw.start()
        self.addCleanup(self.throw.stop)

    def test_profile_roles_determine_module_even_when_profile_is_renamed(self):
        for roles, expected in ((['Sales User'], 'sales_order'), (['Van Sales User'], 'van_sales'),
                                (['Purchase User'], 'purchase'), (['Sales User', 'Purchase User'], None),
                                (['Employee'], None)):
            with self.subTest(roles=roles), patch.object(frappe, 'db', Mock()), patch.object(
                frappe, 'get_doc', return_value=frappe._dict(roles=[frappe._dict(role=r) for r in roles])):
                self.assertEqual(auth.get_user_module('someone@example.com'), expected)

    def test_unassigned_and_guest_have_no_module(self):
        with patch.object(frappe, 'db', Mock()) as db:
            db.get_value.return_value = None
            self.assertIsNone(auth.get_user_module('someone@example.com'))
            self.assertIsNone(auth.get_user_module('Guest'))

    def test_log_routing_excludes_other_modules_and_unknown_users(self):
        from retail import sales_order_api_log, van_sales_sync_log
        for module in ('sales_order', 'van_sales', 'purchase', None):
            for logger, target in ((sales_order_api_log, 'sales_order'), (van_sales_sync_log, 'van_sales')):
                for status in (200, 401):
                    request = Request(EnvironBuilder(path='/api/method/retail.api.auth.login',
                        method='POST', json={'usr': 'user@example.com', 'pwd': 'private-password'}).get_environ())
                    response = Response(json.dumps({'message': 'Logged In'}), content_type='application/json', status=status)
                    with self.subTest(module=module, logger=target, status=status), patch.object(
                        frappe.local, 'form_dict', {}, create=True), patch.object(frappe.local, 'session',
                        frappe._dict(user='Guest'), create=True), patch.object(frappe, 'db', Mock()) as db, patch.object(
                        frappe, 'get_doc') as doc, patch.object(logger, 'login_log_module', return_value=module), patch.object(
                        frappe, 'generate_hash', return_value='test'), patch('retail.van_sales_sync_log.now_datetime', return_value='2026-11-24 12:00:00'):
                        logger.after_request(request, response)
                        self.assertEqual(doc.called if target == 'sales_order' else db.bulk_insert.called, module == target)
                        if module == target:
                            saved = str(doc.call_args if target == 'sales_order' else db.bulk_insert.call_args)
                            self.assertNotIn('private-password', saved)

    def test_shared_response_and_permission_denial(self):
        from retail import login_sales_person
        for allowed in (True, False):
            manager = Mock()
            manager.login.return_value = None
            response = {
                'sales_person_id': 'SP-1', 'sales_person_name': 'Seller',
                'roles': ['Sales User'], 'permissions': {'sales': True, 'van_sales': False},
                'home_page': '/app/business-home', 'full_name': 'Seller',
            }
            form = {}
            with self.subTest(allowed=allowed), patch.object(frappe.local, 'login_manager', manager, create=True), patch.object(
                frappe.local, 'form_dict', form, create=True), patch.object(frappe.local, 'response', response, create=True), patch.object(
                frappe.local, 'session', frappe._dict(user='seller@example.com'), create=True), patch.object(
                auth, 'get_user_module', return_value='sales_order'), patch.object(frappe, 'has_permission', return_value=False), patch.object(login_sales_person, 'get_login_access',
                return_value={'roles': ['Sales User'], 'permissions': {'sales': allowed, 'van_sales': False}}), patch.object(
                login_sales_person, 'get_sales_person_identity', return_value={'sales_person_id': 'SP-1', 'sales_person_name': 'Seller'}):
                if allowed:
                    result = auth.login('seller@example.com', 'private')
                    self.assertEqual(result['app_module'], 'sales_order')
                    self.assertEqual(result['status'], 'Success')
                    self.assertIsNone(result['driverid'])
                    manager.logout.assert_not_called()
                else:
                    with self.assertRaises(frappe.PermissionError):
                        auth.login('seller@example.com', 'private')
                    manager.logout.assert_called_once()
                self.assertNotIn('pwd', form)
                self.assertEqual(response, {'home_page': '/app/business-home', 'full_name': 'Seller'})
                if allowed:
                    self.assertEqual(result['sales_person_id'], 'SP-1')
                    self.assertEqual(result['roles'], ['Sales User'])
                    self.assertEqual(result['permissions'], {'Sales': True, 'Sales Orders': True})

    def test_module_metadata_does_not_block_effective_permissions(self):
        from retail import login_sales_person
        for module in (None, 'sales_order', 'van_sales', 'purchase'):
            for sales, van, purchase in ((True, False, False), (False, False, True), (False, False, False)):
                manager = Mock()
                manager.login.return_value = None
                with self.subTest(module=module, access=(sales, van, purchase)), patch.object(
                    frappe.local, 'login_manager', manager, create=True), patch.object(
                    frappe.local, 'form_dict', {}, create=True), patch.object(
                    frappe.local, 'response', {}, create=True), patch.object(
                    frappe.local, 'session', frappe._dict(user='user@example.com'), create=True), patch.object(
                    auth, 'get_user_module', return_value=module), patch.object(
                    frappe, 'has_permission', return_value=purchase), patch.object(
                    login_sales_person, 'get_login_access', return_value={
                        'roles': ['Sales User'], 'permissions': {'sales': sales, 'van_sales': van}}), patch.object(
                    login_sales_person, 'get_sales_person_identity', return_value={}):
                    if sales or van or purchase:
                        result = auth.login('user@example.com', 'private')
                        self.assertEqual(result['status'], 'Success')
                        self.assertEqual(result['app_module'], module)
                        manager.logout.assert_not_called()
                    else:
                        with self.assertRaises(frappe.PermissionError):
                            auth.login('user@example.com', 'private')
                        manager.logout.assert_called_once()

    def test_incomplete_auth_does_not_resolve_module(self):
        manager = Mock()
        manager.login.return_value = False
        with patch.object(frappe.local, 'response', {}, create=True), patch.object(frappe.local, 'login_manager', manager, create=True), patch.object(
            frappe.local, 'form_dict', {}, create=True), patch.object(auth, 'get_user_module') as module:
            self.assertEqual(auth.login('user', 'private')['status'], 'AuthenticationRequired')
            module.assert_not_called()

    def test_van_login_returns_assignment_and_logs_out_on_invalid_assignment(self):
        from retail import login_sales_person
        ctx = frappe._dict(driver=frappe._dict(name='DRV-1'), van=frappe._dict(name='VAN-1'),
                           warehouse='Van Warehouse', company='Company', session=frappe._dict(name='VS-1'))
        for invalid in (False, True):
            manager = Mock()
            manager.login.return_value = None
            with self.subTest(invalid=invalid), patch.object(frappe.local, 'response', {}, create=True), patch.object(frappe.local, 'login_manager', manager, create=True), patch.object(
                frappe.local, 'form_dict', {}, create=True), patch.object(frappe.local, 'session', frappe._dict(user='driver@example.com'), create=True), patch.object(
                auth, 'get_user_module', return_value='van_sales'), patch.object(login_sales_person, 'get_login_access',
                return_value={'roles': ['Van Sales User'], 'permissions': {'sales': False, 'van_sales': True}}), patch.object(
                login_sales_person, 'get_sales_person_identity', return_value={'sales_person_id': None, 'sales_person_name': None}), patch(
                'retail.api.van_sales._context', return_value=ctx, side_effect=frappe.PermissionError if invalid else None):
                if invalid:
                    with self.assertRaises(frappe.PermissionError):
                        auth.login('driver@example.com', 'private')
                    manager.logout.assert_called_once()
                else:
                    result = auth.login('driver@example.com', 'private')
                    self.assertEqual((result['driverid'], result['vanid'], result['sessionid']), ('DRV-1', 'VAN-1', 'VS-1'))
                    self.assertEqual(result['warehouse'], 'Van Warehouse')

    def test_failed_login_resolves_identifier_without_using_callers_module(self):
        with patch.object(frappe, 'get_all', return_value=['user@example.com']), patch.object(
            auth, 'get_user_module', return_value='sales_order') as module:
            self.assertEqual(auth.login_log_module({'usr': 'user@example.com', 'app_module': 'van_sales'}), 'sales_order')
            module.assert_called_once_with('user@example.com')
        with patch.object(frappe, 'get_all', return_value=[]), patch.object(frappe, 'get_system_settings', return_value=False):
            self.assertIsNone(auth.login_log_module({'usr': 'unknown'}))

    def test_explicit_profile_module_resolves_profiles_with_supporting_roles(self):
        with patch.object(frappe, 'db', Mock()), patch.object(frappe, 'get_doc', return_value=frappe._dict(
            custom_app_module='van_sales', roles=[frappe._dict(role='Sales User'), frappe._dict(role='Van Sales User')])):
            self.assertEqual(auth.get_user_module('driver@example.com'), 'van_sales')


class TestRetailSidebarLoginPermissions(TestCase):
    def test_visible_menu_names_are_flat_true_values(self):
        pages = [
            {'name': 'Sales', 'label': 'Sales'},
            {'name': 'Van Sales', 'label': 'Van Sales'},
            {'name': 'internal-orders', 'title': 'Sales Orders'},
            {'name': 'internal-van', 'title': 'Van Link', 'label': 'Van Fleet'},
            {'name': 'Sales', 'label': 'Sales'},
            {},
        ]
        with patch('retail.workspace_permissions.get_workspace_sidebar_items', return_value={'pages': pages}):
            self.assertEqual(auth.get_retail_sidebar_permissions(), {
                'Sales': True, 'Van Sales': True, 'Sales Orders': True, 'Van Fleet': True,
            })

    def test_no_visible_menus_returns_empty_permissions(self):
        with patch('retail.workspace_permissions.get_workspace_sidebar_items', return_value={'pages': []}):
            self.assertEqual(auth.get_retail_sidebar_permissions(), {})
