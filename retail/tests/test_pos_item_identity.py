import unittest
from unittest.mock import patch

import frappe
from retail.pos_item_identity import with_item_identity


class TestPOSItemIdentity(unittest.TestCase):
	def test_nested_download_rows_keep_barcodes_and_selected_serials(self):
		packing = dict(item_code="ITEM", barcode="PACK", serial_no="SELECTED")
		rule = dict(item_code="ITEM")
		restriction = dict(item_code="ITEM")
		voucher = dict(voucher_code="VOUCHER", barcode="VOUCHER", serial_no=12,
			eligibility=[restriction])
		payload = dict(packings=[packing], pricing_rules=[dict(items=[rule])],
			gift_voucher_ledger=[voucher])
		items = [frappe._dict(item_code="ITEM", item_name="Product", barcode="BASE",
			has_serial_no=1, disabled=0)]
		with patch.object(frappe, "get_all", side_effect=[items,
			[frappe._dict(item_code="ITEM", name="AVAILABLE")]]) as query:
			self.assertIs(with_item_identity(payload, "SHOP"), payload)
		self.assertEqual(query.call_count, 2)
		for row in (packing, rule, restriction):
			self.assertEqual(row["serial_numbers"], ["AVAILABLE"])
			self.assertEqual(row["item_name"], "Product")
		self.assertEqual(packing["barcode"], "PACK")
		self.assertEqual(packing["serial_no"], "SELECTED")
		self.assertEqual(rule["barcode"], "BASE")
		self.assertEqual(rule["serial_no"], "")
		self.assertEqual((voucher["barcode"], voucher["serial_no"]), ("VOUCHER", 12))

	def test_no_products_does_not_query_items(self):
		with patch.object(frappe, "get_all") as query:
			with_item_identity({"customers": [{"name": "CUSTOMER"}]}, "SHOP")
		query.assert_not_called()
