import unittest
from unittest.mock import patch
import frappe
from retail.retail_app.doctype.buy_x_get_y_promotion.buy_x_get_y_promotion import BuyXGetYPromotion
from retail.api import pos_sync


class TestBuyGetScope(unittest.TestCase):
	def doc(self, scope, **target):
		return frappe.get_doc(dict(doctype="Buy X Get Y Promotion", promotion_scope=scope,
			buy_qty=2, free_qty=1, same_product_only=1, products=[dict(add_to="Buy Item", **target)]))

	def test_each_scope_accepts_only_its_target(self):
		for scope, field in (("ITEM", "item"), ("CATEGORY", "item_group"), ("BRAND", "brand")):
			self.doc(scope, **{field: "TARGET"}).validate_products()
			for other in ("item", "item_group", "brand"):
				if other == field:
					continue
				with patch("frappe.throw", side_effect=frappe.ValidationError), self.assertRaises(frappe.ValidationError):
					self.doc(scope, **{other: "TARGET"}).validate_products()

	def test_free_rows_require_an_exact_item_for_every_buy_scope(self):
		for scope, field in (("ITEM", "item"), ("CATEGORY", "item_group"), ("BRAND", "brand")):
			doc = self.doc(scope, **{field: "TARGET"})
			doc.same_product_only = 0
			doc.append("products", {"add_to": "Free Item", "item": "GIFT"})
			doc.validate_products()
			doc.products[-1].brand = "WRONG"
			with patch("frappe.throw", side_effect=frappe.ValidationError), self.assertRaises(frappe.ValidationError):
				doc.validate_products()

	def test_brand_and_scope_exported_by_existing_api(self):
		doc = self.doc("BRAND", brand="BRAND")
		counter = frappe._dict(branch="BRANCH", name="COUNTER", counter_code="C001")
		with patch.object(pos_sync, "_pos_promotion_payload", return_value=({}, counter, None)), patch.object(pos_sync, "_get_promotion_docs", return_value=[doc]), patch.object(pos_sync, "get_system_timezone", return_value="Asia/Dubai"):
			result = pos_sync.get_pos_buy_x_get_y_promotions()["promotions"][0]
		self.assertEqual(result["promotion_scope"], "BRAND")
		self.assertEqual(result["products"][0]["brand"], "BRAND")

	def test_legacy_category_scope_ignores_free_row_position(self):
		from retail.promotions.api_payload import promotion_payload
		doc = self.doc(None, item_group="GROUP")
		doc.append("products", {"add_to": "Free Item", "item": "GIFT"})
		doc.products.insert(0, doc.products.pop())
		self.assertEqual(promotion_payload(doc)["promotion_scope"], "CATEGORY")
	def test_buy_and_free_items_include_barcodes_in_endpoint_response(self):
		doc = self.doc("ITEM", item="BUY")
		doc.append("products", {"add_to": "Free Item", "item": "FREE"})
		counter = frappe._dict(branch="BRANCH", name="COUNTER", counter_code="C001", warehouse="SHOP")
		items = [frappe._dict(item_code=code, item_name=code, barcode=code + "-BC",
			has_serial_no=0, disabled=0) for code in ("BUY", "FREE")]
		with patch.object(pos_sync, "_pos_promotion_payload", return_value=({}, counter, None)), \
			patch.object(pos_sync, "_get_promotion_docs", return_value=[doc]), \
			patch.object(frappe, "get_all", return_value=items):
			rows = pos_sync.get_pos_buy_x_get_y_promotions()["promotions"][0]["products"]
		self.assertEqual([row["barcode"] for row in rows], ["BUY-BC", "FREE-BC"])
		self.assertTrue(all("serial_no" in row and "serial_numbers" in row for row in rows))
