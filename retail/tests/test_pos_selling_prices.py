import unittest
from unittest.mock import patch

import frappe
from retail.api import pos_sync


class TestPOSSellingPrices(unittest.TestCase):
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
        item = frappe._dict(stock_uom='Nos', custom_sales_gross_rate=5)
        with patch.object(frappe, 'get_all', return_value=rows) as query, patch.object(
            frappe, 'get_cached_doc', return_value=item
        ):
            result = pos_sync._pos_item_prices(['price_list_rate'], [['modified', '>', '2026-09-17']], ['CHANGED'])
        self.assertEqual(result[0].price_list_rate, 5)
        self.assertEqual(result[0].rate_includes_vat, 1)
        self.assertEqual(result[1].price_list_rate, 1.90)
        self.assertNotIn('rate_includes_vat', result[1])
        self.assertIn(['item_code', 'in', ['CHANGED']], query.call_args.kwargs['or_filters'])

    def test_packing_export_is_inclusive(self):
        packing = frappe._dict(item_code='ITEM', selling_rate=5, selling_gross_rate=5.25)
        pos_sync._apply_packing_tax_fields(packing, {})
        self.assertEqual(packing.selling_rate, 5.25)
        self.assertEqual(packing.rate_includes_vat, 1)
