import unittest
from unittest.mock import patch

import frappe

from retail.promotions.promo_price import get_purchase_prices, synchronize_discount
from retail.promotions.scheme_builder import validate_product_row
from retail.retail_app.doctype.promo_price.promo_price import PromoPrice


class TestPromoPriceInputs(unittest.TestCase):
	def row(self, **values):
		return frappe._dict(idx=1, item="TEST", item_group="", current_price_including_tax=10,
			discount_percent=0, discount_amount=0, discount_input="", **values)

	def test_amount_is_converted_to_percentage(self):
		row = self.row()
		row.update(discount_amount=1, discount_input="Amount")
		synchronize_discount(row)
		self.assertEqual(row.discount_percent, 10)
		self.assertEqual(row.discount_amount, 1)

	def test_percentage_is_converted_to_amount_and_remains_authoritative(self):
		row = self.row()
		row.update(discount_percent=10, discount_amount=7, discount_input="Percent")
		synchronize_discount(row)
		self.assertEqual(row.discount_amount, 1)
		row.current_price_including_tax = 20
		synchronize_discount(row)
		self.assertEqual(row.discount_amount, 2)
		self.assertEqual(row.discount_percent, 10)

	def test_clear_selected_input_unlocks_both(self):
		for source in ("Amount", "Percent"):
			row = self.row()
			row.update(discount_percent=10, discount_amount=1, discount_input=source)
			row["discount_amount" if source == "Amount" else "discount_percent"] = 0
			synchronize_discount(row)
			self.assertEqual((row.discount_percent, row.discount_amount, row.discount_input), (0, 0, ""))

	def test_server_rejects_invalid_discounts_and_both_targets(self):
		with patch("frappe.throw", side_effect=frappe.ValidationError):
			for values in (
				{"discount_percent": 101}, {"discount_percent": -1},
				{"discount_amount": -1}, {"discount_amount": 11, "discount_input": "Amount"},
				{"discount_amount": 1, "discount_input": "Amount", "current_price_including_tax": 0},
				{"item": "", "item_group": "GROUP", "discount_amount": 1, "discount_input": "Amount"},
			):
				row = self.row()
				row.update(values)
				with self.subTest(values=values), self.assertRaises(frappe.ValidationError):
					synchronize_discount(row)
			row = self.row()
			row.item_group = "GROUP"
			with self.assertRaises(frappe.ValidationError):
				validate_product_row(row)

	def test_group_percentage_requires_no_item_price(self):
		row = self.row()
		row.update(item="", item_group="GROUP", current_price_including_tax=0, discount_percent=10)
		synchronize_discount(row)
		self.assertEqual((row.discount_percent, row.discount_amount), (10, 0))

	def test_fixed_price_cannot_be_combined_with_discount(self):
		row = self.row()
		row.update(discount_amount=1, discount_input="Amount", promo_price=8, promo_price_including_tax=8.4)
		with patch("retail.retail_app.doctype.promo_price.promo_price.get_purchase_prices", return_value={}), patch("frappe.throw", side_effect=frappe.ValidationError):
			with self.assertRaises(frappe.ValidationError):
				PromoPrice.validate_products(frappe._dict(products=[row]))

	def test_purchase_prices_use_purchase_vat_and_packing_uom(self):
		item = frappe._dict(stock_uom="Nos", custom_purchase_net_rate=4,
			custom_purchase_gross_rate=0, custom_purchase_tax_template="PURCHASE VAT")
		with patch("frappe.db.get_value", return_value=item), patch("retail.promotions.promo_price.get_item_tax_rate", return_value=5):
			self.assertEqual(get_purchase_prices("TEST", "Nos"), {"purchase_price":4, "purchase_price_including_tax":4.2})
		packing = frappe._dict(conversion_factor=6, purchase_net_rate=20, purchase_gross_rate=21)
		with patch("frappe.db.get_value", side_effect=[item, packing]), patch("retail.promotions.promo_price.get_item_tax_rate", return_value=5):
			self.assertEqual(get_purchase_prices("TEST", "Box"), {"purchase_price":20, "purchase_price_including_tax":21})
