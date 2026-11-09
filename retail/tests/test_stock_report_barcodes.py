"""Check barcode resolution and preserve native report calculations."""
import unittest
from unittest.mock import Mock, patch

import frappe

from retail.stock_report_barcodes import execute, matching_items


class TestStockReportBarcodes(unittest.TestCase):
	def test_master_and_alternate_barcodes_are_combined(self):
		with patch("retail.stock_report_barcodes.frappe.get_all",
			side_effect=[["MAIN"], ["STANDARD", "MAIN"], ["PACK"]]) as query:
			self.assertEqual(matching_items("00123"), {"MAIN", "STANDARD", "PACK"})
			self.assertEqual(query.call_args_list[2].kwargs["filters"],
				{"barcode": "00123", "parenttype": "Item"})

	def test_filter_intersection_and_native_values_are_preserved(self):
		filters = {"barcode": "00123", "item_code": ["A", "B"], "warehouse": ["WH"]}
		rows = [frappe._dict(item_code="B", bal_qty=7, bal_val=21)]
		native = Mock(return_value=([
			{"fieldname": "item_code"}, {"fieldname": "item_name"},
			{"fieldname": "bal_qty"}], rows, "message"))
		with patch("retail.stock_report_barcodes.matching_items", return_value={"B", "C"}), \
			patch("retail.stock_report_barcodes.frappe.get_all",
				return_value=[frappe._dict(name="B", custom_barcode="00123")]), \
			patch("retail.stock_report_barcodes._", side_effect=lambda text: text):
			result = execute("Stock Balance", filters, native)
		self.assertEqual(native.call_args.args[0].item_code, ["B"])
		self.assertEqual(native.call_args.args[0].warehouse, ["WH"])
		self.assertEqual(filters["item_code"], ["A", "B"])
		self.assertEqual(result[1][0], dict(item_code="B", bal_qty=7, bal_val=21, barcode="00123"))
		self.assertEqual(result[0][2]["fieldname"], "barcode")
		self.assertEqual(result[2], "message")
