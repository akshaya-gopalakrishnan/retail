import unittest
from unittest.mock import patch, Mock

import frappe

from retail.domains.purchase import master_rates, selling_price
from retail.domains.item import rate_audit


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
                    self.assertEqual(values['last_purchase_rate'], 100)

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
