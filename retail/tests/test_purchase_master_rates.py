import unittest
from unittest.mock import patch, Mock

import frappe

from retail.domains.purchase import master_rates, selling_price
from retail.domains.item import rate_audit, item_price_sync


class TestStandardSellingRate(unittest.TestCase):
    def _item(self, **overrides):
        values = {"stock_uom": "Nos", "standard_rate": 4, "custom_sales_net_rate": 8}
        values.update(overrides)
        return frappe._dict(values)

    def test_exact_price_list_rate_wins(self):
        def get_value(doctype, filters, field, as_dict=False):
            if doctype == "Item":
                return self._item()
            if doctype == "Item Price" and filters.get("uom") == "Nos":
                return 9
            return None

        with patch.object(frappe, "db", Mock(get_value=get_value)):
            self.assertEqual(selling_price.get_standard_selling_rate("ITEM", "Nos"), 9)

    def test_stock_item_master_rate_is_used_when_the_price_list_is_empty(self):
        def get_value(doctype, filters, field, as_dict=False):
            if doctype == "Item":
                return self._item()
            return None

        with patch.object(frappe, "db", Mock(get_value=get_value)):
            self.assertEqual(selling_price.get_standard_selling_rate("ITEM"), 8)

    def test_packing_selling_rate_is_used_when_the_price_list_is_empty(self):
        def get_value(doctype, filters, field, as_dict=False):
            if doctype == "Item":
                return self._item()
            if doctype == "Retail Packing Detail":
                return frappe._dict(selling_net_rate=70, selling_rate=80, conversion_factor=10)
            return None

        with patch.object(frappe, "db", Mock(get_value=get_value)):
            self.assertEqual(selling_price.get_standard_selling_rate("ITEM", "Box"), 70)


