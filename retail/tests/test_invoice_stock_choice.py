"""Invoice stock choice checks without business data writes."""
import unittest
from unittest.mock import Mock, patch

import frappe
from retail.domains.transactions.stock import set_update_stock_for_standalone_invoice


class TestInvoiceStockChoice(unittest.TestCase):
    def invoice(self, doctype, update_stock=0, **item_values):
        return frappe._dict(
            doctype=doctype, update_stock=update_stock,
            meta=Mock(has_field=Mock(return_value=True)),
            items=[frappe._dict(item_code="STOCK-ITEM", **item_values)],
        )

    def test_sales_choice_survives_save_and_submit_validation(self):
        for choice in (0, 1):
            doc = self.invoice("Sales Invoice", choice)
            with patch("frappe.get_cached_value", return_value=1):
                for status in (0, 1):
                    doc.docstatus = status
                    set_update_stock_for_standalone_invoice(doc, "before_validate")
                    self.assertEqual(doc.update_stock, choice)

    def test_purchase_behavior_is_preserved(self):
        with patch("frappe.get_cached_value", return_value=1):
            standalone = self.invoice("Purchase Invoice")
            linked = self.invoice("Purchase Invoice", purchase_receipt="PR-TEST")
            set_update_stock_for_standalone_invoice(standalone)
            set_update_stock_for_standalone_invoice(linked)
        self.assertEqual(standalone.update_stock, 1)
        self.assertEqual(linked.update_stock, 0)
