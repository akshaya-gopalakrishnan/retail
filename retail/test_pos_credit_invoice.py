import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

import frappe
from retail.api import pos_sync


class TestPOSCreditInvoice(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(frappe.local, 'flags', frappe._dict(in_test=False), create=True))
        self.counter = frappe._dict(branch='Branch', company='Company', pos_profile='Profile')
        self.doc = Mock()
        self.doc.name = 'POS-1'
        self.doc.docstatus = 1
        self.doc.grand_total = 100
        self.doc.rounded_total = 100
        self.doc.write_off_amount = 0
        self.doc.posting_date = '2026-09-15'
        self.doc.payments = [frappe._dict(amount=100, base_amount=100)]
        self.doc.precision.return_value = 2
        for name, value in {
            '_assert_pos_user': Mock(), '_existing_invoice': Mock(return_value=None),
            '_counter': Mock(return_value=self.counter), '_assert_day_not_closed': Mock(),
            '_business_date': Mock(), '_base_invoice': Mock(return_value=self.doc),
            '_set_profile_taxes': Mock(), '_append_invoice_items': Mock(),
            '_validate_vat': Mock(), '_validate_credit_customer': Mock(),
            'create_for_pos_invoice': Mock(return_value=[]),
            'get_due_date': Mock(return_value='2026-10-15'),
            '_run': Mock(side_effect=lambda kind, payload, handler: handler()),
            '_': lambda text: text,
        }.items():
            self.stack.enter_context(patch.object(pos_sync, name, value))
        self.db = self.stack.enter_context(patch.object(frappe, 'db', Mock()))
        self.db.get_value.return_value = 1
        self.stack.enter_context(patch('retail.promotions.pos_gift_voucher.issued_for', return_value=[]))
        self.stack.enter_context(patch.object(frappe, 'get_system_settings', return_value="Banker's Rounding"))
        self.stack.enter_context(patch.object(frappe, 'throw', side_effect=frappe.ValidationError))
        self.payload = dict(customer='Customer', external_pos_reference='CREDIT-1')

    def test_credit_sale_is_unpaid_pos_invoice(self):
        result = pos_sync.create_credit_pos_invoice(self.payload)
        self.assertEqual(result['doctype'], 'POS Invoice')
        self.assertEqual(result['pos_invoice_name'], 'POS-1')
        self.assertEqual(result['outstanding_amount'], 100)
        self.assertEqual(self.doc.due_date, '2026-10-15')
        self.assertEqual(self.doc.paid_amount, 0)
        self.assertEqual(self.doc.payments[0].amount, 0)
        self.doc.submit.assert_called_once()
        pos_sync._validate_credit_customer.assert_called_once_with('Customer', 'Company', 100)

    def test_profile_must_allow_credit(self):
        self.db.get_value.return_value = 0
        with self.assertRaises(frappe.ValidationError):
            pos_sync.create_credit_pos_invoice(self.payload)
        self.doc.submit.assert_not_called()

    def test_credit_endpoint_rejects_initial_payment(self):
        with self.assertRaises(frappe.ValidationError):
            pos_sync.create_credit_pos_invoice(dict(self.payload, payments=[dict(amount=10)]))
        self.doc.submit.assert_not_called()

    def test_generic_endpoint_routes_unpaid_sale(self):
        with patch.object(pos_sync, 'create_credit_pos_invoice', return_value={'status': 'Success'}) as credit:
            pos_sync.create_pos_invoice(self.payload)
        credit.assert_called_once_with(self.payload)

    def test_retry_preserves_existing_invoice(self):
        pos_sync._existing_invoice.return_value = frappe._dict(
            name='SI06', doctype='Sales Invoice', docstatus=1, grand_total=100, outstanding_amount=100)
        result = pos_sync.create_credit_pos_invoice(self.payload)
        self.assertEqual(result['status'], 'Duplicate')
        self.assertEqual(result['invoice_name'], 'SI06')
        self.doc.insert.assert_not_called()
