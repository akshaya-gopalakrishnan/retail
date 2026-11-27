"""Read-only endpoint tests: no site initialization or business records."""
import unittest
from unittest.mock import patch

import frappe
from retail import van_stock


class VanStockViewTests(unittest.TestCase):
    def test_ledger_in_out_returns_and_zero_qty_revaluation(self):
        movements = [frappe._dict(actual_qty=q, stock_value_difference=v)
                     for q, v in [(10, 90), (-2, -18), (1, 9), (0, 5)]]
        wh = frappe._dict(company='Company')
        wh.check_permission = lambda permission: None
        with patch.object(van_stock, '_validate_van_stock_view_permission'), \
             patch.object(van_stock, '_get_van_stock_view_vans', return_value=[frappe._dict(van_warehouse='Van WH')]), \
             patch.object(frappe, 'get_doc', return_value=wh), \
             patch.object(frappe, 'get_cached_value', return_value='AED'), \
             patch.object(frappe.db, 'sql', return_value=movements):
            result = van_stock.get_van_stock_ledger('Van', posting_date='2026-11-26')
        load, sale, returned, adjustment = result['rows']
        self.assertEqual((load.in_qty, load.in_rate, load.in_value), (10, 9, 90))
        self.assertEqual((sale.out_qty, sale.out_rate, sale.out_value), (2, 9, 18))
        self.assertEqual((returned.in_qty, returned.in_value), (1, 9))
        self.assertEqual((adjustment.in_qty, adjustment.out_qty, adjustment.value_adjustment), (0, 0, 5))

    def test_summary_one_row_per_van_including_zero_stock(self):
        vans = [frappe._dict(name=n, vehicle_name=n, van_warehouse=n) for n in ['V1', 'V2']]
        wh = frappe._dict(name='WH', company='Company')
        replies = [[frappe._dict(qty=10, stock_value=120)], [frappe._dict(qty=3)],
                   [frappe._dict(qty=0, stock_value=0)], [frappe._dict(qty=0)]]
        with patch.object(van_stock, '_validate_van_stock_view_permission'), \
             patch.object(van_stock, '_get_van_stock_view_vans', return_value=vans), \
             patch.object(frappe, 'get_doc', return_value=wh), \
             patch.object(frappe, 'has_permission', return_value=True), \
             patch.object(frappe, 'get_cached_value', return_value='AED'), \
             patch.object(frappe.db, 'sql', side_effect=replies):
            result = van_stock.get_van_stock_summary(posting_date='2026-11-26')
        self.assertEqual(len(result['rows']), 2)
        self.assertEqual(result['rows'][0]['valuation_rate'], 12)
        self.assertEqual(result['rows'][0]['sold_qty'], 3)
        self.assertIsNone(result['rows'][1]['valuation_rate'])
        self.assertNotIn('item_code', result['rows'][0])


if __name__ == '__main__':
    # Provide a stub database object only; no connection is opened.
    from types import SimpleNamespace
    frappe.local.flags = frappe._dict(in_test=False)
    frappe.local.db = SimpleNamespace(sql=lambda *a, **k: None)
    unittest.main()
