import unittest
from unittest.mock import patch

import frappe
from retail.domains.item import vat_pricing


class PackingRow(dict):
    def set(self, key, value):
        self[key] = value


class TestPackingVat(unittest.TestCase):
    def test_saved_breakdown_uses_template_instead_of_stale_row_percentage(self):
        for side, template_field in [('purchase', 'custom_purchase_tax_template'), ('selling', 'custom_tax')]:
            for rate, stored_rate in [(5, 0), (5, 15), (0, 5)]:
                for mode, entry in [('Including VAT', 105), ('Excluding VAT', 100)]:
                    with self.subTest(side=side, rate=rate, stored_rate=stored_rate, mode=mode), patch.object(
                        vat_pricing, 'get_item_tax_rate', return_value=rate
                    ), patch.object(frappe, 'get_system_settings', return_value="Banker's Rounding"):
                        row = PackingRow({f'{side}_rate': entry, f'{side}_vat_rate': stored_rate,
                                          f'{side}_vat_mode': mode})
                        vat_pricing._apply_packing_direction({template_field: 'Template'}, row, side)
                        self.assertEqual(row[f'{side}_vat_rate'], rate)
                        self.assertEqual(row[f'{side}_net_rate'], 100 if rate else entry)
                        self.assertEqual(row[f'{side}_gross_rate'], 105 if rate else entry)

    def test_empty_packing_selling_rate_defaults_using_factor_and_vat(self):
        with patch.object(vat_pricing, 'get_item_tax_rate', return_value=5), patch.object(
            frappe, 'get_system_settings', return_value="Banker's Rounding"
        ):
            doc = {'custom_sales_net_rate': 100, 'custom_sales_rate_includes_vat': 1, 'custom_tax': 'VAT'}
            row = PackingRow(selling_rate=0, conversion_factor=12)
            vat_pricing._set_missing_packing_selling_rate_from_item(doc, row)
            vat_pricing._apply_packing_direction(doc, row, 'selling')
            self.assertEqual(row['selling_net_rate'], 1200)
            self.assertEqual(row['selling_gross_rate'], 1260)
            row['selling_rate'] = 1500
            vat_pricing._set_missing_packing_selling_rate_from_item(doc, row)
            self.assertEqual(row['selling_rate'], 1500)

    def test_new_hard_disk_rows_scale_unit_price_once(self):
        with patch.object(vat_pricing, 'get_item_tax_rate', return_value=5), patch.object(
            frappe, 'get_system_settings', return_value="Banker's Rounding"
        ):
            doc = {'custom_sales_net_rate': 428.57, 'custom_sales_gross_rate': 450,
                   'custom_sales_rate_includes_vat': 1, 'custom_tax': 'VAT'}
            for factor, gross, net in [(12, 5400, 5142.86), (2, 900, 857.14), (50, 22500, 21428.57)]:
                row = PackingRow(selling_rate=450, selling_vat_mode='Including VAT',
                                 conversion_factor=factor, __islocal=1)
                for _ in range(2):
                    vat_pricing._set_missing_packing_selling_rate_from_item(doc, row)
                    vat_pricing._apply_packing_direction(doc, row, 'selling')
                    self.assertEqual(row['selling_gross_rate'], gross)
                    self.assertEqual(row['selling_net_rate'], net)
            for extra in ({'__islocal': 0}, {'__islocal': 1, '__retail_manual_selling_price': True}):
                row = PackingRow(selling_rate=450, selling_vat_mode='Including VAT', conversion_factor=12, **extra)
                vat_pricing._set_missing_packing_selling_rate_from_item(doc, row)
                self.assertEqual(row['selling_rate'], 450)
