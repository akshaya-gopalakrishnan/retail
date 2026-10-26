import unittest
import frappe
from retail.loyalty_display import balances


class TestLoyaltyDisplay(unittest.TestCase):
    def test_redemption_restoration_and_expiry(self):
        root = frappe._dict(name='earned', loyalty_points=157, redeem_against=None,
                            expiry_date='2026-09-17', posting_date='2026-09-17')
        spent = frappe._dict(name='spent', loyalty_points=-10, redeem_against='earned',
                             expiry_date='2026-09-17', posting_date='2026-09-17')
        result = balances([root, spent], [spent], '2026-09-17')
        self.assertEqual(result['earned']['available_points'], 147)
        self.assertEqual(result['spent']['used_points'], 10)
        self.assertEqual(result['spent']['remaining_points'], 0)
        self.assertEqual(balances([root], [spent], '2026-09-18')['earned']['expired_points'], 147)
        spent.loyalty_points = -157
        self.assertEqual(balances([root], [spent], '2026-09-17')['earned']['remaining_points'], 0)
        restored = frappe._dict(redeem_against='earned', loyalty_points=10)
        result = balances([root], [spent, restored], '2026-09-17')['earned']
        self.assertEqual(result['remaining_points'], 10)
        self.assertEqual(result['used_points'], 147)
