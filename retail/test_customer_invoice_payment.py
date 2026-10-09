import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

import frappe
from retail.api import pos_sync


class TestCustomerInvoicePayment(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(frappe.local, "flags", frappe._dict(in_test=False), create=True))
        self.invoice = frappe._dict(name='INV-1', customer='Customer', company='Company', docstatus=1, outstanding_amount=100)
        self.counter = frappe._dict(branch='Branch', company='Company')
        replacements = {
            '_assert_pos_user': Mock(),
            '_existing_doc': Mock(return_value=None),
            '_counter': Mock(return_value=self.counter),
            '_assert_day_not_closed': Mock(),
            '_validate_active_counter_session': Mock(),
            '_business_date': Mock(return_value='2026-09-15'),
            '_run': Mock(side_effect=lambda kind, payload, handler: handler()),
            '_new_customer_payment': Mock(return_value=frappe._dict(name='PAY-1', docstatus=1)),
            '_': lambda text: text,
        }
        for name, value in replacements.items():
            self.stack.enter_context(patch.object(pos_sync, name, value))
        self.db = self.stack.enter_context(patch.object(frappe, 'db', Mock()))
        self.db.get_value.side_effect = lambda dt, filters, field: 'INV-1' if dt == 'Sales Invoice' else None
        self.stack.enter_context(patch.object(frappe, 'get_doc', return_value=self.invoice))
        self.stack.enter_context(patch.object(frappe, 'throw', side_effect=frappe.ValidationError))

    def pay(self, **kwargs):
        return pos_sync.pay_customer_invoice(dict(external_pos_reference='REF-1', invoice_name='INV-1', **kwargs))

    def test_endpoint_is_whitelisted(self):
        self.assertIn(pos_sync.pay_customer_invoice, frappe.whitelisted)
        self.assertNotIn(pos_sync.pay_customer_invoice, frappe.guest_methods)

    def test_partial_payment(self):
        result = self.pay(amount=25)
        self.assertEqual(result['invoice_outstanding_amount'], 75)
        self.assertEqual(result['allocated_amount'], 25)
        pos_sync._new_customer_payment.assert_called_once_with(
            unittest.mock.ANY, self.counter, 'Customer', 25, invoice=self.invoice)
        self.assertEqual(pos_sync._run.call_args.args[0], 'Payment Entry')
        pos_sync._assert_pos_user.assert_called_once()

    def test_invalid_payments_do_not_create_entries(self):
        for args in ({'amount': 0}, {'amount': -1}, {'amount': 101}, {'amount': 25, 'customer': 'Other'}):
            with self.subTest(args=args), self.assertRaises(frappe.ValidationError):
                self.pay(**args)
        self.invoice.docstatus = 0
        with self.assertRaises(frappe.ValidationError):
            self.pay(amount=25)
        pos_sync._new_customer_payment.assert_not_called()

    def test_duplicate_does_not_create_entry(self):
        pos_sync._existing_doc.return_value = frappe._dict(name='PAY-1', docstatus=1)
        self.assertEqual(self.pay(amount=25)['status'], 'Duplicate')
        pos_sync._new_customer_payment.assert_not_called()

    def test_external_invoice_reference(self):
        result = pos_sync.pay_customer_invoice(dict(external_pos_reference='REF-1',
            invoice_external_reference='SALE-1', amount=100))
        self.assertEqual(result['invoice_outstanding_amount'], 0)
        self.db.get_value.assert_any_call('Sales Invoice',
            {'external_pos_reference': 'SALE-1', 'docstatus': 1}, 'name')

    def test_pos_collection_returns_original_reference(self):
        from retail import pos_credit
        self.db.get_value.side_effect = lambda dt, filters, field: 'POS-1' if dt == 'POS Invoice' else None
        self.invoice.name = 'POS-1'
        accounting = frappe._dict(name='SI-1', docstatus=1, outstanding_amount=100)
        with patch.object(pos_credit, 'remaining_amount', return_value=100), patch.object(
            pos_credit, 'accounting_invoice', return_value=accounting
        ):
            result = self.pay(amount=25)
        self.assertEqual(result['invoice_name'], 'POS-1')
        self.assertEqual(result['sales_invoice'], 'SI-1')
        self.assertEqual(result['invoice_outstanding_amount'], 75)
        pos_sync._new_customer_payment.assert_called_once_with(unittest.mock.ANY,
            self.counter, 'Customer', 25, invoice=accounting, pos_invoice='POS-1')

    def test_pos_collection_respects_shared_accounting_balance(self):
        from retail import pos_credit
        self.db.get_value.side_effect = lambda dt, filters, field: 'POS-1' if dt == 'POS Invoice' else None
        with patch.object(pos_credit, 'remaining_amount', return_value=100), patch.object(
            pos_credit, 'accounting_invoice',
            return_value=frappe._dict(name='SI-1', docstatus=1, outstanding_amount=10)
        ), self.assertRaises(frappe.ValidationError):
            self.pay(amount=25)
        pos_sync._new_customer_payment.assert_not_called()

    def test_cross_company_invoice_is_rejected(self):
        self.invoice.company = 'Other Company'
        with self.assertRaises(frappe.ValidationError):
            self.pay(amount=25)
        pos_sync._new_customer_payment.assert_not_called()

    def test_ambiguous_name_requires_doctype(self):
        self.db.get_value.side_effect = None
        self.db.get_value.return_value = 'INV-1'
        with self.assertRaises(frappe.ValidationError):
            self.pay(amount=25)
        pos_sync._new_customer_payment.assert_not_called()

    def multi(self, **changes):
        payload = dict(external_pos_reference='REF-1', customer='Customer', amount=75,
            invoices=[dict(invoice_external_reference='SALE-1', invoice_doctype='Sales Invoice', allocated_amount=25),
                      dict(invoice_external_reference='SALE-2', invoice_doctype='Sales Invoice', allocated_amount=50)])
        payload.update(changes)
        self.db.get_value.side_effect = lambda dt, filters, field: filters['external_pos_reference']
        self.stack.enter_context(patch.object(frappe, 'get_doc', side_effect=lambda dt, name, **kw:
            frappe._dict(name=name, customer='Customer', company='Company', docstatus=1, outstanding_amount=100)))
        return pos_sync.pay_customer_invoice(payload)

    def test_multi_invoice_one_payment(self):
        result = self.multi()
        self.assertEqual(result['allocated_amount'], 75)
        self.assertEqual([r['invoice_outstanding_amount'] for r in result['invoices']], [75, 50])
        self.assertEqual([r['sales_invoice'] for r in result['invoices']], ['SALE-1', 'SALE-2'])
        pos_sync._new_customer_payment.assert_called_once_with(
            unittest.mock.ANY, self.counter, 'Customer', 75, allocations=result['invoices'])

    def test_multi_invalid_allocations_do_not_post(self):
        for changes in (
            {'amount': 80}, {'customer': 'Other'}, {'customer': ''},
            {'invoices': []}, {'invoices': 'SALE-1'}, {'invoices': [None]},
            {'invoice_external_reference': 'SALE-1'},
            {'invoices': [dict(invoice_external_reference='SALE-1', allocated_amount=101)]},
            {'invoices': [dict(invoice_external_reference='SALE-1', allocated_amount=25),
                          dict(invoice_external_reference='SALE-1', allocated_amount=50)]},
        ):
            with self.subTest(changes=changes), self.assertRaises(frappe.ValidationError):
                self.multi(**changes)
        pos_sync._new_customer_payment.assert_not_called()

    def test_multi_invalid_money_does_not_post(self):
        for value in (None, 0, -1, 'bad', 'NaN', 'Infinity', 0.001):
            with self.subTest(value=value), self.assertRaises(frappe.ValidationError):
                self.multi(amount=value)
            with self.subTest(allocation=value), self.assertRaises(frappe.ValidationError):
                self.multi(invoices=[dict(invoice_external_reference='SALE-1', allocated_amount=value)])
        pos_sync._new_customer_payment.assert_not_called()

    def test_multi_duplicate_accounting_invoice_does_not_post(self):
        from retail import pos_credit
        accounting = frappe._dict(name='SI-1', docstatus=1, outstanding_amount=100)
        with patch.object(pos_credit, 'remaining_amount', return_value=100), patch.object(
                pos_credit, 'accounting_invoice', return_value=accounting), self.assertRaises(frappe.ValidationError):
            self.multi(invoices=[dict(invoice_external_reference='POS-1', invoice_doctype='POS Invoice', allocated_amount=25),
                                 dict(invoice_external_reference='POS-2', invoice_doctype='POS Invoice', allocated_amount=50)])
        pos_sync._new_customer_payment.assert_not_called()


