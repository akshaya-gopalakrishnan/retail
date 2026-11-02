"""Regression checks for Retail ownership of former core customizations."""
import unittest
from unittest.mock import patch

import frappe
from retail.core_compat.runtime import install


class TestInvoicePriceProtection(unittest.TestCase):
    def test_purchase_master_fallback_preserves_existing_prices_and_scope(self):
        from erpnext.stock import get_item_details as core
        from retail.domains.item import item_price_sync
        with patch.object(core, 'get_price_list_rate_for', return_value=None) as original, patch.object(
            item_price_sync, 'get_purchase_master_lookup_rate', return_value=100
        ) as fallback, patch.object(frappe, 'get_installed_apps', return_value=['retail']):
            install()
            wrapped = core.get_price_list_rate_for
            install()
            self.assertIs(wrapped, core.get_price_list_rate_for)
            for doctype in ('Purchase Receipt', 'Purchase Invoice'):
                self.assertEqual(wrapped(frappe._dict(doctype=doctype, price_list='Standard Buying'), 'ITEM'), 100)
            self.assertEqual(fallback.call_count, 2)
            fallback.reset_mock()
            for rate in (0, 80):
                original.return_value = rate
                self.assertEqual(wrapped(frappe._dict(doctype='Purchase Receipt', price_list='Standard Buying'), 'ITEM'), rate)
            original.return_value = None
            for doctype, price_list in [('Sales Invoice', 'Standard Buying'), ('Purchase Order', 'Standard Buying'),
                                        ('Purchase Invoice', 'Supplier Buying')]:
                self.assertIsNone(wrapped(frappe._dict(doctype=doctype, price_list=price_list), 'ITEM'))
            with patch.object(frappe, 'get_installed_apps', return_value=['erpnext']):
                self.assertIsNone(wrapped(frappe._dict(doctype='Purchase Receipt', price_list='Standard Buying'), 'ITEM'))
            fallback.assert_not_called()

    def test_guard_is_scoped_and_idempotent(self):
        from erpnext.stock import get_item_details as core

        original = core.insert_item_price
        try:
            with patch.object(core, "insert_item_price") as writer:
                install()
                wrapped = core.insert_item_price
                install()
                self.assertIs(core.insert_item_price, wrapped)
                with patch.object(frappe, "get_installed_apps", return_value=["retail"]):
                    for dt in ("Sales Invoice", "POS Invoice"):
                        core.insert_item_price(frappe._dict(doctype=dt))
                        core.insert_item_price(frappe._dict(parenttype=dt, doctype=dt + " Item"))
                    writer.assert_not_called()
                    core.insert_item_price(frappe._dict(doctype="Purchase Invoice"))
                    self.assertEqual(writer.call_count, 1)
                with patch.object(frappe, "get_installed_apps", return_value=["erpnext"]):
                    core.insert_item_price(frappe._dict(doctype="Sales Invoice"))
                    self.assertEqual(writer.call_count, 2)
        finally:
            core.insert_item_price = original
