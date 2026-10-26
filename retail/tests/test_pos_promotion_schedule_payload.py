import json
import unittest
from datetime import date, time, timedelta
from unittest.mock import patch

import frappe
from retail.api import gift_vouchers, pos_sync
from retail.promotions.api_payload import promotion_payload


class TestPOSPromotionSchedulePayload(unittest.TestCase):
	def setUp(self):
		additional = patch.object(pos_sync, "_additional_pos_promotions", return_value={})
		additional.start()
		self.addCleanup(additional.stop)

	def doc(self, doctype="Promo Price", **fields):
		values = dict(doctype=doctype, name="PROMOTION", company="COMPANY", warehouse="WAREHOUSE",
			active_from=date(2026, 10, 14), active_to=None,
			active_from_time=timedelta(hours=9), active_to_time=time(12), products=[])
		values.update(fields)
		return frappe.get_doc(values)

	def test_dates_times_and_midnight_have_stable_json_types(self):
		for doctype in ("Promo Price", "Buy X Get Y Promotion", "Gift Voucher Promotion"):
			with self.subTest(doctype=doctype):
				result = promotion_payload(self.doc(doctype))
				self.assertEqual(result["active_from"], "2026-10-14")
				self.assertIsNone(result["active_to"])
				self.assertEqual(result["active_from_time"], "09:00:00")
				self.assertEqual(result["active_to_time"], "12:00:00")
		for value in (timedelta(0), time(0), "00:00:00"):
			self.assertEqual(promotion_payload(self.doc(active_from_time=value))["active_from_time"], "00:00:00")
		for value in (None, ""):
			self.assertIsNone(promotion_payload(self.doc(active_from_time=value))["active_from_time"])

	def test_scope_targets_and_schedule_are_exported_without_mutation(self):
		for scope, targets in (("ITEM", {"item": "ITEM"}), ("CATEGORY", {"item_group": "GROUP"}),
			("BRAND", {"brand": "BRAND"}), ("WHOLE BILL", {})):
			doc = self.doc(promotion_scope=scope, disabled=1, products=[dict(discount_percent=10, **targets)])
			counter = frappe._dict(branch="BRANCH", name="COUNTER", counter_code="C001")
			with patch.object(pos_sync, "_pos_promotion_payload", return_value=({}, counter, None)), patch.object(pos_sync, "_get_promotion_docs", return_value=[doc]), patch.object(pos_sync, "get_system_timezone", return_value="Asia/Dubai"):
				result = pos_sync.get_pos_promo_prices()
			self.assertEqual(result["server_timezone"], "Asia/Dubai")
			promotion = result["promotions"][0]
			self.assertEqual(promotion["promotion_scope"], scope)
			self.assertEqual(promotion["active_from_time"], "09:00:00")
			for key, value in targets.items():
				self.assertEqual(promotion["products"][0][key], value)
			self.assertEqual(doc.active_from_time, timedelta(hours=9))
			json.loads(frappe.as_json(result))

	def test_legacy_scope_is_inferred(self):
		self.assertEqual(promotion_payload(self.doc(products=[{"item_group": "GROUP"}]))["promotion_scope"], "CATEGORY")
		self.assertEqual(promotion_payload(self.doc(products=[{"item": "ITEM"}]))["promotion_scope"], "ITEM")

	def test_buy_get_response_has_separate_hours_and_timezone(self):
		counter = frappe._dict(branch="BRANCH", name="COUNTER", counter_code="C001")
		with patch.object(pos_sync, "_pos_promotion_payload", return_value=({}, counter, None)), patch.object(pos_sync, "_get_promotion_docs", return_value=[self.doc("Buy X Get Y Promotion")]), patch.object(pos_sync, "get_system_timezone", return_value="Asia/Dubai"):
			result = pos_sync.get_pos_buy_x_get_y_promotions()
		self.assertEqual(result["promotions"][0]["active_to_time"], "12:00:00")
		self.assertEqual(result["server_timezone"], "Asia/Dubai")

	def test_voucher_snapshot_preserves_company_scope_and_cursor(self):
		counter = frappe._dict(company="COMPANY", warehouse="WAREHOUSE")
		docs = {"matched": self.doc("Gift Voucher Promotion", enabled=0),
			"other": self.doc("Gift Voucher Promotion", company="OTHER")}
		with patch.object(gift_vouchers, "context", return_value=(frappe._dict(modified_after="CURSOR"), counter)), patch.object(frappe, "get_all", return_value=list(docs)) as lookup, patch.object(frappe, "get_doc", side_effect=lambda dt, name: docs[name]), patch.object(gift_vouchers, "get_system_timezone", return_value="Asia/Dubai"):
			result = gift_vouchers.get_gift_voucher_promotions()
		self.assertEqual(lookup.call_args.kwargs["filters"], {"modified": [">", "CURSOR"]})
		self.assertEqual(len(result["promotions"]), 1)
		self.assertEqual(result["promotions"][0]["enabled"], 0)
		self.assertEqual(result["promotions"][0]["active_from_time"], "09:00:00")
		self.assertEqual(result["server_timezone"], "Asia/Dubai")
		self.assertIn("server_time", result)

	def test_category_targets_include_descendants_in_existing_product_rows(self):
		doc = self.doc("Buy X Get Y Promotion", promotion_scope="CATEGORY",
			products=[{"add_to": "Buy Item", "item_group": "DRINKS"}])
		counter = frappe._dict(branch="BRANCH", name="COUNTER", counter_code="C001")
		with patch.object(pos_sync, "_pos_promotion_payload", return_value=({}, counter, None)), patch.object(pos_sync, "_get_promotion_docs", return_value=[doc]), patch.object(pos_sync, "matching_item_groups", return_value=["DRINKS", "JUICE"]) as groups:
			row = pos_sync.get_pos_buy_x_get_y_promotions()["promotions"][0]["products"][0]
		groups.assert_called_once_with("DRINKS")
		self.assertEqual(row["matching_item_groups"], ["DRINKS", "JUICE"])
		self.assertEqual(row["item_group"], "DRINKS")

	def test_voucher_exclusion_descendants_are_exported_without_mutation(self):
		doc = self.doc("Gift Voucher Promotion", excluded_item_groups=[{"item_group": "DRINKS"}])
		with patch("retail.promotions.api_payload.matching_item_groups", return_value=["DRINKS", "JUICE"]):
			row = promotion_payload(doc)["excluded_item_groups"][0]
		self.assertEqual(row["matching_item_groups"], ["DRINKS", "JUICE"])
		self.assertIsNone(doc.excluded_item_groups[0].get("matching_item_groups"))

	def test_group_resolution_includes_selected_group_and_descendants(self):
		from retail.promotions.api_payload import matching_item_groups
		with patch.object(frappe.db, "get_value", return_value=frappe._dict(lft=2, rgt=7)), patch.object(frappe, "get_all", return_value=["DRINKS", "JUICE"]) as lookup:
			self.assertEqual(matching_item_groups("DRINKS"), ["DRINKS", "JUICE"])
		self.assertEqual(lookup.call_args.kwargs["filters"], {"lft": [">=", 2], "rgt": ["<=", 7]})
		with patch.object(frappe.db, "get_value", return_value=None):
			self.assertEqual(matching_item_groups("DRINKS"), ["DRINKS"])
		self.assertEqual(matching_item_groups(None), [])

	def test_master_data_keeps_existing_promotions_with_all_new_fields(self):
		from contextlib import ExitStack
		from unittest.mock import MagicMock
		counter = MagicMock(company="COMPANY", warehouse="WAREHOUSE", branch="BRANCH", counter_code="C001")
		counter.name = "COUNTER"
		counter.as_dict.return_value = {"name": "COUNTER"}
		promo = self.doc(promotion_scope="WHOLE BILL", products=[{"discount_percent": 10}])
		buy = self.doc("Buy X Get Y Promotion", promotion_scope="BRAND", buy_qty=2, free_qty=1,
			products=[{"add_to": "Buy Item", "brand": "BRAND"}])
		with ExitStack() as stack:
			stack.enter_context(patch.object(pos_sync, "_assert_pos_user"))
			stack.enter_context(patch.object(pos_sync, "_as_dict", return_value=frappe._dict(branch="BRANCH", counter_code="C001", modified_after="CURSOR")))
			stack.enter_context(patch.object(pos_sync, "_counter", return_value=counter))
			stack.enter_context(patch.object(pos_sync, "_get_promotion_docs", side_effect=lambda dt, *_: [promo] if dt == "Promo Price" else [buy]))
			stack.enter_context(patch.object(pos_sync, "get_system_timezone", return_value="Asia/Dubai"))
			stack.enter_context(patch.object(frappe, "get_all", return_value=[]))
			stack.enter_context(patch.object(frappe.db, "has_column", return_value=False))
			for name, value in {"_get_current_stock_by_item": {}, "_pos_tax_config": {}, "_company_bill_format": {}, "_customer_master_rows": [], "_operator_master_rows": [], "_pos_item_prices": []}.items():
				stack.enter_context(patch.object(pos_sync, name, return_value=value))
			stack.enter_context(patch.object(gift_vouchers, "get_gift_voucher_promotions", return_value={"promotions": [promotion_payload(self.doc("Gift Voucher Promotion"))]}))
			result = pos_sync.get_pos_master_data("BRANCH", "C001", "CURSOR")
		self.assertEqual(result["server_timezone"], "Asia/Dubai")
		self.assertEqual(result["promo_prices"][0]["promotion_scope"], "WHOLE BILL")
		self.assertEqual(result["buy_x_get_y_promotions"][0]["promotion_scope"], "BRAND")
		self.assertEqual(result["buy_x_get_y_promotions"][0]["products"][0]["brand"], "BRAND")
		self.assertEqual(result["gift_voucher_promotions"][0]["active_from_time"], "09:00:00")
