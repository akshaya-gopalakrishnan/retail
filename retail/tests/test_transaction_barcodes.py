import unittest

import frappe
from retail.transaction_barcodes import resolve


class TestTransactionBarcodes(unittest.TestCase):
	def setUp(self):
		self.items = {"ITEM": frappe._dict(stock_uom="Nos", custom_barcode="BASE")}
		self.packings = [frappe._dict(name="PACK", parent="ITEM", uom="Box-10", barcode="BOX")]

	def barcode(self, **values):
		row = dict(name="ROW", item_code="ITEM", uom="Nos", **values)
		return resolve([row], self.items, self.packings)["ROW"]

	def test_stock_item_uses_master_barcode(self):
		self.assertEqual(self.barcode(), "BASE")

	def test_packing_identity_wins_over_stale_master_barcode(self):
		row = dict(name="ROW", item_code="ITEM", uom="Box-10",
			custom_packing_detail="PACK", barcode="BASE", custom_item_barcode="BASE")
		self.assertEqual(resolve([row], self.items, self.packings)["ROW"], "BOX")

	def test_unique_packing_uom_resolves_without_native_barcode_field(self):
		row = dict(name="ROW", item_code="ITEM", uom="Box-10")
		self.assertEqual(resolve([row], self.items, self.packings)["ROW"], "BOX")

	def test_scanned_barcode_is_preserved(self):
		self.assertEqual(self.barcode(barcode="SCANNED"), "SCANNED")

	def test_blank_packing_barcode_does_not_use_master(self):
		self.packings[0].barcode = ""
		row = dict(name="ROW", item_code="ITEM", uom="Box-10", custom_packing_detail="PACK")
		self.assertEqual(resolve([row], self.items, self.packings)["ROW"], "")

	def test_unpermitted_item_is_omitted(self):
		self.assertEqual(resolve([dict(name="ROW", item_code="OTHER")], self.items, self.packings), {})
