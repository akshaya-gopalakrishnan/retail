import unittest
from unittest.mock import patch

import frappe
from retail import loyalty_enrollment as enrollment


class TestLoyaltyEnrollment(unittest.TestCase):
    def test_newest_eligible_program_and_sale_date(self):
        customer = frappe._dict(loyalty_program=None, customer_group='Retail', territory='Dubai')
        programs = [frappe._dict(name=name, from_date=start, to_date=end, auto_opt_in=auto,
            customer_group=group, customer_territory=territory)
            for name, start, end, auto, group, territory in [
                ('future', '2027-01-01', None, 1, None, None),
                ('manual', '2026-10-31', None, 0, None, None),
                ('other-group', '2026-10-31', None, 1, 'Wholesale', None),
                ('expired', '2026-10-30', '2026-10-30', 1, None, None),
                ('latest', '2026-10-01', None, 1, 'Retail', 'Dubai'),
                ('older', '2026-01-01', None, 1, None, None)]]
        with patch.object(enrollment, 'matches_tree', side_effect=lambda dt, group, actual: not group or group == actual):
            self.assertEqual(enrollment.select_program(customer, programs, '2026-10-31'), 'latest')
            self.assertEqual(enrollment.select_program(customer, programs, '2026-09-30'), 'older')
            customer.disabled = 1
            self.assertIsNone(enrollment.select_program(customer, programs, '2026-10-31'))

    def test_nested_group_and_territory_eligibility(self):
        for dt in ('Customer Group', 'Territory'):
            with patch.object(frappe, 'get_cached_value', side_effect=[
                    frappe._dict(lft=1, rgt=10), frappe._dict(lft=2, rgt=3)]):
                self.assertTrue(enrollment.matches_tree(dt, 'Parent', 'Child'))
            with patch.object(frappe, 'get_cached_value', side_effect=[
                    frappe._dict(lft=1, rgt=4), frappe._dict(lft=5, rgt=6)]):
                self.assertFalse(enrollment.matches_tree(dt, 'Parent', 'Unrelated'))
