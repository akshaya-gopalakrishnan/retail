import unittest
from unittest.mock import patch
import frappe
from retail import customer_promotions as service

class TestCustomerPromotions(unittest.TestCase):
    def test_balance_and_preserved_credit(self):
        rows = [dict(name='C1', credit_limit=500), dict(name='C2')]
        def query(doctype, **kwargs):
            if doctype == 'Customer':
                return [frappe._dict(name='C1', loyalty_program='LP', loyalty_program_tier='Gold')]
            self.assertEqual(kwargs['filters']['company'], 'Company')
            if doctype == 'Loyalty Program':
                return [frappe._dict(name='LP', loyalty_program_name='Rewards', conversion_factor=0.5)]
            self.assertEqual(kwargs['filters']['customer'], ['in', ['C1', 'C2']])
            if doctype == 'Gift Voucher Ledger':
                return []
            return [frappe._dict(name=name, customer='C1', loyalty_program='LP', loyalty_points=points,
                redeem_against=against, posting_date='2026-01-01', expiry_date=expiry)
                for name, points, against, expiry in [('E1', 100, None, '2099-12-31'),
                    ('R1', -20, 'E1', None), ('E2', 10, None, '2026-01-31')]]
        with patch.object(frappe, 'get_all', side_effect=query), patch.object(frappe,
                'get_cached_value', return_value='AED'), patch.object(service, 'nowdate', return_value='2026-10-23'), patch('retail.loyalty.today', return_value='2026-10-23'):
            service.add_customer_promotions(rows, 'Company')
        self.assertEqual(rows[0]['credit_limit'], 500)
        balance = rows[0]['loyalty_balances'][0]
        self.assertEqual([balance[k] for k in ('earned_points', 'used_points', 'expired_points',
            'available_points', 'redeemable_amount')], [110, 20, 10, 80, 40])
        self.assertEqual(rows[1]['loyalty_balances'], [])
        self.assertEqual(rows[1]['gift_vouchers'], [])
        self.assertIsNone(rows[1]['loyalty_program'])

    def test_empty_list(self):
        with patch.object(frappe, 'get_all') as query:
            service.add_customer_promotions([], 'Company')
        query.assert_not_called()
