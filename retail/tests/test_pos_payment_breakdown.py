import unittest
from unittest.mock import Mock, patch

import frappe
from retail.pos_payment_breakdown import onload


class TestPaymentBreakdown(unittest.TestCase):
    def document(self, doctype):
        doc = Mock(doctype=doctype, company='Company', customer='Customer')
        doc.name = 'INV-1'
        doc.get.return_value = 'SALE-1'
        return doc

    def test_both_invoice_types_and_credit_references(self):
        for doctype in ('POS Invoice', 'Sales Invoice'):
            with self.subTest(doctype=doctype), patch('retail.pos_payment_breakdown.frappe.get_all') as query:
                query.side_effect = [['TX-1'], [frappe._dict(
                    settlement_type=typ, requested_amount=4, applied_amount=3,
                    unresolved_amount=1, source_external_reference='RETURN-1',
                    external_pos_reference='SALE-1', status='Pending Reconciliation',
                ) for typ in ('Credit Note Redeemed', 'Credit Note Issued')]]
                doc = self.document(doctype)
                onload(doc)
                doc.check_permission.assert_called_once_with('read')
                filters = query.call_args_list[0].kwargs['filters']
                self.assertEqual(filters['company'], 'Company')
                self.assertEqual(filters['customer'], 'Customer')
                self.assertEqual(filters.get('sales_invoice') if doctype == 'Sales Invoice'
                                 else filters.get('external_pos_reference'),
                                 'INV-1' if doctype == 'Sales Invoice' else 'SALE-1')
                rows = doc.set_onload.call_args.args[1]
                self.assertEqual([r['reference_no'] for r in rows], ['RETURN-1', 'SALE-1'])
                self.assertEqual(rows[0]['unresolved_amount'], 1)
                self.assertNotIn('Cash Refund', query.call_args.kwargs['filters']['settlement_type'][1])

    def test_permission_failure_prevents_queries(self):
        doc = self.document('Sales Invoice')
        doc.check_permission.side_effect = frappe.PermissionError
        with patch('retail.pos_payment_breakdown.frappe.get_all') as query:
            with self.assertRaises(frappe.PermissionError):
                onload(doc)
            query.assert_not_called()

    def test_no_acceptance_has_no_settlement_rows(self):
        with patch('retail.pos_payment_breakdown.frappe.get_all', return_value=[]) as query:
            doc = self.document('Sales Invoice')
            onload(doc)
            self.assertEqual(query.call_count, 1)
            doc.set_onload.assert_called_once_with('retail_payment_settlements', [])
