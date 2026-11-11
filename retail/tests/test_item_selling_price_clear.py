"""Selling-price clear lifecycles run entirely in memory."""
import unittest
from unittest.mock import Mock, patch

import frappe
from retail.domains.item import item_price_sync as sync, vat_pricing
from retail.domains.purchase import price_history


class Item(frappe._dict):
    def get_doc_before_save(self):
        return self._before

    def set(self, key, value):
        self[key] = value


class TestSellingPriceClear(unittest.TestCase):
    def setUp(self):
        self.price = frappe._dict(name='SELL', item_code='SKU', uom='Nos',
            price_list='Standard Selling', price_list_rate=5,
            creation='2026-11-11 10:00:00', valid_from='2026-11-11')
        self.db = Mock()
        self.db.has_column.return_value = True
        for context in [patch.object(frappe, 'db', self.db),
                        patch.object(frappe, 'get_system_settings', return_value="Banker's Rounding"),
                        patch.object(frappe, 'get_all', return_value=[self.price]),
                        patch.object(price_history, 'lock_item'),
                        patch.object(vat_pricing, 'get_item_tax_rate', return_value=0),
                        patch.object(price_history, 'record_change', return_value='REVISION')]:
            context.start()
            self.addCleanup(context.stop)

    def item(self):
        doc = Item(doctype='Item', name='SKU', stock_uom='Nos',
            custom_sales_rate_entry=0, custom_sales_net_rate=0, standard_rate=0,
            custom_b2b=99, last_purchase_rate=7, custom_average_purchase_rate=6,
            custom_retail_packing_detail=[])
        doc._before = frappe._dict(custom_sales_rate_entry=5, custom_sales_net_rate=5)
        return doc

    def test_unit_zero_clears_existing_record_and_records_selling_revision(self):
        doc = self.item()
        sync.sync_simple_item_prices(doc)
        self.db.set_value.assert_called_once_with('Item Price', 'SELL',
            {'price_list_rate': 0, price_history.POINTER: 'REVISION'})
        price_history.record_change.assert_called_once_with('SKU', 'Nos', self.price, 0,
            'SELL', source={'doctype': 'Item', 'name': 'SKU'})
        self.assertEqual((doc.last_purchase_rate, doc.custom_average_purchase_rate), (7, 6))

    def test_zero_to_positive_to_zero_updates_same_record(self):
        doc = self.item()
        def persist(_doctype, name, field, value=None):
            self.assertEqual(name, 'SELL')
            self.price.update(field if isinstance(field, dict) else {field: value})
        self.db.set_value.side_effect = persist
        with patch.object(sync, 'get_item_price_barcode', return_value='BAR'), \
                patch.object(frappe, 'get_doc') as create:
            sync.sync_simple_item_prices(doc)
            self.assertEqual(self.price.price_list_rate, 0)
            doc.custom_sales_rate_entry = doc.custom_sales_net_rate = doc.standard_rate = 8
            sync.sync_simple_item_prices(doc)
            self.assertEqual(self.price.price_list_rate, 8)
            doc.custom_sales_rate_entry = doc.custom_sales_net_rate = doc.standard_rate = 0
            sync.sync_simple_item_prices(doc)
            self.assertEqual(self.price.price_list_rate, 0)
            self.db.set_value.reset_mock()
            sync.sync_simple_item_prices(doc)
            self.db.set_value.assert_not_called()
            create.assert_not_called()

    def test_no_existing_price_does_not_create_zero_record_or_history(self):
        with patch.object(frappe, 'get_all', return_value=[]), patch.object(frappe, 'get_doc') as create:
            sync.sync_simple_item_prices(self.item())
        create.assert_not_called()
        price_history.record_change.assert_not_called()
        self.db.set_value.assert_not_called()

    def test_packing_zero_targets_its_uom_without_changing_positive_buying_price(self):
        doc = self.item()
        doc.custom_retail_packing_detail = [frappe._dict(uom='Box-10',
            selling_rate=0, selling_net_rate=0, purchase_rate=30, purchase_net_rate=30)]
        with patch.object(sync, '_clear_item_price') as clear, patch.object(sync, 'sync_item_price') as positive:
            sync.sync_packing_item_prices(doc)
        clear.assert_called_once_with('SKU', 'Box-10', 'Standard Selling')
        self.assertEqual(positive.call_args.args[1:3], ('Standard Buying', 30))

    def test_positive_packing_for_same_uom_prevents_zero_row_overriding_it(self):
        doc = self.item()
        doc.custom_retail_packing_detail = [
            frappe._dict(uom='Box-10', selling_rate=0, selling_net_rate=0),
            frappe._dict(uom='Box-10', selling_rate=8, selling_net_rate=8)]
        with patch.object(sync, '_clear_item_price') as clear, patch.object(sync, 'sync_item_price'):
            sync.sync_packing_item_prices(doc)
        clear.assert_not_called()

    def test_duplicate_or_specialized_selling_prices_raise_instead_of_staying_stale(self):
        for prices in [[self.price, self.price.copy()], [frappe._dict(self.price, customer='Customer')]]:
            with patch.object(frappe, 'get_all', return_value=prices), \
                    patch.object(frappe, 'throw', side_effect=ValueError), self.assertRaises(ValueError):
                sync.sync_simple_item_prices(self.item())
        self.db.set_value.assert_not_called()
        price_history.record_change.assert_not_called()

    def test_cleared_packing_remains_zero_on_first_and_subsequent_server_saves(self):
        doc = self.item()
        doc.standard_rate = doc.custom_sales_net_rate = 5
        row = Item(uom='Box-10', conversion_factor=10, selling_rate=0, selling_net_rate=0)
        for previous_rate in [50, 0]:
            doc._before.custom_retail_packing_detail = [frappe._dict(
                uom='Box-10', selling_rate=previous_rate)]
            vat_pricing._set_missing_packing_selling_rate_from_item(doc, row)
            self.assertEqual(row.selling_rate, 0)

    def test_new_pack_defaults_still_work_but_manual_zero_is_preserved(self):
        doc = self.item()
        doc.standard_rate = doc.custom_sales_net_rate = 5
        row = Item(uom='Box-10', conversion_factor=10, selling_rate=0, __islocal=1)
        vat_pricing._set_missing_packing_selling_rate_from_item(doc, row)
        self.assertEqual(row.selling_rate, 50)
        row.selling_rate = 0
        row["__retail_manual_selling_price"] = True
        vat_pricing._set_missing_packing_selling_rate_from_item(doc, row)
        self.assertEqual(row.selling_rate, 0)
