import unittest
from unittest.mock import patch

import frappe
from erpnext.stock.get_item_details import insert_item_price
from retail.domains.item import item_price_sync as prices


class TestInvoicePriceIsolation(unittest.TestCase):
	def test_invoice_lifecycle_preserves_master_and_invoice_rates(self):
		for doctype in ("POS Invoice", "Sales Invoice"):
			for is_return, is_consolidated in ((0, 0), (1, 0), (0, 1)):
				with self.subTest(doctype=doctype, is_return=is_return, consolidated=is_consolidated):
					row = frappe._dict(item_code="OPEN", uom="Nos", rate=37, price_list_rate=50)
					doc = frappe._dict(doctype=doctype, items=[row], selling_price_list="Branch Selling",
						is_return=is_return, is_consolidated=is_consolidated)
					with patch.object(prices, "sync_item_price") as write, patch.object(
						prices, "_recalculate_side_item_prices"
					) as recalculate:
						for event in ("on_submit", "on_update_after_submit"):
							prices.sync_latest_transaction_item_prices(doc, event)
						prices.recalculate_transaction_item_prices(doc, "on_cancel")
						prices.sync_transaction_item_prices(doc, "Standard Selling", "Branch Selling")
						write.assert_not_called()
						recalculate.assert_not_called()
					self.assertEqual(row.rate, 37)
					self.assertEqual(row.price_list_rate, 50)

	def test_other_sales_cancellation_cannot_restore_an_invoice_override(self):
		doc = frappe._dict(doctype="Sales Order", selling_price_list="Branch Selling")
		with patch.object(prices, "_recalculate_side_item_prices") as recalculate:
			prices.recalculate_transaction_item_prices(doc)
			history = recalculate.call_args.args[1]
			self.assertTrue(history)
			self.assertFalse({entry[0] for entry in history} & {"POS Invoice", "Sales Invoice"})

	def test_core_auto_price_write_is_blocked_before_settings_or_database_access(self):
		for doctype in ("POS Invoice", "Sales Invoice"):
			for context in ({"doctype": doctype}, {"doctype": doctype + " Item", "parenttype": doctype}):
				with self.subTest(context=context), patch.object(frappe, "get_cached_doc") as settings:
					insert_item_price(frappe._dict(context, price_list="Standard Selling", rate=37,
						item_code="OPEN", currency="AED"))
					settings.assert_not_called()

	def test_purchase_price_sync_still_runs(self):
		doc = frappe._dict(doctype="Purchase Invoice", buying_price_list="Supplier Buying")
		with patch.object(prices, "sync_transaction_item_prices") as sync:
			prices.sync_latest_transaction_item_prices(doc)
			sync.assert_called_once_with(doc, "Standard Buying", "Supplier Buying")
