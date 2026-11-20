import json
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from retail.sales_order_api_log import after_request, sanitize_payload


class TestSalesOrderAPILog(TestCase):
    def test_nested_credentials_and_encoded_payload_are_redacted(self):
        payload = {'data': json.dumps({'customer': 'CUST-1', 'items': [{'item_code': 'ITEM-1', 'qty': 2}], 'password': 'private'}), 'api_secret': 'private'}
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
