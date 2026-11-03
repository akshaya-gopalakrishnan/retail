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

	def test_multiple_buy_items_are_allowed_in_the_same_group(self):
		doc = self.promotion("ITEM")
		doc.append("products", dict(add_to="Buy Item", item="OTHER", group_no=1, qty=3))
		doc.validate_products()
		self.assertEqual([(row.group_no, row.qty) for row in doc.products], [(1, 2), (1, 1), (1, 1), (1, 3)])

	def test_each_group_must_have_its_own_buy_and_reward(self):
		for side in ("Buy Item", "Free Item"):
			doc = self.promotion("ITEM")
			doc.append("products", dict(add_to=side, item="OTHER", group_no=2, qty=1))
			with patch("frappe.throw", side_effect=frappe.ValidationError), self.assertRaises(frappe.ValidationError):
				doc.validate_products()

	def test_each_row_requires_a_positive_quantity_and_whole_group_number(self):
		for field, value in (("qty", 0), ("qty", -1), ("qty", float("inf")), ("qty", float("nan")),
			("group_no", 0), ("group_no", -1), ("group_no", 1.5)):
			doc = self.promotion("ITEM")
			doc.products[0].set(field, value)
			with self.subTest(field=field, value=value), patch("frappe.throw", side_effect=frappe.ValidationError), self.assertRaises(frappe.ValidationError):
				doc.validate_products()

	def test_duplicate_buy_items_are_rejected_within_one_group(self):
		doc = self.promotion("ITEM")
		doc.append("products", dict(add_to="Buy Item", item="BUY", group_no=1, qty=2))
		with patch("frappe.throw", side_effect=frappe.ValidationError), self.assertRaises(frappe.ValidationError):
			doc.validate_products()

	def test_move_reward_to_another_group_and_keep_remaining_rewards(self):
		doc = self.promotion("ITEM")
		doc.append("products", dict(add_to="Buy Item", item="OTHER", group_no=2, qty=4))
		doc.append("products", dict(add_to="Free Item", item="CUP", group_no=2, qty=2))
		doc.append("products", dict(add_to="Free Item", item="PLATE", group_no=2, qty=1))
		doc.products[-2].group_no = 1
		doc.validate_products()
		from retail.promotions.buy_get_groups import group_rows
		groups = group_rows(doc)
		self.assertEqual([row.item for row in groups[1]["get"]], ["FREE-A", "FREE-B", "CUP"])
		self.assertEqual([row.item for row in groups[2]["get"]], ["PLATE"])

	def test_multi_buy_group_never_generates_independent_native_rules(self):
		doc = self.promotion("ITEM")
		doc.append("products", dict(add_to="Buy Item", item="OTHER", group_no=1, qty=3))
		doc.validate_products()
		module = "retail.retail_app.doctype.buy_x_get_y_promotion.buy_x_get_y_promotion."
		with patch(module + "retire_linked_schemes"), patch(module + "update_linked_schemes"), patch(module + "build_base_scheme") as build:
			doc.sync_promotional_scheme()
		build.assert_not_called()

	def test_migration_backfills_database_zero_defaults_from_original_quantities(self):
		from retail.patches import buy_get_item_groups
		doc = self.promotion("ITEM")
		doc.name = "LEGACY"
		for row in doc.products:
			row.qty = 0
			row.group_no = 1
		with patch.object(frappe, "reload_doc"), patch.object(frappe, "get_all", return_value=[doc.name]), \
			patch.object(frappe, "get_doc", return_value=doc), patch.object(frappe, "clear_document_cache"), \
			patch.object(frappe.db, "get_value", return_value=frappe._dict(group_no=1, qty=0)), \
			patch.object(frappe.db, "set_value") as write, patch("retail.promotions.history.record_revision"):
			buy_get_item_groups.execute()
		self.assertEqual([call.args[2] for call in write.call_args_list[:3]],
			[{"group_no": 1, "qty": 2}, {"group_no": 1, "qty": 1}, {"group_no": 1, "qty": 1}])
		self.assertEqual(write.call_args_list[-1].args[:3], (doc.doctype, doc.name, "modified"))

	def test_api_adds_groups_and_quantities_without_removing_existing_fields(self):
		from retail.api import pos_sync
		doc = self.promotion("ITEM")
		doc.name = "OFFER"
		doc.active_from = "2026-11-01"
		doc.active_to = "2026-11-30"
		doc.active_from_time = "09:00:00"
		doc.active_to_time = "23:00:00"
		doc.products[0].qty = 3
		doc.products[1].qty = 2
		counter = frappe._dict(branch="BRANCH", name="COUNTER", counter_code="C001")
		with patch.object(pos_sync, "_pos_promotion_payload", return_value=({}, counter, "CURSOR")), \
			patch.object(pos_sync, "_get_promotion_docs", return_value=[doc]) as load, \
			patch.object(pos_sync, "with_item_identity", side_effect=lambda data, warehouse: data):
			counter.warehouse = "WAREHOUSE"
			result = pos_sync.get_pos_buy_x_get_y_promotions()
		load.assert_called_once_with("Buy X Get Y Promotion", counter, "CURSOR")
		promotion = result["promotions"][0]
		self.assertEqual(promotion["active_from_time"], "09:00:00")
		self.assertEqual(promotion["active_to_time"], "23:00:00")
		self.assertEqual(promotion["active_from"], "2026-11-01")
		self.assertEqual(promotion["active_to"], "2026-11-30")
		self.assertEqual(promotion["buy_qty"], 2)
		self.assertEqual(promotion["free_qty"], 1)
		self.assertEqual([(row["group_no"], row["qty"]) for row in promotion["products"]], [(1, 3), (1, 2), (1, 1)])
		self.assertTrue(all({"name", "idx", "add_to", "item", "item_group", "brand", "uom", "matching_item_groups"} <= row.keys() for row in promotion["products"]))
		self.assertIsNone(doc.products[-1].get("qty"))
