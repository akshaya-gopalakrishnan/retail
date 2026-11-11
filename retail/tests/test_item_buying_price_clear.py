"""In-memory lifecycle tests for positive and zero maintained buying prices."""
import unittest
from unittest.mock import Mock, patch

import frappe
from retail.domains.item import item_price_sync as sync


class Item(frappe._dict):
    def get_doc_before_save(self):
        return self._before


class TestBuyingPriceClear(unittest.TestCase):
    def setUp(self):
        self.price = frappe._dict(name="PRICE", item_code="SKU", uom="Nos",
            price_list="Standard Buying", price_list_rate=38,
            creation="2026-11-10 10:00:00", valid_from="2026-11-10",
            **{sync.MANAGED_BUYING_FIELD: 1})
        self.db = Mock()
        self.db.has_column.return_value = True
        self.patches = [patch.object(frappe, 'db', self.db),
            patch.object(frappe, 'get_all', side_effect=lambda *a, **k: [self.price]),
            patch('retail.domains.purchase.price_history.lock_item')]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def item(self, old_entry=39.9, new_entry=0):
        doc = Item(doctype='Item', name='SKU', item_code='SKU', stock_uom='Nos',
            custom_purchase_rate_entry=new_entry, custom_purchase_net_rate=0,
            last_purchase_rate=38, custom_retail_packing_detail=[])
        doc._before = frappe._dict(custom_purchase_rate_entry=old_entry,
            custom_purchase_net_rate=38 if old_entry else 0)
        return doc

    def test_intentional_clear_zeros_owned_price_without_stale_last_rate_recreation(self):
        sync.sync_simple_item_prices(self.item())
        self.db.set_value.assert_called_once_with('Item Price', 'PRICE', 'price_list_rate', 0)

    def test_blank_stays_blank_and_generic_zero_sync_never_writes(self):
        self.assertFalse(sync._purchase_cleared(None, self.item()))
        self.assertFalse(sync._purchase_cleared(self.item(0)._before, self.item(0)))
        sync.sync_item_price({'item_code': 'SKU'}, 'Standard Buying', 0)
        self.db.set_value.assert_not_called()

    def test_specialized_prices_are_preserved_with_an_explicit_error(self):
        for changes in (
            {'supplier': 'Supplier'},
            {'customer': 'Customer'}, {'batch_no': 'Batch'},
            {'valid_upto': '2026-12-31'}, {'valid_from': '2027-01-01'},
            {'reference': 'PR-1'}, {'note': 'Negotiated price'},
        ):
            with self.subTest(changes=changes):
                old = self.price.copy()
                self.price.update(changes)
                with patch.object(frappe, 'throw', side_effect=ValueError), self.assertRaises(ValueError):
                    sync._clear_managed_buying_price('SKU', 'Nos')
                self.db.set_value.assert_not_called()
                self.price.clear()
                self.price.update(old)

    def test_duplicate_prices_stop_the_save_instead_of_silently_retaining_old_prices(self):
        with patch.object(frappe, 'get_all', return_value=[self.price, self.price.copy()]), \
                patch.object(frappe, 'throw', side_effect=ValueError), self.assertRaises(ValueError):
            sync._clear_managed_buying_price('SKU', 'Nos')
        self.db.set_value.assert_not_called()

    def test_legacy_manual_and_transaction_prices_clear_without_provenance_column(self):
        self.db.has_column.return_value = False
        self.price.pop(sync.MANAGED_BUYING_FIELD)
        sync.sync_simple_item_prices(self.item())
        self.db.set_value.assert_called_once_with('Item Price', 'PRICE', 'price_list_rate', 0)

    def test_resaving_explicit_zero_repairs_a_stale_price_but_blank_does_not(self):
        sync.sync_simple_item_prices(self.item(0))
        self.db.set_value.assert_called_once_with('Item Price', 'PRICE', 'price_list_rate', 0)
        self.db.set_value.reset_mock()
        doc = self.item(0, None)
        sync.sync_simple_item_prices(doc)
        self.db.set_value.assert_not_called()

    def test_zero_to_positive_to_zero_updates_same_record_and_preserves_history(self):
        self.price[sync.MANAGED_BUYING_FIELD] = 0
        self.price.price_list_rate = 0
        doc = self.item(0, 5)
        doc.custom_purchase_net_rate = 5
        doc.custom_default_purchase_rate = 5
        doc.custom_average_purchase_rate = 2
        def persist(_doctype, name, field, value=None):
            self.assertEqual(name, 'PRICE')
            self.price.update(field if isinstance(field, dict) else {field: value})
        self.db.set_value.side_effect = persist
        with patch.object(sync, 'get_item_price_barcode', return_value='BAR'), \
                patch.object(frappe, 'get_doc') as create:
            sync.sync_simple_item_prices(doc)
            self.assertEqual(self.price.price_list_rate, 5)
            doc._before = frappe._dict(custom_purchase_rate_entry=5, custom_purchase_net_rate=5)
            doc.custom_purchase_rate_entry = 0
            doc.custom_purchase_net_rate = 0
            doc.custom_default_purchase_rate = 0
            sync.sync_simple_item_prices(doc)
            self.assertEqual(self.price.price_list_rate, 0)
            self.assertEqual(doc.last_purchase_rate, 38)
            self.assertEqual(doc.custom_average_purchase_rate, 2)
            create.assert_not_called()
        self.db.set_value.reset_mock()
        sync.sync_simple_item_prices(doc)
        self.db.set_value.assert_not_called()

    def test_zero_without_existing_price_does_not_create_a_record(self):
        with patch.object(frappe, 'get_all', return_value=[]), patch.object(frappe, 'get_doc') as create:
            sync.sync_simple_item_prices(self.item())
            create.assert_not_called()
        self.db.set_value.assert_not_called()

    def test_packing_clear_targets_only_its_uom_and_does_not_clear_alternate_positive_price(self):
        doc = self.item(0)
        row = frappe._dict(uom='Box-36', purchase_rate=0, purchase_net_rate=0)
        doc.custom_retail_packing_detail = [row]
        previous = frappe._dict(custom_retail_packing_detail=[frappe._dict(
            uom='Box-36', purchase_rate=39.9, purchase_net_rate=38)])
        with patch.object(sync, '_clear_managed_buying_price') as clear, patch.object(sync, 'sync_item_price'):
            sync.sync_packing_item_prices(doc, previous=previous)
            clear.assert_called_once_with('SKU', 'Box-36')
            clear.reset_mock()
            doc.custom_retail_packing_detail.append(frappe._dict(
                uom='Box-36', purchase_rate=50, purchase_net_rate=50))
            sync.sync_packing_item_prices(doc, previous=previous)
            clear.assert_not_called()

    def test_new_item_prices_are_marked_but_existing_unmarked_rows_are_not_adopted(self):
        doc = self.item()
        price = Mock()
        with patch.object(frappe, 'get_all', return_value=[]), patch.object(
                frappe, 'get_doc', return_value=price) as create, patch.object(
                sync, 'get_item_price_barcode', return_value='BAR'):
            sync.sync_item_price(doc, 'Standard Buying', 38)
            self.assertEqual(create.call_args.args[0][sync.MANAGED_BUYING_FIELD], 1)
        self.price[sync.MANAGED_BUYING_FIELD] = 0
        with patch.object(sync, 'get_item_price_barcode', return_value='BAR'):
            sync.sync_item_price(doc, 'Standard Buying', 38)
        values = self.db.set_value.call_args.args[2]
        self.assertNotIn(sync.MANAGED_BUYING_FIELD, values)

    def test_transaction_update_releases_item_ownership(self):
        with patch.object(sync, 'get_item_price_barcode', return_value='BAR'):
            sync.sync_item_price({'item_code': 'SKU'}, 'Standard Buying', 40,
                                source={'doctype': 'Purchase Receipt', 'name': 'PR-1'}, uom='Nos')
        self.assertEqual(self.db.set_value.call_args.args[2][sync.MANAGED_BUYING_FIELD], 0)

    def test_direct_price_save_releases_item_ownership(self):
        doc = Mock()
        doc.flags = frappe._dict()
        doc.meta.has_field.return_value = True
        doc.get.return_value = None
        sync.populate_item_price_barcode(doc)
        doc.set.assert_called_once_with(sync.MANAGED_BUYING_FIELD, 0)

    def test_server_validation_does_not_refill_explicitly_cleared_packing(self):
        from retail.domains.item import vat_pricing
        doc = self.item()
        doc.set = lambda key, value: doc.__setitem__(key, value)
        doc._before.custom_retail_packing_detail = [frappe._dict(
            uom='Box-36', purchase_rate=1436.4, purchase_net_rate=1368)]
        row = frappe._dict(uom='Box-36', purchase_rate=0, purchase_net_rate=1368,
                          conversion_factor=36)
        row.set = lambda key, value: row.__setitem__(key, value)
        # Even with an independently positive unit price, clearing a saved pack
        # must survive the default-filling phase and reach VAT calculation.
        doc.custom_purchase_net_rate = 38
        vat_pricing._set_missing_packing_purchase_rate_from_item(doc, row)
        self.assertEqual(row.purchase_rate, 0)
        with patch.object(frappe, 'get_system_settings', return_value="Banker's Rounding"):
            vat_pricing._apply_packing_direction(doc, row, 'purchase')
        self.assertEqual(row.purchase_net_rate, 0)
        doc._before.custom_retail_packing_detail[0].purchase_rate = 0
        doc._before.custom_retail_packing_detail[0].purchase_net_rate = 0
        vat_pricing._set_missing_packing_purchase_rate_from_item(doc, row)
        self.assertEqual(row.purchase_rate, 0)