class TestCustomerPaymentAccountSetup(unittest.TestCase):
    def test_multiple_allocations_create_one_entry(self):
        doc = Mock()
        payload = frappe._dict(external_pos_reference='PAY-1', payment_mode='Cash')
        counter = frappe._dict(company='Company', cost_center='Main')
        allocations = [dict(sales_invoice='SI-1', allocated_amount=25), dict(sales_invoice='SI-2', allocated_amount=50)]
        with patch.object(pos_sync, '_payment_account', return_value='Cash'), patch.object(
                pos_sync, 'get_party_account', return_value='Debtors'), patch.object(frappe, 'new_doc', return_value=doc), \
                patch.object(pos_sync, '_set_pos_audit_fields'), patch.object(frappe.utils, 'today', return_value='2026-10-08'):
            pos_sync._new_customer_payment(payload, counter, 'Customer', 75, allocations=allocations)
        self.assertEqual(doc.paid_amount, 75)
        self.assertEqual(doc.received_amount, 75)
        self.assertEqual(doc.append.call_args_list, [
            unittest.mock.call('references', dict(reference_doctype='Sales Invoice', reference_name='SI-1', allocated_amount=25)),
            unittest.mock.call('references', dict(reference_doctype='Sales Invoice', reference_name='SI-2', allocated_amount=50))])
        doc.submit.assert_called_once()

    def test_customer_account_initialized_before_missing_values(self):
        from hrms.overrides.employee_payment_entry import EmployeePaymentEntry

        # Use HRMS's actual account setup on a minimal unsaved document.
        doc = Mock()
        del doc.party_account
        doc.paid_from_account_currency = 'AED'
        doc.setup_party_account_field.side_effect = lambda: EmployeePaymentEntry.setup_party_account_field(doc)

        def check_account():
            self.assertEqual(doc.party_account, 'Debtors')
            self.assertEqual(doc.party_account_field, 'paid_from')
            self.assertEqual(doc.party_account_currency, 'AED')

        doc.set_missing_values.side_effect = check_account
        payload = frappe._dict(external_pos_reference='PAY-1', posting_date='2026-09-15', payment_mode='CASH')
        counter = frappe._dict(company='Company', cost_center='Main')
        with patch.object(pos_sync, '_payment_account', return_value='Cash'), patch.object(
            pos_sync, 'get_party_account', return_value='Debtors'
        ), patch.object(frappe, 'new_doc', return_value=doc), patch.object(pos_sync, '_set_pos_audit_fields'):
            result = pos_sync._new_customer_payment(payload, counter, 'Customer', 25,
                invoice=frappe._dict(name='SI06'))
        self.assertIs(result, doc)
        doc.insert.assert_called_once_with(ignore_permissions=True)
        doc.submit.assert_called_once()
