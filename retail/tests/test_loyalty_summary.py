import unittest
from unittest.mock import patch

import frappe

from retail.loyalty_summary import summarize, get_summary


class TestLoyaltySummary(unittest.TestCase):
    def entry(self, name, points, **values):
        row = frappe._dict(name=name, company='Company', customer='C-1', loyalty_program='Rewards',
            loyalty_points=points, posting_date='2026-10-01', expiry_date='2026-12-31',
            redeem_against=None, invoice_type='POS Invoice')
        row.update(values)
        return row

    def test_multiple_invoices_combine_but_customer_and_program_remain_separate(self):
        rows = [self.entry('sale1', 100), self.entry('sale2', 50),
            self.entry('redeem', -30, redeem_against='sale1'),
            self.entry('restore', 10, redeem_against='sale1'),
            self.entry('expired', 200, expiry_date='2026-10-29'),
            self.entry('future', 500, posting_date='2026-10-31'),
            self.entry('other-customer', 20, customer='C-2'),
            self.entry('other-program', 40, loyalty_program='Other')]
        with patch('retail.loyalty.today', return_value='2026-10-30'):
            result = summarize(rows, '2026-10-30')
        self.assertEqual(len(result), 3)
        balance = next(row for row in result if row['customer'] == 'C-1' and row['loyalty_program'] == 'Rewards')
        self.assertEqual((balance['earned_points'], balance['used_points'],
            balance['expired_points'], balance['available_points']), (350, 20, 200, 130))
        self.assertNotIn('invoice', balance)
        self.assertEqual(rows[0].loyalty_points, 100)

    def test_permission_failure_does_not_read_entries(self):
        with patch.object(frappe, 'has_permission', side_effect=frappe.PermissionError), \
                patch.object(frappe, 'get_list') as query:
            with self.assertRaises(frappe.PermissionError):
                get_summary('Company')
        query.assert_not_called()
