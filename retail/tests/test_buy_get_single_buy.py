import unittest
from unittest.mock import patch
import frappe


class TestBuyGetSingleBuy(unittest.TestCase):
	def promotion(self, scope):
		field = {"ITEM": "item", "CATEGORY": "item_group", "BRAND": "brand"}[scope]
		return frappe.get_doc(dict(doctype="Buy X Get Y Promotion", promotion_scope=scope,
			buy_qty=2, free_qty=1, same_product_only=0, products=[
				dict(add_to="Buy Item", **{field: "BUY"}),
				dict(add_to="Free Item", item="FREE-A"),
				dict(add_to="Free Item", item="FREE-B")]))

	def test_one_buy_can_have_multiple_specific_free_items(self):
		for scope in ("ITEM", "CATEGORY", "BRAND"):
			with self.subTest(scope=scope):
				self.promotion(scope).validate_products()

	def test_second_buy_is_rejected_even_for_a_different_product(self):
		for scope in ("ITEM", "CATEGORY", "BRAND"):
			with self.subTest(scope=scope):
				doc = self.promotion(scope)
				field = {"ITEM": "item", "CATEGORY": "item_group", "BRAND": "brand"}[scope]
				doc.append("products", dict(add_to="Buy Item", **{field: "OTHER"}))
				with patch("frappe.throw", side_effect=frappe.ValidationError) as throw, self.assertRaises(frappe.ValidationError):
					doc.validate_products()
				self.assertIn("Only one Buy Item", throw.call_args.args[0])
