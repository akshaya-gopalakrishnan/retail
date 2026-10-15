"""Regression checks for Retail ownership of former core customizations."""
import unittest
from unittest.mock import patch

import frappe
from retail.core_compat.runtime import install


class TestInvoicePriceProtection(unittest.TestCase):
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
