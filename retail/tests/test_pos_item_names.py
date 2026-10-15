import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from retail.pos_item_names import resolve_item_name, restore_item_names


class TestPOSItemNames(unittest.TestCase):
	def setUp(self):
		self.item = frappe._dict(name="I-1", item_name="Aqua Fresh Water 1.5 ltr", stock_uom="Nos",
			custom_retail_packing_detail=[
				frappe._dict(barcode="PACK4", packing_name="Aqua 1.5 LTR 1X4"),
				frappe._dict(barcode="PACK6", packing_name="Aqua 1.5 LTR 1X6")])

	def test_exact_barcode_selects_packing(self):
		self.assertEqual(resolve_item_name(self.item, {"barcode": "PACK4"}), "Aqua 1.5 LTR 1X4")
		self.assertEqual(resolve_item_name(self.item, {"barcode": "PACK6"}), "Aqua 1.5 LTR 1X6")

	def test_missing_barcode_uses_transaction_units(self):
		self.assertEqual(resolve_item_name(self.item, {"uom": "Pack", "conversion_factor": 4}),
			"Aqua Fresh Water 1.5 ltr - Pack x4")

	def test_unknown_barcode_does_not_generate_pack_name(self):
		self.assertEqual(resolve_item_name(self.item,
			{"barcode": "UNKNOWN", "uom": "Pack", "conversion_factor": 4}), self.item.item_name)

	def test_single_unit_keeps_original_name(self):
		self.assertEqual(resolve_item_name(self.item, {"uom": "Nos", "conversion_factor": 1}),
			self.item.item_name)

	def test_restore_changes_only_identity(self):
		line = frappe._dict(item_code="I-1", item_name=self.item.item_name, qty=2, rate=8,
			uom="Pack", conversion_factor=4)
		doc = SimpleNamespace(items=[line])
		with patch("retail.pos_item_names.frappe.get_cached_doc", return_value=self.item):
			restore_item_names(doc, {"items": [{"barcode": "PACK4"}]})
		self.assertEqual(line.item_name, "Aqua 1.5 LTR 1X4")
		self.assertEqual(line.barcode, "PACK4")
		self.assertEqual((line.qty, line.rate, line.uom, line.conversion_factor), (2, 8, "Pack", 4))
