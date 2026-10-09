"""Run on a migrated test site; test writes are rolled back."""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPackingUomsIntegration(FrappeTestCase):
    def test_standard_packing_conversion_and_prices(self):
        from retail.domains.item.packing_sync import sync_uoms_and_barcodes
        from retail.domains.item.item_price_sync import sync_packing_item_prices
        from erpnext.stock.get_item_details import get_conversion_factor, get_item_details
        from erpnext.stock.utils import scan_barcode
        item = frappe.get_doc({'doctype': 'Item', 'item_code': 'PACK-UOM-TEST-' + frappe.generate_hash(length=8),
            'item_name': 'Packing UOM regression', 'item_group': frappe.db.get_value('Item Group', {'is_group': 0}, 'name'),
            'stock_uom': 'Nos', 'is_stock_item': 0})
        item.insert(ignore_permissions=True)
        for factor in [21, 50, 100]:
            item.append('custom_retail_packing_detail', {'uom': 'Box', 'conversion_factor': factor,
                'barcode': item.name + '-' + str(factor), 'selling_rate': factor*10, 'purchase_rate': factor*5})
        for attempt in range(2):
            item.save(ignore_permissions=True)
            for row in item.custom_retail_packing_detail:
                assert row.uom == 'Box-' + str(int(row.conversion_factor)), row.uom
                assert get_conversion_factor(item.name, row.uom)['conversion_factor'] == row.conversion_factor
                assert scan_barcode(row.barcode)['uom'] == row.uom
                for price_list in ['Standard Selling', 'Standard Buying']:
                    assert frappe.db.count('Item Price', {'item_code': item.name, 'uom': row.uom, 'price_list': price_list}) == 1
        company = frappe.db.get_value('Company', {}, ['name', 'default_currency'], as_dict=True)
        for doctype in ['Sales Invoice', 'Purchase Invoice', 'Purchase Receipt', 'Delivery Note']:
            price_list = 'Standard Buying' if doctype.startswith('Purchase') else 'Standard Selling'
            for row in item.custom_retail_packing_detail:
                out = get_item_details(frappe._dict(item_code=item.name, uom=row.uom, qty=2,
                    doctype=doctype, company=company.name, currency=company.default_currency,
                    conversion_rate=1, price_list=price_list,
                    buying_price_list=price_list, selling_price_list=price_list,
                    price_list_currency=company.default_currency, plc_conversion_rate=1))
                assert out.conversion_factor == row.conversion_factor, out
                expected = frappe.db.get_value('Item Price', {'item_code': item.name, 'uom': row.uom, 'price_list': price_list}, 'price_list_rate')
                assert out.price_list_rate == expected, (doctype, row.uom, out.price_list_rate, expected)
