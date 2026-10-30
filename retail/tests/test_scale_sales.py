import unittest
from unittest.mock import patch, MagicMock

import frappe
from retail.domains.item import packing_scan, scale_sales


class TestScaleSales(unittest.TestCase):
	def label(self, kind, payload, uom="Kg"):
		return scale_sales.decode_label("9900002" + payload + "7", kind, uom)

	def test_all_five_layouts_and_large_price(self):
		cases = [
			("Weight", "00500", 20, (0.5, 20, 10)),
			("Quantity", "00003", 20, (3, 20, 60)),
			("Price", "99999", 20, (49.9995, 20, 999.99)),
			("Weight+UPrice", "0050003050", 20, (0.5, 30.5, 15.25)),
			("Weight+TotPrice", "0050099999", 20, (0.5, 1999.98, 999.99)),
		]
		for kind, payload, rate, expected in cases:
			with self.subTest(kind=kind):
				values = scale_sales.sale_values(self.label(kind, payload), rate)
				self.assertEqual(tuple(values.values()), expected)

	def test_actual_scale_labels_with_five_price_digits(self):
		for barcode, qty, amount in [("992051300750010006", 0.75, 7.5),
			("992051300075010006", 0.075, 0.75)]:
			with self.subTest(barcode=barcode):
				label = scale_sales.decode_label(barcode, "Weight+UPrice", "Kg")
				self.assertEqual(label["master_barcode"], "9920513")
				self.assertEqual(scale_sales.sale_values(label, 99),
					{"qty": qty, "rate": 10, "amount": amount})
				label = scale_sales.decode_label(barcode, "Weight+TotPrice", "Kg")
				values = scale_sales.sale_values(label, 99)
				self.assertEqual(values["amount"], 10)
				self.assertAlmostEqual(values["qty"] * values["rate"], 10)

	def test_weight_precision_grams_and_price_only_fallback(self):
		self.assertEqual(self.label("Weight", "00001")["scale_qty"], 0.001)
		self.assertEqual(self.label("Weight", "00500", "Gram")["scale_qty"], 500)
		self.assertEqual(self.label("Weight", "01000")["scale_qty"], 1)
		self.assertEqual(scale_sales.sale_values(self.label("Price", "03050"), 0),
			{"qty": 1, "rate": 30.5, "amount": 30.5})
		values = scale_sales.sale_values(self.label("Price", "03050"), 7)
		self.assertAlmostEqual(values["qty"] * values["rate"], 30.5)
		values = scale_sales.sale_values(self.label("Weight+TotPrice", "0033303050"), 7)
		self.assertAlmostEqual(values["qty"] * values["rate"], 30.5)

	def test_invalid_labels_and_missing_rate(self):
		with patch.object(frappe, "throw", side_effect=ValueError), patch.object(scale_sales, "_", side_effect=lambda s: s):
			for kind, payload in [("Price", "003050"), ("Weight", "00000"),
				("Weight+UPrice", "00500003050"), ("Quantity", "0000X"), ("", "00500")]:
				with self.subTest(kind=kind, payload=payload), self.assertRaises(ValueError):
					self.label(kind, payload)
			with self.assertRaises(ValueError):
				scale_sales.sale_values(self.label("Weight", "00500"), 0)

	def test_only_checked_enabled_sales_master_is_resolved(self):
		with patch.object(frappe.db, "get_value", return_value=None) as lookup:
			self.assertIsNone(scale_sales.resolve_label("9900002005007"))
			self.assertEqual(lookup.call_args.args[1], {"custom_barcode": "9900002",
				"custom_scale_item": 1, "disabled": 0, "is_sales_item": 1})
		with patch.object(frappe.db, "get_value") as lookup:
			self.assertIsNone(scale_sales.resolve_label("9900002"))
			self.assertIsNone(scale_sales.resolve_label("ABCDEFG005007"))
			lookup.assert_not_called()

	def test_any_numeric_master_prefix_uses_checked_item_and_selected_type(self):
		item = frappe._dict(name="SCALE", stock_uom="Kg", scale_uom=None,
			custom_scale_barcode_type="Weight+UPrice")
		for master in ("1234567", "0000001", "8800002"):
			with self.subTest(master=master), \
				patch.object(frappe.db, "get_value", return_value=item) as lookup, \
				patch.object(frappe, "get_doc"):
				label = scale_sales.resolve_label(master + "00500030507")
				self.assertEqual(label["master_barcode"], master)
				self.assertEqual(label["scale_qty"], 0.5)
				self.assertEqual(label["scale_rate"], 30.5)
				self.assertEqual(lookup.call_args.args[1], {"custom_barcode": master,
					"custom_scale_item": 1, "disabled": 0, "is_sales_item": 1})

	def test_exact_matches_win_over_scale_decoding(self):
		with patch.object(packing_scan, "resolve_packing", return_value=None), \
			patch.object(frappe.db, "get_value", return_value=None), \
			patch.object(packing_scan, "standard_scan_barcode", return_value={"item_code": "EXACT"}), \
			patch.object(scale_sales, "resolve_label") as decode:
			self.assertEqual(packing_scan.scan_barcode("9900002005007"), {"item_code": "EXACT"})
			decode.assert_not_called()

	def test_final_digit_is_excluded_without_assuming_checksum_algorithm(self):
		first = scale_sales.decode_label("9900002005000", "Weight", "Kg")
		second = scale_sales.decode_label("9900002005009", "Weight", "Kg")
		self.assertEqual(first["scale_qty"], second["scale_qty"])

	def test_submitted_facts_are_not_decoded_or_repriced(self):
		doc = MagicMock(docstatus=1)
		doc.get_doc_before_save.return_value = frappe._dict(docstatus=1)
		with patch.object(scale_sales, "resolve_label") as resolve:
			scale_sales.prepare_precision(doc)
			resolve.assert_not_called()
			doc.get.assert_not_called()

	def test_fixed_price_promotion_does_not_replace_encoded_label_price(self):
		from retail.promotions import promo_price
		row = frappe._dict(rate=30.5, flags=frappe._dict(retail_scale_price=True))
		doc = MagicMock(doctype="Sales Invoice")
		doc.get.side_effect = lambda key: [row] if key == "items" else None
		with patch.object(promo_price, "get_active_promo_prices", return_value=[object()]), \
			patch.object(promo_price, "get_matching_inclusive_promo_row") as match:
			promo_price.apply_inclusive_promo_prices(doc)
			match.assert_not_called()
		self.assertEqual(row.rate, 30.5)
