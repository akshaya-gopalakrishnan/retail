import unittest
from unittest.mock import patch

import frappe
from retail.print_barcodes import add_barcode_lines, item_barcode_for_print


class TestPrintBarcodes(unittest.TestCase):
	def test_saved_barcode_requires_no_master_lookup(self):
		with patch('retail.print_barcodes.frappe') as db:
			self.assertEqual(item_barcode_for_print({'barcode': '000123', 'custom_item_barcode': 'other'}), '000123')
			self.assertEqual(item_barcode_for_print({'custom_item_barcode': 'PACK-10'}), 'PACK-10')
			db.db.get_value.assert_not_called()

	def test_visible_names_only_and_repeatable(self):
		source = '<img alt="{{ item.item_name }}"><div>{{ item.item_name or item.item_code }}</div>'
		result = add_barcode_lines(source)
		self.assertIn('<img alt="{{ item.item_name }}">', result)
		self.assertIn('item_barcode_for_print(item)', result)
		self.assertEqual(result.count('retail-item-barcode'), 1)
		self.assertEqual(add_barcode_lines(result), result)
		self.assertEqual(add_barcode_lines('{{ doc.item_name }}'), '{{ doc.item_name }}')

	def test_promotion_rows_use_item_reference(self):
		result = add_barcode_lines('{{ frappe.db.get_value("Item", row.item, "item_name") or "" }}')
		self.assertIn('item_barcode_for_print(row)', result)
