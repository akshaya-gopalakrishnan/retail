import unittest
from unittest.mock import patch

import frappe
from retail.api import pos_sync


class TestPOSSellingPrices(unittest.TestCase):
    def setUp(self):
        rounding = patch.object(frappe, 'get_system_settings', return_value="Banker's Rounding")
        rounding.start()
        self.addCleanup(rounding.stop)

    def test_customer_prices_include_vat_for_both_entry_modes(self):
        for inclusive, gross in ((1, 5), (0, 5.25), (0, 0)):
            item = frappe._dict(stock_uom='Nos', custom_sales_gross_rate=gross,
                                custom_sales_rate_includes_vat=inclusive)
            self.assertEqual(pos_sync._pos_selling_price(item, 'Nos'), gross)

    def test_packing_uses_its_own_gross_price_and_barcode(self):
        item = frappe._dict(stock_uom='Nos', custom_sales_gross_rate=5,
            custom_retail_packing_detail=[
                frappe._dict(uom='Box', barcode='A', selling_gross_rate=30),
                frappe._dict(uom='Box', barcode='B', selling_gross_rate=50)])
        self.assertEqual(pos_sync._pos_selling_price(item, 'Box', 'B'), 50)

    def test_incremental_price_rows_use_parent_even_if_not_in_item_delta(self):
        rows = [frappe._dict(item_code='ITEM', selling=1, price_list_rate=4.76, uom='Nos'),
                frappe._dict(item_code='ITEM', selling=0, price_list_rate=1.90, uom='Nos')]
        item = frappe._dict(name='ITEM', stock_uom='Nos', custom_sales_gross_rate=5)
        with patch.object(frappe, 'get_all', side_effect=[rows, [item]]) as query:
            result = pos_sync._pos_item_prices(['price_list_rate'], [['modified', '>', '2026-09-17']], ['CHANGED'])
        self.assertEqual(result[0].price_list_rate, 5)
        self.assertEqual(result[0].rate_includes_vat, 1)
        self.assertEqual(result[1].price_list_rate, 1.90)
        self.assertNotIn('rate_includes_vat', result[1])
        self.assertIn(['item_code', 'in', ['CHANGED']], query.call_args_list[0].kwargs['or_filters'])

    def test_packing_export_is_inclusive(self):
        packing = frappe._dict(item_code='ITEM', selling_rate=5, selling_gross_rate=5.25)
        pos_sync._apply_packing_tax_fields(packing, {})
        self.assertEqual(packing.selling_rate, 5.25)
        self.assertEqual(packing.rate_includes_vat, 1)

    def test_bulk_prices_preserve_packing_selection_and_fallbacks(self):
        rows = [frappe._dict(item_code='I', selling=1, uom=uom, barcode=barcode, price_list_rate=rate)
                for uom, barcode, rate in [('Nos', None, 99), ('Box', 'B', 99),
                    ('Box', 'missing', 99), ('Case', None, 10), ('Crate', None, 20)]]
        rows.append(frappe._dict(item_code='I', selling=0, uom='Nos', price_list_rate=2))
        item = frappe._dict(name='I', stock_uom='Nos', custom_sales_gross_rate=None,
                           standard_rate=4.76, custom_tax='VAT5')
        packings = [frappe._dict(parent='I', uom='Box', barcode='A', selling_gross_rate=30),
                    frappe._dict(parent='I', uom='Box', barcode='B', selling_gross_rate=0),
                    frappe._dict(parent='I', uom='Case', barcode='C', selling_gross_rate=None)]
        with patch.object(frappe, 'get_all', side_effect=[rows, [item], packings]) as query, patch.object(
            frappe, 'get_cached_doc', side_effect=AssertionError('per-item document read')
        ), patch.object(pos_sync, 'get_item_tax_rate', return_value=5) as tax:
            result = pos_sync._pos_item_prices(['price_list_rate'], [], [], ['I'])
        self.assertEqual([row.price_list_rate for row in result], [5, 0, 30, 10.5, 21, 2])
        self.assertTrue(all(row.rate_includes_vat == 1 for row in result[:-1]))
        self.assertNotIn('rate_includes_vat', result[-1])
        self.assertTrue(all('selling' not in row for row in result))
        self.assertEqual(query.call_count, 3)
        tax.assert_called_once_with('VAT5')

    def test_large_price_list_uses_bounded_reads(self):
        rows = [frappe._dict(item_code=f'I-{i}', selling=1, uom='Nos', price_list_rate=4)
                for i in range(1000)]
        items = [frappe._dict(name=row.item_code, stock_uom='Nos', custom_sales_gross_rate=5)
                 for row in rows]
        with patch.object(frappe, 'get_all', side_effect=[rows, items]) as query, patch.object(
            frappe, 'get_cached_doc', side_effect=AssertionError('per-item document read')
        ):
            result = pos_sync._pos_item_prices(['price_list_rate'], [], [])
        self.assertEqual(query.call_count, 2)
        self.assertTrue(all(row.price_list_rate == 5 for row in result))

    def test_purchase_only_prices_do_not_load_item_documents(self):
        rows = [frappe._dict(item_code='I', selling=0, price_list_rate=2)]
        with patch.object(frappe, 'get_all', return_value=rows) as query:
            result = pos_sync._pos_item_prices(['price_list_rate'], [], [])
        self.assertEqual(query.call_count, 1)
        self.assertEqual(result, [dict(item_code='I', price_list_rate=2)])