class TestPurchaseMasterRates(unittest.TestCase):
    def setUp(self):
        rounding = patch.object(frappe, 'get_system_settings', return_value="Banker's Rounding")
        rounding.start()
        self.addCleanup(rounding.stop)
        self.item = frappe._dict(name='ITEM', stock_uom='Nos')
        self.row = frappe._dict(name='ROW', item_code='ITEM', qty=2, uom='Box',
            conversion_factor=12, base_net_rate=120, net_rate=60,
            custom_upd_sell_price=1, custom_new_sell_rate=180)
        self.doc = frappe._dict(doctype='Purchase Receipt', name='PR', company='Company',
            currency='USD', conversion_rate=2, custom_update_item_master_rates=1,
            custom_allow_selling_price=1, items=[self.row])

    def test_disabled_and_returns_do_not_write(self):
        with patch.object(master_rates.rate_audit, '_require_price_manager') as permission, patch.object(
            frappe, 'get_doc'
        ) as get_doc:
            self.doc.custom_update_item_master_rates = 0
            master_rates.update_purchase_master_rates(self.doc)
            self.doc.custom_update_item_master_rates = 1
            self.doc.is_return = 1
            master_rates.update_purchase_master_rates(self.doc)
            permission.assert_not_called()
            get_doc.assert_not_called()

    def test_purchase_uses_base_net_and_stock_uom_for_both_documents(self):
        with patch.object(master_rates.rate_audit, '_require_price_manager'), patch.object(
            frappe, 'get_doc', return_value=self.item
        ), patch.object(master_rates, '_apply') as apply:
            for doctype in ('Purchase Receipt', 'Purchase Invoice'):
                self.doc.doctype = doctype
                master_rates.update_purchase_master_rates(self.doc)
                self.assertEqual(apply.call_args.args[3:], ('Purchase', 10, 'Box', 12))

    def test_free_purchase_does_not_fall_back_to_positive_net(self):
        self.row.base_net_rate = 0
        with patch.object(master_rates.rate_audit, '_require_price_manager'), patch.object(
            frappe, 'get_doc', return_value=self.item
        ), patch.object(rate_audit, '_apply_item_rate_update') as apply:
            master_rates.update_purchase_master_rates(self.doc)
            apply.assert_not_called()

    def test_pr_and_pi_update_purchased_packing_with_discounted_company_rate(self):
        self.row.uom = 'Box-10'
        self.row.conversion_factor = 10
        self.row.base_net_rate = 100
        self.row.price_list_rate = 1000
        self.item.custom_retail_packing_detail = [
            frappe._dict(name='PACK', uom='Box-10', purchase_vat_mode='Including VAT',
                         purchase_vat_confirmed=1, selling_net_rate=150),
            frappe._dict(name='OTHER', uom='Carton-100', purchase_rate=9999),
        ]
        with patch.object(rate_audit, '_require_price_manager'), patch.object(
            frappe, 'get_doc', return_value=self.item
        ), patch.object(rate_audit, '_apply_item_rate_update') as audit, patch.object(
            rate_audit, '_get_item_direction_vat_rate', return_value=5
        ), patch.object(item_price_sync, 'sync_item_price') as prices, patch.object(
            frappe, 'clear_document_cache'
        ), patch.object(frappe, 'db', Mock(get_value=Mock(return_value='AED'))) as db:
            for doctype in ('Purchase Receipt', 'Purchase Invoice'):
                with self.subTest(doctype=doctype):
                    db.reset_mock()
                    prices.reset_mock()
                    self.doc.doctype = doctype
                    master_rates.update_purchase_master_rates(self.doc)
                    self.assertEqual(audit.call_args.kwargs['new_net_rate'], 10)
                    db.set_value.assert_called_once()
                    self.assertEqual(db.set_value.call_args.args[:2], ('Retail Packing Detail', 'PACK'))
                    values = db.set_value.call_args.args[2]
                    self.assertEqual(values['purchase_net_rate'], 100)
                    self.assertEqual(values['purchase_rate'], 105)
                    self.assertEqual(values['purchase_vat_amount'], 5)
                    self.assertEqual(values['purchase_gross_rate'], 105)
                    self.assertEqual(values['purchase_vat_status'], 'Incl 5% OK')
                    self.assertEqual(values['packing_margin'], 50)
                    self.assertFalse(any(key.startswith('selling_') for key in values))
                    self.assertEqual([(call.kwargs['uom'], call.args[2]) for call in prices.call_args_list],
                                     [('Nos', 10), ('Box-10', 100)])

    def test_purchase_lookup_prices_convert_company_currency_to_price_list_currency(self):
        with patch.object(frappe, 'db', Mock()), patch.object(
            master_rates, '_currency_factor', return_value=2
        ), patch.object(item_price_sync, 'sync_item_price') as prices:
            master_rates._sync_purchase_lookup_prices(self.doc, self.row, self.item, 'Box', 10, 12)
            self.assertEqual([(call.kwargs['uom'], call.args[2]) for call in prices.call_args_list],
                             [('Nos', 5), ('Box', 60)])
            prices.reset_mock()
            master_rates._sync_purchase_lookup_prices(self.doc, self.row, self.item, 'Nos', 10, 1)
            prices.assert_called_once()

    def test_missing_buying_price_uses_exact_packing_net_rate_and_currency(self):
        self.item.custom_purchase_net_rate = 10
        self.item.custom_retail_packing_detail = [
            frappe._dict(uom='Box-10', purchase_net_rate=95.24, purchase_rate=100),
            frappe._dict(uom='Box-20', purchase_net_rate=180, disabled=1),
        ]
        with patch.object(frappe, 'get_cached_doc', return_value=self.item):
            for uom, expected in [('Nos', 5), ('Box-10', 47.62), ('Box', None), ('Box-20', None)]:
                self.assertEqual(item_price_sync.get_purchase_master_lookup_rate(
                    frappe._dict(uom=uom, plc_conversion_rate=2), 'ITEM'), expected)

    def test_packing_exclusive_and_exempt_prices_preserve_entry_mode(self):
        self.item.custom_retail_packing_detail = [
            frappe._dict(name='PACK', uom='Box', purchase_vat_mode='Excluding VAT')
        ]
        for vat_rate, gross in [(5, 105), (0, 100)]:
            with self.subTest(vat_rate=vat_rate), patch.object(
                rate_audit, '_get_item_direction_vat_rate', return_value=vat_rate
            ), patch.object(frappe, 'db', Mock()) as db:
                master_rates._update_purchased_packing(self.item, 'Box', 100)
                values = db.set_value.call_args.args[2]
                self.assertEqual(values['purchase_rate'], 100)
                self.assertEqual(values['purchase_gross_rate'], gross)
                self.assertEqual(values['purchase_vat_mode'], 'Excluding VAT')

    def test_purchase_without_matching_packing_does_not_change_other_packings(self):
        self.item.custom_retail_packing_detail = [frappe._dict(name='PACK', uom='Box-10')]
        with patch.object(frappe, 'db', Mock()) as db:
            for uom in ('Nos', 'Unknown'):
                master_rates._update_purchased_packing(self.item, uom, 10)
            db.set_value.assert_not_called()

    def test_selling_stock_override_wins_and_packing_converts(self):
        with patch.object(master_rates.rate_audit, '_require_price_manager'), patch.object(
            frappe, 'db', Mock(get_value=Mock(return_value='AED'))
        ), patch.object(master_rates, '_apply') as apply:
            master_rates.update_selling_master_rate(self.doc, self.row, self.item, {'Box': 180})
            self.assertEqual(apply.call_args.args[3:], ('Selling', 15, 'Box', 12))
            master_rates.update_selling_master_rate(self.doc, self.row, self.item, {'Box': 180, 'Nos': 20})
            self.assertEqual(apply.call_args.args[3:], ('Selling', 20, 'Nos', 1))

    def test_vat_fields_are_complete_for_purchase_and_selling(self):
        with patch.object(frappe, 'db', Mock(has_column=Mock(return_value=True))):
            for direction, prefix, base in [('Purchase', 'purchase', 'custom_default_purchase_rate'),
                                           ('Selling', 'sales', 'standard_rate')]:
                state = rate_audit._make_rate_state(100, 5)
                values = rate_audit._get_item_update_values(direction, state)
                self.assertEqual(values[base], 100)
                self.assertEqual(values[f'custom_{prefix}_net_rate'], 100)
                self.assertEqual(values[f'custom_{prefix}_vat_amount'], 5)
                self.assertEqual(values[f'custom_{prefix}_gross_rate'], 105)
                self.assertEqual(values[f'custom_{prefix}_rate_entry'], 105)
                self.assertEqual(values[f'custom_{prefix}_rate_includes_vat'], 1)
                if direction == 'Purchase':
                    self.assertNotIn('last_purchase_rate', values)

    def test_permission_denial_stops_master_update(self):
        with patch.object(master_rates.rate_audit, '_require_price_manager', side_effect=PermissionError), patch.object(
            master_rates, '_apply'
        ) as apply:
            with self.assertRaises(PermissionError):
                master_rates.update_purchase_master_rates(self.doc)
            apply.assert_not_called()

    def test_currency_conversion_and_missing_uom_factor(self):
        with patch.object(frappe, 'db', Mock(get_value=Mock(return_value='AED'))), patch.object(
            frappe, 'throw', side_effect=ValueError
        ):
            self.assertEqual(master_rates._currency_factor(self.doc, 'USD'), 2)
            self.assertEqual(master_rates._currency_factor(self.doc, 'AED'), 1)
            with self.assertRaises(ValueError):
                master_rates._currency_factor(self.doc, 'EUR')
            with self.assertRaises(ValueError):
                master_rates._factor(self.item, 'Box', 0)

    def test_exempt_vat(self):
        self.assertEqual(rate_audit._make_rate_state(100, 0),
                         {'net': 100, 'vat': 0, 'gross': 100})

    def test_equal_price_still_updates_master_and_disabled_checkbox_does_not(self):
        from retail.domains.purchase import price_history
        with patch.object(price_history, 'lock_item'), patch.object(price_history, 'sync_selling_state') as sync, patch.object(
            master_rates, 'update_purchase_master_rates'
        ), patch.object(master_rates, 'update_selling_master_rate') as master, patch.object(
            frappe, 'get_doc', return_value=self.item
        ), patch.object(selling_price, '_packing_prices', return_value=[]), patch.object(
            selling_price, 'get_standard_selling_rate', return_value=180
        ), patch.object(selling_price, 'sync_item_price') as price:
            selling_price.update_selected_selling_prices(self.doc)
            master.assert_called_once()
            price.assert_not_called()
            sync.assert_not_called()
            master.reset_mock()
            self.doc.custom_update_item_master_rates = 0
            selling_price.update_selected_selling_prices(self.doc)
            master.assert_not_called()
