import unittest
from unittest.mock import patch

import frappe

from retail.retail_app.doctype.customer_loyalty_balance import customer_loyalty_balance as balance


class TestCustomerLoyaltyBalance(unittest.TestCase):
    def rows(self):
        return [dict(company=company, customer=customer, customer_name=name,
            loyalty_program=program, earned_points=earned, used_points=used,
            expired_points=expired, available_points=available, as_of_date='2026-10-31')
            for company, customer, name, program, earned, used, expired, available in [
                ('Company', 'C-1', 'Alice', 'Rewards', 100, 20, 10, 70),
                ('Company', 'C-1', 'Alice', 'Older Rewards', 50, 10, 40, 0),
                ('Company', 'C-2', 'Bob', 'Rewards', 20, 0, 0, 20),
                ('Other', 'C-1', 'Alice', 'Rewards', 10, 0, 0, 10)]]

    def test_one_row_per_customer_company_with_name_and_separate_program_math(self):
        rows = balance.consolidate(self.rows())
        self.assertEqual(len(rows), 3)
        alice = next(row for row in rows if row.customer == 'C-1' and row.company == 'Company')
        self.assertEqual(alice.customer_name, 'Alice')
        self.assertEqual([alice[field] for field in balance.POINT_FIELDS], [150, 30, 50, 70])
        self.assertEqual(alice.loyalty_programs, 'Older Rewards, Rewards')
        self.assertNotIn('invoice', alice)
        self.assertEqual(balance.consolidate(self.rows())[0].name, rows[0].name)
        self.assertEqual(alice.name, '1')
        self.assertEqual([row.name for row in rows], ['1', '2', '3'])
        self.assertEqual(len({row.name for row in rows}), 3)
        self.assertNotIn('balance_id', alice)

    def test_invoice_points_consolidate_split_redemption_and_exclude_future(self):
        def entry(name, invoice, points, against=None, program='Rewards', date='2026-10-01', expiry='2027-10-01'):
            return frappe._dict(name=name, invoice_type='POS Invoice', invoice=invoice,
                loyalty_program=program, loyalty_points=points, redeem_against=against,
                posting_date=date, expiry_date=expiry)
        entries = [entry('earn1', 'POS-1', 100), entry('earn2', 'POS-1', 50, program='Other'),
            entry('spent1', 'POS-2', -10, 'earn1'), entry('spent2', 'POS-2', -20, 'earn1'),
            entry('restore', 'POS-3', 10, 'earn1'),
            entry('expired', 'POS-4', 20, expiry='2026-10-30'),
            entry('future', 'POS-5', 100, date='2026-11-01')]
        with patch('retail.loyalty.today', return_value='2026-10-31'):
            rows = balance.invoice_details(entries, '2026-10-31')
        self.assertEqual(len(rows), 4)
        invoices = {row.invoice: row for row in rows}
        self.assertEqual(invoices['POS-1'].earned_points, 150)
        self.assertEqual(invoices['POS-1'].available_points, 130)
        self.assertEqual(invoices['POS-2'].used_points, 30)
        self.assertEqual(invoices['POS-3'].used_points, -10)
        self.assertEqual(invoices['POS-4'].expired_points, 20)
        self.assertNotIn('POS-5', invoices)
        self.assertEqual([sum(row[field] for row in rows) for field in balance.POINT_FIELDS],
            [170, 20, 20, 130])

    def test_native_filters_sort_pagination_and_count(self):
        rows = self.rows()[:3]
        with patch.object(frappe, 'has_permission', return_value=True), \
                patch.object(frappe, 'get_list', return_value=['Company']), \
                patch('retail.customer_loyalty_names.names', return_value={('Company', 'C-1'): '1', ('Company', 'C-2'): '2'}), \
                patch.object(balance, 'get_summary', return_value=rows):
            args = dict(filters={'customer_name': ['like', '%Ali%']}, page_length=1,
                order_by='`tabCustomer Loyalty Balance`.`available_points` desc')
            result = balance.CustomerLoyaltyBalance.get_list(args)
            self.assertEqual([row.customer for row in result], ['C-1'])
            self.assertEqual(balance.CustomerLoyaltyBalance.get_count(args), 1)
            self.assertEqual(balance.CustomerLoyaltyBalance.get_list(dict(start=1, page_length=1))[0].customer, 'C-2')

    def test_numeric_names_do_not_change_when_other_customers_are_hidden(self):
        names = {('Company', 'C-1'): '1', ('Company', 'C-2'): '2', ('Other', 'C-1'): '3'}
        all_rows = balance.consolidate(self.rows(), names)
        only_bob = balance.consolidate([self.rows()[2]], names)
        self.assertEqual(only_bob[0].name, '2')
        self.assertEqual(next(row.name for row in all_rows if row.customer == 'C-2'), '2')

    def test_denied_ledger_permission_does_not_read_data(self):
        with patch.object(frappe, 'has_permission', side_effect=frappe.PermissionError), \
                patch.object(balance, 'get_summary') as query:
            with self.assertRaises(frappe.PermissionError):
                balance.CustomerLoyaltyBalance.get_list({})
            query.assert_not_called()
