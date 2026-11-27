import json
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from retail.sales_order_api_log import after_request, sanitize_payload


class TestSalesOrderAPILog(TestCase):
    def test_shared_login_success_failure_and_v1_route_are_logged(self):
        for method in ('login', 'frappe.auth.login', 'retail.api.auth.login', '/api/v1/method/login'):
            for code in (200, 401):
                incoming = {'usr': 'seller@example.com', 'pwd': 'private-password'}
                path = method if method.startswith('/') else '/api/method/' + method
                request = Request(EnvironBuilder(path=path, method='POST', json=incoming).get_environ())
                response = Response(json.dumps({'message': 'Logged In', 'sid': 'private-session'}), content_type='application/json', status=code)
                with patch.object(frappe.local, 'form_dict', {}, create=True), patch.object(frappe.local, 'session', frappe._dict(user='Guest'), create=True), patch.object(frappe, 'get_doc') as get_doc, patch.object(frappe, 'db', Mock()), patch('retail.sales_order_api_log.login_log_module', return_value='sales_order'):
                    after_request(request, response)
                    saved = get_doc.call_args.args[0]
                    self.assertEqual(saved['operation'], 'Login')
                    self.assertEqual(saved['user'], 'seller@example.com')
                    self.assertEqual(saved['status'], 'Success' if code == 200 else 'Failed')
                    self.assertNotIn('private-password', saved['request_json'])
                    self.assertNotIn('private-session', saved['response_json'])

    def test_nested_credentials_and_encoded_payload_are_redacted(self):
        payload = {'data': json.dumps({'customer': 'CUST-1', 'items': [{'item_code': 'ITEM-1', 'qty': 2}], 'password': 'private', 'otp': 'private', 'tmp_id': 'private', 'quick_pin_hash': 'private'}), 'api_secret': 'private'}
        clean = sanitize_payload(payload)
        self.assertEqual(clean['data']['items'][0]['qty'], 2)
        self.assertEqual(clean['data']['password'], '[REDACTED]')
        self.assertNotIn('private', json.dumps(clean))

    def test_hook_records_request_and_response_without_secrets(self):
        method = 'retail.api.pos_sync.save_sales_order'
        incoming = {'data': {'customer': 'CUST-1', 'items': [{'item_code': 'ITEM-1', 'qty': 2}]}}
        request = Request(EnvironBuilder(path='/api/method/' + method, method='POST', json=incoming).get_environ())
        response = Response(json.dumps({'message': {'name': 'SO-TEST'}, 'exc': 'private traceback'}), content_type='application/json')
        with patch.object(frappe.local, 'form_dict', incoming, create=True), patch.object(frappe.local, 'session', frappe._dict(user='Administrator'), create=True), patch.object(frappe, 'get_doc') as get_doc, patch.object(frappe, 'db', Mock()):
            after_request(request, response)
            saved = get_doc.call_args.args[0]
            self.assertEqual(json.loads(saved['request_json']), incoming)
            self.assertEqual(json.loads(saved['response_json'])['message']['name'], 'SO-TEST')
            self.assertNotIn('private traceback', saved['response_json'])
            get_doc.return_value.insert.assert_called_once_with(ignore_permissions=True)

    def test_readable_error_reasons_without_tracebacks(self):
        from retail.sales_order_api_log import response_issue
        cases = [
            ({'message': 'Incomplete login details', 'exc': 'private traceback'}, 401, 'Incomplete login details'),
            ({'_server_messages': json.dumps([json.dumps({'message': '<b>requestid</b> is required', 'raise_exception': 1})])}, 417, 'requestid is required'),
            ({'message': {'status': 'Failed', 'error': 'Van assignment missing'}}, 200, 'Van assignment missing'),
            ({'message': {'status': 'AuthenticationRequired', 'detail': 'Complete two-factor authentication.'}}, 200, 'Complete two-factor authentication.'),
            ({'exc': 'private traceback', 'exc_type': 'PermissionError'}, 403, 'PermissionError'),
            ({}, 502, 'HTTP 502'),
            ({'message': 'Logged In'}, 200, ''),
        ]
        for body, code, expected in cases:
            with self.subTest(body=body):
                self.assertEqual(response_issue(body, code), expected)
