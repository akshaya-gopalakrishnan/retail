import unittest
from unittest.mock import patch
from unittest.mock import MagicMock

import frappe
from retail.domains.item import scale_item_validation as scale


class TestScaleBarcodeGeneration(unittest.TestCase):
	def test_preview_is_reallocated_on_save_and_retained_on_second_hook(self):
		doc = MagicMock()
		values = {"custom_scale_item": 1, "custom_barcode": "9900001",
			"__retail_scale_barcode_preview": "9900001", "name": "NEW"}
		doc.get.side_effect = lambda key: values.get(key, getattr(doc, key, None))
		doc.get_doc_before_save.return_value = None
		with patch.object(scale, "get_unique_item_barcode", return_value="9900002") as allocate:
			scale.ensure_item_barcode(doc)
			self.assertEqual(doc.custom_barcode, "9900002")
			self.assertIsNone(getattr(doc, "__retail_scale_barcode_preview"))
			allocate.assert_called_once_with("NEW", scale_item=True)

	def test_starts_at_one_and_does_not_reserve_unsaved_numbers(self):
		with patch.object(frappe.db, "sql", return_value=[]):
			self.assertEqual(scale.get_unique_item_barcode(scale_item=True), "9900001")
			self.assertEqual(scale.get_unique_item_barcode(scale_item=True), "9900001")

	def test_fills_first_gap_and_checks_child_barcodes(self):
		with patch.object(frappe.db, "sql", side_effect=[
			[], [("9900001",), ("9900004",)], [("9900002",)],
		]) as query:
			self.assertEqual(scale.get_unique_item_barcode(scale_item=True), "9900003")
			self.assertIn("for update", query.call_args_list[0].args[0])
			self.assertTrue(all("for update" in call.args[0] for call in query.call_args_list))

	def test_exhaustion_does_not_fall_back_to_duplicates_or_zero(self):
		rows = [(f"99{number:05d}",) for number in range(1, 100000)]
		with patch.object(frappe.db, "sql", side_effect=[[], rows, []]):
			with self.assertRaises(frappe.ValidationError):
				scale.get_unique_item_barcode(scale_item=True)

	def test_normal_items_keep_random_barcode_generation(self):
		with patch.object(scale, "generate_random_barcode", return_value="1234567890123"), \
			patch.object(frappe.db, "exists", return_value=False), \
			patch.object(scale, "get_next_scale_barcode") as allocate:
			self.assertEqual(scale.get_unique_item_barcode(), "1234567890123")
			allocate.assert_not_called()
