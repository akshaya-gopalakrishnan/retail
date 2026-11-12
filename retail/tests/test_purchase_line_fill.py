"""One purchase line fill resolves, prices and taxes a row once."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from retail.domains.purchase import line_fill


class TestPurchaseLineFill(unittest.TestCase):
	def setUp(self):
		self.item = frappe._dict(name="SKU", item_name="Primer", stock_uom="Nos", purchase_uom="Box-10",
			has_serial_no=0, has_batch_no=0, disabled=0, is_purchase_item=1, custom_barcode="555")
		patches = [
			patch.object(frappe, "local", SimpleNamespace(flags=frappe._dict(in_test=False))),
			patch.object(line_fill, "scan_barcode", return_value={"item_code": "SKU", "uom": "Box-10", "barcode": "555"}),
			patch.object(line_fill, "get_item_details", return_value={"item_name": "Primer", "uom": "Box-10", "rate": 10, "qty": 1}),
			patch.object(line_fill, "get_standard_selling_rate", return_value=12),
			patch.object(line_fill, "get_item_selling_vat_rate", return_value=5),
			patch.object(line_fill, "get_transaction_item_vat_rate", return_value=5),
			patch.object(line_fill, "get_transaction_vat_tax_rows", return_value={"tax_rows": [], "item_tax_rates": {}}),
			patch.object(frappe, "has_permission", return_value=True),
			patch.object(frappe, "get_meta", return_value=SimpleNamespace(has_field=lambda name: name == "custom_barcode")),
			patch.object(frappe, "db", SimpleNamespace(get_value=Mock(return_value=self.item))),
		]
		self.mocks = [item.start() for item in patches]
		for item in patches:
			self.addCleanup(item.stop)

	def document(self):
		return {"doctype": "Purchase Receipt", "name": "new-purchase-receipt-1", "__islocal": 1,
			"company": "Demo", "supplier": "S-2", "set_warehouse": "Stores", "buying_price_list": "Standard Buying",
			"items": [{"doctype": "Purchase Receipt Item", "name": "row-1", "parentfield": "items"}]}

	def test_barcode_scan_prices_the_packing_once(self):
		result = line_fill.fill_line(self.document(), search_value="555", child_name="row-1")
		self.assertEqual(result["item_code"], "SKU")
		self.assertEqual(result["uom"], "Box-10")
		self.assertEqual(result["details"]["rate"], 10)
		self.assertEqual(result["details"]["barcode"], "555")
		self.assertEqual(result["selling_rate"], 12)
		self.assertEqual(result["purchase_vat_rate"], 5)
		details_call = self.mocks[2]
		details_call.assert_called_once()
		self.assertEqual(details_call.call_args.args[0]["barcode"], "555")
		self.assertEqual(details_call.call_args.args[0]["uom"], "Box-10")
		self.mocks[1].assert_called_once_with("555")

	def test_named_item_does_not_scan_again(self):
		line_fill.fill_line(self.document(), item_code="SKU", uom="Nos", child_name="row-1")
		self.mocks[1].assert_not_called()
		self.assertEqual(self.mocks[2].call_args.args[0]["uom"], "Nos")

	def test_unknown_barcode_returns_nothing_without_pricing(self):
		self.mocks[1].return_value = {}
		self.assertEqual(line_fill.fill_line(self.document(), search_value="missing"), {})
		self.mocks[2].assert_not_called()

	def test_sales_document_is_rejected_before_any_lookup(self):
		with patch.object(frappe, "throw", side_effect=ValueError):
			with self.assertRaises(ValueError):
				line_fill.fill_line({"doctype": "Sales Invoice"}, item_code="SKU")
		self.mocks[1].assert_not_called()
		self.mocks[2].assert_not_called()

	def test_vat_failure_still_returns_the_priced_row(self):
		self.mocks[6].side_effect = RuntimeError("tax table")
		with patch.object(frappe, "logger", return_value=SimpleNamespace(warning=lambda *args, **kwargs: None)):
			result = line_fill.fill_line(self.document(), item_code="SKU", child_name="row-1")
		self.assertEqual(result["details"]["rate"], 10)
		self.assertIsNone(result["vat_tax"])
