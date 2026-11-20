"""Database-free regressions complement the disposable posting/ledger checks."""
import json
import unittest
from unittest.mock import patch

import frappe
from retail.product_conversion import finalize_stock_entry, restore_master_costs
from retail.tests import test_repack as helpers


class TestProductConversionCosts(unittest.TestCase):
    setUp = helpers.TestRepackCosts.setUp
    calculate = helpers.TestRepackCosts.calculate
    def test_conversion_json_uses_the_same_native_group_allocator(self):
        doc = helpers.entry()
        doc.custom_multiple_boms = 0
        doc.custom_product_conversion = 'PC-TEST'
        doc.custom_conversion_groups = json.dumps([
            dict(idx=r.idx, finished_item=r.finished_item, qty=r.qty, bom_no=r.bom_no)
            for r in doc.custom_repack_boms
        ])
        doc.custom_repack_boms = []
        self.calculate(doc)
        self.assertEqual(doc.total_incoming_value,57.5)
        self.assertEqual(doc.items[1].valuation_rate,2.25)
        self.assertEqual(doc.items[3].valuation_rate,1.75)

    def test_conversion_finalizer_restores_stock_amounts_after_display_hooks(self):
        doc = helpers.entry()
        self.calculate(doc)
        doc.custom_product_conversion = 'PC-TEST'
        for row in doc.items:
            row.amount = 0
        finalize_stock_entry(doc)
        self.assertEqual(doc.total_incoming_value,57.5)
        self.assertEqual(doc.total_outgoing_value,50)
        doc.custom_product_conversion = None
        doc.items[1].amount = 123
        finalize_stock_entry(doc)
        self.assertEqual(doc.items[1].amount,123)

    def test_cancel_does_not_overwrite_a_later_item_master_edit(self):
        from unittest.mock import MagicMock
        item = MagicMock(name='Item')
        item.modified = '2026-11-19 15:00:00'
        doc = frappe._dict(master_cost_updates=json.dumps([
            dict(item_code='Pack A', updated_modified='2026-11-19 14:00:00', before={'custom_purchase_rate_entry':7})
        ]))
        with patch.object(frappe,'get_doc',return_value=item), patch.object(frappe,'msgprint'), patch('retail.product_conversion._',side_effect=lambda x:x):
            restore_master_costs(doc)
        item.save.assert_not_called()
        item.update.assert_not_called()

    def test_shared_fifo_material_consumes_successive_layers(self):
        doc = helpers.entry()
        doc.custom_multiple_boms = 0
        doc.custom_product_conversion = 'PC-TEST'
        doc.custom_conversion_groups = json.dumps([
            dict(idx=r.idx, finished_item=r.finished_item, qty=r.qty, bom_no=r.bom_no)
            for r in doc.custom_repack_boms
        ])
        doc.posting_date='2026-11-19'
        doc.posting_time='10:00:00'
        doc.company='Company'
        doc.name=None
        # Two units cost 10 each; the next three cost 20 each. Native's
        # cumulative FIFO quote for five units is therefore 16 per unit.
        with patch('erpnext.stock.utils.get_incoming_rate',return_value=16) as rate:
            self.calculate(doc,reset=True)
        self.assertEqual(doc.items[0].basic_amount,20)
        self.assertEqual(doc.items[2].basic_amount,60)
        self.assertEqual(doc.items[3].valuation_rate,3.25)
        self.assertEqual(rate.call_args.args[0].qty,-5)
