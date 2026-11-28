"""Document-local lookup reuse must preserve row margins and fresh prices."""
import unittest
from unittest.mock import Mock, patch

import frappe
from retail.domains.purchase import selling_price


class Row(frappe._dict):
    def set(self, key, value):
        self[key] = value

    def precision(self, field):
        return 2


class TestPurchaseMarginLookups(unittest.TestCase):
    def document(self):
        rows = [Row(item_code='SKU', uom=uom, rate=5,
                    meta=Mock(has_field=Mock(return_value=True)))
                for uom in ('Nos', 'Nos', 'Box')]
        return frappe._dict(doctype='Purchase Invoice', custom_allow_selling_price=1, items=rows)

    def test_duplicate_rows_keep_native_values_and_separate_uoms(self):
        with patch.object(selling_price, 'get_standard_selling_rate', side_effect=lambda item, uom: 10 if uom == 'Nos' else 20) as read, \
                patch.object(selling_price, 'get_item_selling_vat_rate', return_value=5), \
                patch.object(frappe, 'get_system_settings', return_value="Banker's Rounding"):
            doc = self.document()
            selling_price.set_selling_price_margins(doc)
            self.assertEqual(read.call_count, 2)
            self.assertEqual([(r.custom_cur_sell_rate, r.custom_new_sell_incl, r.custom_sell_margin)
                              for r in doc.get('items')], [(10, 10.5, 5), (10, 10.5, 5), (20, 21, 15)])
            read.reset_mock()
            read.side_effect = lambda item, uom: 30
            next_doc = self.document()
            selling_price.set_selling_price_margins(next_doc)
            self.assertEqual(read.call_count, 2)
            self.assertEqual(next_doc.get('items')[0].custom_cur_sell_rate, 30)

    def test_zero_lookup_is_reused_without_creating_a_selling_rate(self):
        with patch.object(selling_price, 'get_standard_selling_rate', return_value=0) as read, \
                patch.object(frappe, 'get_system_settings', return_value="Banker's Rounding"):
            doc = self.document()
            selling_price.set_selling_price_margins(doc)
            self.assertEqual(read.call_count, 2)
            self.assertTrue(all(not r.custom_cur_sell_rate and r.custom_new_sell_incl == 0
                                for r in doc.get('items')))
