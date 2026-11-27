import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from retail import van_sales_sync_log as log
from retail.sidebar_registry import registry, target_entries, routes


class TestSyncLogNavigation(TestCase):
    def test_logs_belong_to_their_own_categories_and_van_log_follows_reports(self):
        groups=registry()
        for dt,parent in [('POS Sync Log','POS'),('Van Sales Sync Log','Van Sales'),('Sales Order API Log','Sales')]:
            entries=target_entries('doctype',dt)
            self.assertEqual(len(entries),1,dt)
            group=next(g for g in groups if g['workspace']==parent)
            self.assertEqual(entries[0]['parent'],group['id'])
            self.assertEqual(routes()[entries[0]['workspace']],['List',dt])
        van=next(g for g in groups if g['workspace']=='Van Sales')
        names=[c['workspace'] for c in van['children']]
        self.assertEqual(names[names.index('Van Sales Reports')+1],'Van Sales Sync Logs')

    def test_unchecked_log_capability_blocks_target_without_hiding_other_van_features(self):
        from retail.sidebar_permissions import target_allowed
        van=next(g for g in registry() if g['workspace']=='Van Sales')
        selected={g['id'] for g in van['children'] if g['workspace']!='Van Sales Sync Logs'}|{van['id']}
        with patch('retail.sidebar_permissions.selection',return_value=selected):
            self.assertFalse(target_allowed('doctype','Van Sales Sync Log'))
            self.assertTrue(target_allowed('doctype','Van Session'))


class TestVanSyncLog(TestCase):
    def test_method_scope_preserves_pos_and_shared_login_partition(self):
        for method in ('retail.api.van_sales.post_sale','retail.api.van_sales.missing_method',
                'retail.api.pos_sync.get_expenses','retail.api.pos_sync.driver_login',
                'retail.van_stock.get_van_warehouse_stock'):
            self.assertTrue(log.is_van_method(method),method)
        for method in ('login','retail.api.pos_sync.get_pos_master_data','retail.api.pos_sync.save_sales_order',None,[]):
            self.assertFalse(log.is_van_method(method),str(method))

    def record(self,method,body,result,code=200):
        request=Request(EnvironBuilder(path='/api/method/'+method,method='POST',json=body).get_environ())
        response=Response(json.dumps(result),content_type='application/json',status=code)
        db=Mock()
        with patch.object(frappe.local,'form_dict',body,create=True), \
             patch.object(frappe.local,'session',frappe._dict(user='Guest'),create=True), \
             patch.object(frappe,'db',db),patch.object(log,'now_datetime',return_value='2026-11-24 16:00:00'), \
             patch.object(frappe,'generate_hash',return_value='sample-log'):
            log.after_request(request,response)
        if db.bulk_insert.called:
            args=db.bulk_insert.call_args.kwargs
            return dict(zip(args['fields'],args['values'][0])),db,response
        return None,db,response

    def test_failed_guest_login_is_logged_and_credentials_are_redacted(self):
        saved,db,response=self.record('retail.api.van_sales.driver_login',
            dict(userid='driver@example.com',password='do-not-store'),
            dict(exc_type='AuthenticationError',exception='private trace'),401)
        self.assertEqual(saved['status'],'Failed')
        self.assertEqual(saved['user'],'driver@example.com')
        self.assertEqual(saved['owner'],'Guest')
        self.assertNotIn('do-not-store',saved['request_json'])
        self.assertNotIn('private trace',saved['response_json'])
        self.assertEqual(response.get_json()['exception'],'private trace')
        db.commit.assert_called_once()

    def test_alias_payload_ids_and_duplicate_status_are_preserved(self):
        saved,_,_=self.record('retail.api.pos_sync.get_expenses',
            dict(data=json.dumps(dict(driver_id='D',session_id='S',request_id='R',api_secret='hidden'))),
            dict(message=dict(status='Posted',duplicate=True)))
        self.assertEqual((saved['driver_id'],saved['session_id'],saved['request_id']),('D','S','R'))
        self.assertEqual(saved['status'],'Duplicate')
        self.assertNotIn('hidden',saved['request_json'])

    def test_shared_login_success_and_failure_are_logged_without_credentials(self):
        for method in ('login', 'frappe.auth.login'):
            for code in (200, 401):
                saved,db,_=self.record(method,
                    dict(usr='driver@example.com',pwd='private-password'),
                    dict(message='Logged In' if code == 200 else 'Denied',sid='private-session'),code)
                self.assertEqual(saved['operation'],'Login (shared)')
                self.assertEqual(saved['user'],'driver@example.com')
                self.assertEqual(saved['status'],'Success' if code == 200 else 'Failed')
                self.assertNotIn('private-password',saved['request_json'])
                self.assertNotIn('private-session',saved['response_json'])
                db.commit.assert_called_once()

    def test_successful_read_and_business_failure_are_distinguished(self):
        for body,code,expected in [({'message':{'status':'Success'}},200,'Success'),
                ({'message':{'status':'Failed'}},200,'Failed'),
                ({'message':{'status':'AuthenticationRequired'}},200,'Pending'),
                ({'exc_type':'PermissionError'},403,'Failed')]:
            saved,_,_=self.record('retail.api.van_sales.get_expense_data',{},body,code)
            self.assertEqual(saved['status'],expected)

    def test_other_families_are_not_logged_by_van_callback(self):
        saved,db,_=self.record('retail.api.pos_sync.save_sales_order',{},dict(message={}))
        self.assertIsNone(saved)
        db.bulk_insert.assert_not_called()


class TestRestrictedSalesLogDiscovery(TestCase):
    def test_route_added_only_when_backend_read_is_already_allowed(self):
        from retail.sales_order_api_log import extend_bootinfo
        for allowed in (True, False):
            boot=frappe._dict(user=frappe._dict(can_read=['Item'],all_read=['Item']))
            with patch.object(frappe,'has_permission',return_value=allowed), patch('retail.sales_order_api_log.is_super_admin',return_value=True):
                extend_bootinfo(boot)
                extend_bootinfo(boot)
            for key in ('can_read','all_read'):
                self.assertEqual(boot.user[key].count('Sales Order API Log'),1 if allowed else 0)
