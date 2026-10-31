import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from erpnext.controllers.taxes_and_totals import get_itemised_taxable_amount
from retail.pos_tax_breakup import update


class TestPOSTaxBreakup(unittest.TestCase):
    def test_sale_quantity_discount_and_return_use_final_net_amount(self):
        cases = [
            (1, 3.81, .19, 3.81),
            (2, 7.62, .38, 7.62),
            (-1, -3.81, -.19, -3.81),
            (2, 6.00, .30, 6.00),
        ]
        for qty, net, vat, expected in cases:
            with self.subTest(qty=qty, net=net):
                original = SimpleNamespace(is_return=int(qty < 0), conversion_rate=1,
                    items=[frappe._dict(item_code='ITEM', qty=qty, rate=3.81,
                                       net_amount=net, custom_vat_amount=vat)],
                    taxes=[frappe._dict(base_tax_amount=vat,
                        item_wise_tax_detail=json.dumps({'ITEM': [0, abs(vat)]}))])
                display = copy.deepcopy(original)
                doc = Mock()
                doc.as_dict.return_value = original
                with patch('retail.pos_completed_sale.payload_for', return_value={'items': [{}]}), \
                     patch('retail.pos_tax_breakup.frappe.get_doc', return_value=display), \
                     patch('erpnext.controllers.taxes_and_totals.get_itemised_tax_breakup_html', return_value='HTML') as render:
                    update(doc)
                rendered = render.call_args.args[0]
                self.assertEqual(get_itemised_taxable_amount(rendered.items)['ITEM'], expected)
                self.assertAlmostEqual(json.loads(rendered.taxes[0].item_wise_tax_detail)['ITEM'][1], vat)
                self.assertEqual(rendered.is_return, 0)  # Bypass template absolute-value formatting only.
                self.assertEqual(original.is_return, int(qty < 0))
                self.assertEqual(json.loads(original.taxes[0].item_wise_tax_detail)['ITEM'][1], abs(vat))
                self.assertEqual(doc.other_charges_calculation, 'HTML')

    def test_regular_invoice_is_not_changed(self):
        doc = Mock()
        with patch('retail.pos_completed_sale.payload_for', return_value={}), \
             patch('retail.pos_tax_breakup.frappe.get_doc') as clone:
            update(doc)
            clone.assert_not_called()

    def test_multiple_tax_accounts_keep_separate_amounts_and_source_rows(self):
        display = SimpleNamespace(is_return=1, conversion_rate=2,
            items=[frappe._dict(item_code='ITEM', net_amount=-10, custom_vat_amount=-.5)],
            taxes=[frappe._dict(base_tax_amount=amount,
                   item_wise_tax_detail=json.dumps({'ITEM': [rate, abs(amount)]}))
                   for rate, amount in [(5, -1), (2, -.4)]])
        doc = Mock()
        with patch('retail.pos_completed_sale.payload_for', return_value={'items': [{}]}), \
             patch('retail.pos_tax_breakup.frappe.get_doc', return_value=display), \
             patch('erpnext.controllers.taxes_and_totals.get_itemised_tax_breakup_html'):
            update(doc)
        for tax, expected in zip(display.taxes, [-1, -.4]):
            self.assertAlmostEqual(json.loads(tax.item_wise_tax_detail)['ITEM'][1], expected)
