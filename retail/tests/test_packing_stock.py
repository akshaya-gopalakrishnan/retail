import unittest
from unittest.mock import MagicMock, patch

import frappe

from retail.packing_stock import SOURCES, apply_packing_stock, get_packing_movements


def packing(uom='Box-10', factor=10, stock=100):
    return frappe._dict(item_code='A', stock_uom='Nos', uom=uom,
                        conversion_factor=factor, real_stock_qty=stock, in_qty=100, out_qty=0)


def movement(uom='Box-10', factor=10, incoming=100, outgoing=0, warehouse='Stores'):
    return frappe._dict(item_code='A', warehouse=warehouse, uom=uom, factor=factor,
                        in_stock_qty=incoming, out_stock_qty=outgoing)


class TestPackingStock(unittest.TestCase):
    def test_saved_packing_counts_and_alternate_barcodes_share_balance(self):
        rows = [packing(stock=80), packing(stock=80)]
        apply_packing_stock(rows, [movement(incoming=100, outgoing=20)])
        for row in rows:
            self.assertEqual((row.packing_in_qty, row.packing_out_qty, row.packing_stock_qty), (10, 2, 8))
            self.assertTrue(row.packing_balance_known)

    def test_loose_sales_do_not_invent_which_box_was_opened(self):
        rows = [packing(stock=99)]
        apply_packing_stock(rows, [movement(), movement('Nos', 1, 0, 1)])
        self.assertEqual(rows[0].packing_recorded_balance, 10)
        self.assertIsNone(rows[0].packing_stock_qty)
        self.assertEqual(rows[0].packing_in_qty, 10)

    def test_changed_conversion_unknown_adjustment_and_bin_mismatch(self):
        for moves in ([movement(factor=20)], [movement('', 0)], [movement(incoming=90)]):
            with self.subTest(moves=moves):
                row = packing()
                apply_packing_stock([row], moves)
                self.assertIsNone(row.packing_stock_qty)

    def test_transfer_both_legs_and_returns_use_ledger_sign(self):
        row = packing(stock=90)
        apply_packing_stock([row], [movement(incoming=100, outgoing=40),
                                   movement(incoming=40, outgoing=10, warehouse='Van')])
        self.assertEqual((row.packing_in_qty, row.packing_out_qty, row.packing_stock_qty), (14, 5, 9))

    def test_loose_receipt_does_not_manufacture_boxes(self):
        row = packing(stock=105)
        apply_packing_stock([row], [movement(), movement('Nos', 1, 5, 0)])
        self.assertEqual(row.packing_stock_qty, 10)
        self.assertEqual(row.packing_in_qty, 10)

    def test_negative_packing_warehouse_balance_is_unknown(self):
        row = packing(stock=100)
        apply_packing_stock([row], [movement(incoming=200),
                                   movement(incoming=0, outgoing=100, warehouse='Van')])
        self.assertIsNone(row.packing_stock_qty)

    def test_query_is_bounded_and_anchored_to_non_cancelled_ledger(self):
        with patch.object(frappe, 'db', MagicMock()) as db:
            get_packing_movements(['A', 'A', 'B'])
            db.sql.assert_called_once()
            query, args = db.sql.call_args.args
            self.assertEqual(args['item_codes'], ('A', 'B'))
            self.assertIn('sle.item_code in %(item_codes)s', query)
            self.assertIn('sle.is_cancelled = 0', query)
            self.assertIn('sle.actual_qty', query)
            for voucher, child in SOURCES:
                self.assertIn(f'`tab{child}`', query)
                self.assertIn(f"sle.voucher_type = '{voucher}'", query)
            db.sql.reset_mock()
            self.assertEqual(get_packing_movements([]), [])
            db.sql.assert_not_called()
