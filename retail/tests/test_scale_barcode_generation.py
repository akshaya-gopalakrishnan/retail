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
		with patch.object(scale, "validate_unique_item_barcodes"), \
			patch.object(scale, "get_unique_item_barcode", return_value="9900002") as allocate:
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

	def test_normal_starts_at_one_and_has_valid_check_digit(self):
		with patch.object(frappe.db, "sql", return_value=[]):
			self.assertEqual(scale.get_unique_item_barcode(), "2000000000015")
			self.assertEqual(scale.get_unique_item_barcode(), "2000000000015")

	def test_normal_fills_gap_including_child_barcodes(self):
		with patch.object(frappe.db, "sql", side_effect=[
			[], [(scale.normal_barcode(1),), (scale.normal_barcode(4),)],
			[(scale.normal_barcode(2),)],
		]) as query:
			self.assertEqual(scale.get_unique_item_barcode(), "2000000000039")
			self.assertTrue(all("for update" in call.args[0] for call in query.call_args_list))

	def test_normal_ignores_unrelated_and_invalid_check_digits(self):
		with patch.object(frappe.db, "sql", side_effect=[
			[], [("2000000000010",), ("200abcdefghij",)], [],
		]):
			self.assertEqual(scale.get_unique_item_barcode(), "2000000000015")

	def test_normal_preview_is_reallocated_at_save(self):
		doc = frappe._dict(custom_scale_item=0, custom_barcode="2000000000015",
			__retail_normal_barcode_preview="2000000000015", name="NEW")
		doc.get_doc_before_save = lambda: None
		with patch.object(scale, "validate_unique_item_barcodes"), \
			patch.object(scale, "get_unique_item_barcode", return_value="2000000000022") as allocate:
			scale.ensure_item_barcode(doc)
			self.assertEqual(doc.custom_barcode, "2000000000022")
			self.assertIsNone(doc.__retail_normal_barcode_preview)
			allocate.assert_called_once_with("NEW", scale_item=False)

	def test_manual_barcode_is_preserved(self):
		doc = frappe._dict(custom_scale_item=0, custom_barcode="1234567890128", name="NEW")
		doc.get_doc_before_save = lambda: None
		with patch.object(frappe.db, "sql", return_value=[]), \
			patch.object(scale, "get_unique_item_barcode") as allocate:
			scale.ensure_item_barcode(doc)
			self.assertEqual(doc.custom_barcode, "1234567890128")
			allocate.assert_not_called()

	def test_manual_scale_barcode_requires_exactly_seven_ascii_digits(self):
		for barcode in ("123456", "12345678", "1234567890123", "123a567", "１２３４５６７"):
			with self.subTest(barcode=barcode):
				doc = frappe._dict(custom_scale_item=1, custom_barcode=barcode, name="NEW")
				doc.get_doc_before_save = lambda: None
				with self.assertRaises(frappe.ValidationError):
					scale.ensure_item_barcode(doc)

	def test_manual_scale_barcode_preserves_leading_zeroes_and_any_prefix(self):
		doc = frappe._dict(custom_scale_item=1, custom_barcode="0000001", name="NEW")
		doc.get_doc_before_save = lambda: None
		with patch.object(frappe.db, "sql", return_value=[]), \
			patch.object(scale, "get_unique_item_barcode") as allocate:
			scale.ensure_item_barcode(doc)
			self.assertEqual(doc.custom_barcode, "0000001")
			allocate.assert_not_called()

	def test_duplicates_rejected_across_master_child_and_packing_barcodes(self):
		for duplicate_table in range(3):
			for packing in (False, True):
				with self.subTest(table=duplicate_table, packing=packing):
					doc = frappe._dict(name="CURRENT", custom_retail_packing_detail=[
						frappe._dict(barcode="7654321")
					] if packing else [])
					responses = [[]] + [[]] * (3 if packing else 0) + [[]] * duplicate_table + [[("OTHER",)]]
					with patch.object(frappe.db, "sql", side_effect=responses), \
						self.assertRaises(frappe.ValidationError):
						scale.validate_unique_item_barcodes(doc, "1234567")

	def test_same_item_aliases_are_allowed_and_reads_are_locked(self):
		doc = frappe._dict(name="CURRENT", custom_retail_packing_detail=[frappe._dict(barcode="1234567")])
		with patch.object(frappe.db, "sql", return_value=[]) as query:
			scale.validate_unique_item_barcodes(doc, "1234567")
			self.assertEqual(query.call_count, 4)
			for call in query.call_args_list:
				self.assertIn("for update", call.args[0])
			for call in query.call_args_list[1:]:
				self.assertEqual(call.args[1], ("1234567", "CURRENT"))
