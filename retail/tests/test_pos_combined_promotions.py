import unittest
from unittest.mock import patch

import frappe

from retail.api import pos_sync
from retail.promotions import pos_download


class TestPOSCombinedPromotions(unittest.TestCase):
	def setUp(self):
		self.counter = frappe._dict(branch="Karama", counter_code="counter01", name="Counter 01",
			company="nesto", warehouse="Stores - N")

	def test_endpoint_retains_legacy_array_and_adds_sibling_arrays(self):
		promo = frappe.get_doc(dict(doctype="Promo Price", name="Original", products=[], disabled=0))
		additional = {key: [{"name": key}] for key in ("buy_x_get_y_promotions",
			"gift_voucher_promotions", "loyalty_programs", "pricing_rules", "promotional_schemes",
			"loyalty_point_entries")}
		with patch.object(pos_sync, "_pos_promotion_payload", return_value=({}, self.counter, "CURSOR")), \
			patch.object(pos_sync, "_get_promotion_docs", return_value=[promo]), \
			patch.object(pos_sync, "_additional_pos_promotions", return_value=additional) as loader:
			result = pos_sync.get_pos_promo_prices("Karama", "counter01", "CURSOR")
		loader.assert_called_once_with(self.counter, "CURSOR")
		self.assertEqual([row["name"] for row in result["promotions"]], ["Original"])
		for key, rows in additional.items():
			self.assertEqual(result[key], rows)

	def test_combined_download_forwards_scope_and_cursor(self):
		from retail.api import gift_vouchers
		with patch.object(pos_sync, "get_pos_buy_x_get_y_promotions", return_value={"promotions": ["BUY"]}) as buy, \
			patch.object(gift_vouchers, "get_gift_voucher_promotions", return_value={"promotions": ["GIFT"]}) as gift, \
			patch.object(pos_download, "_voucher_snapshot", return_value={}), \
			patch.object(pos_download, "_retail_scheme_sources", return_value={}), \
			patch.object(pos_download, "_loyalty_programs", return_value=["LOYALTY"]), \
			patch.object(pos_download, "_loyalty_snapshot", return_value={"loyalty_point_entries": ["ENTRY"]}) as snapshot, \
			patch.object(pos_download, "_selling_documents", return_value=[]):
			result = pos_download.additional_promotions(self.counter, "CURSOR")
		args = dict(branch="Karama", counter_code="counter01", modified_after="CURSOR")
		buy.assert_called_once_with(**args)
		gift.assert_called_once_with(args)
		self.assertEqual(result["buy_x_get_y_promotions"], ["BUY"])
		self.assertEqual(result["gift_voucher_promotions"], ["GIFT"])
		self.assertEqual(result["loyalty_programs"], ["LOYALTY"])
		snapshot.assert_called_once_with(self.counter)
		self.assertEqual(result["loyalty_point_entries"], ["ENTRY"])

	def test_scope_and_incremental_filter_include_disabled_and_future_documents(self):
		docs = {name: frappe._dict(name=name, company=company, warehouse=warehouse)
			for name, company, warehouse in (("global", "", ""), ("local", "nesto", "Stores - N"),
				("company", "OTHER", ""), ("warehouse", "nesto", "OTHER"))}
		with patch.object(frappe, "get_all", return_value=list(docs)) as query, \
			patch.object(frappe, "get_doc", side_effect=lambda dt, name: docs[name]):
			rows = list(pos_download._scoped_documents("Pricing Rule", self.counter, "CURSOR", selling=1))
		self.assertEqual([doc.name for doc in rows], ["global", "local"])
		self.assertEqual(query.call_args.kwargs["filters"], {"selling": 1, "modified": [">", "CURSOR"]})

	def test_generated_retail_rules_and_scheme_are_not_applied_twice(self):
		sources = {"SCHEME": dict(source_promotion_type="Buy X Get Y Promotion", source_promotion="BUY")}
		for doctype, name, scheme, expected in (("Pricing Rule", "RULE", "SCHEME", 0),
			("Pricing Rule", "INDEPENDENT", "OTHER", 1), ("Promotional Scheme", "SCHEME", None, 0)):
			with self.subTest(doctype=doctype, name=name):
				doc = frappe.get_doc(dict(doctype=doctype, name=name, disable=1, selling=1,
					promotional_scheme=scheme, item_groups=[dict(item_group="Drinks")]))
				with patch.object(pos_download, "_scoped_documents", return_value=[doc]), \
					patch.object(pos_download, "matching_item_groups", return_value=["Drinks", "Juice"]):
					row = pos_download._selling_documents(doctype, self.counter, None, sources)[0]
				self.assertEqual(row["apply_in_pos"], expected)
				self.assertEqual(row["disabled"], 1)
				self.assertEqual(row["item_groups"][0]["matching_item_groups"], ["Drinks", "Juice"])
				self.assertIsNone(doc.item_groups[0].get("matching_item_groups"))
				if scheme == "SCHEME":
					self.assertEqual(row["source_promotion"], "BUY")

	def test_buy_category_or_brand_can_reward_a_different_specific_item(self):
		for scope, target in (("ITEM", {"item": "TEA"}), ("CATEGORY", {"item_group": "Tea"}),
			("BRAND", {"brand": "Tea Brand"})):
			with self.subTest(scope=scope):
				doc = frappe.get_doc(dict(doctype="Buy X Get Y Promotion", name="BUY", promotion_scope=scope,
					buy_qty=1, free_qty=1, same_product_only=0, products=[
						dict(add_to="Buy Item", uom="Nos", **target),
						dict(add_to="Free Item", item="MUFFIN", uom="Nos")]))
				with patch.object(pos_sync, "_pos_promotion_payload", return_value=({}, self.counter, None)), \
					patch.object(pos_sync, "_get_promotion_docs", return_value=[doc]), \
					patch.object(pos_sync, "matching_item_groups", side_effect=lambda group: [group] if group else []):
					row = pos_sync.get_pos_buy_x_get_y_promotions()["promotions"][0]
				self.assertEqual(row["promotion_scope"], scope)
				self.assertEqual(row["same_product_only"], 0)
				self.assertEqual(row["products"][1]["item"], "MUFFIN")

	def test_loyalty_full_download_keeps_future_program_and_collection_rules(self):
		doc = frappe.get_doc(dict(doctype="Loyalty Program", name="Future", from_date="2030-01-01",
			to_date=None, company="nesto", conversion_factor=1, collection_rules=[
				dict(tier_name="Standard", min_spent=0, collection_factor=20)]))
		with patch.object(pos_download, "_scoped_documents", return_value=[doc]):
			row = pos_download._loyalty_programs(self.counter, None)[0]
		self.assertEqual(row["from_date"], "2030-01-01")
		self.assertEqual(row["collection_rules"][0]["collection_factor"], 20)

	def loyalty_snapshot(self, entries):
		with patch.object(frappe, "get_all", return_value=entries) as query, \
			patch.object(pos_download, "nowdate", return_value="2026-10-22"), \
			patch("retail.loyalty.today", return_value="2026-10-22"):
			result = pos_download._loyalty_snapshot(self.counter)
		query.assert_called_once()
		self.assertEqual(query.call_args.kwargs["filters"], {"company": "nesto"})
		self.assertNotIn("customer_loyalty_balances", result)
		return result

	def entry(self, name, points, **kwargs):
		return frappe._dict(name=name, customer="C-1", loyalty_program="PROGRAM", company="nesto",
			loyalty_points=points, posting_date=kwargs.get("posting_date", "2026-10-01"),
			expiry_date=kwargs.get("expiry_date", "2026-12-31"),
			redeem_against=kwargs.get("redeem_against"), invoice_type="Sales Invoice", invoice="INV")

	def test_loyalty_balances_use_unexpired_buckets_and_signed_movements(self):
		entries = [self.entry("EARN", 100), self.entry("SPEND", -30, redeem_against="EARN"),
			self.entry("RESTORE", 5, redeem_against="EARN"),
			self.entry("EXPIRED", 200, expiry_date="2026-10-21"),
			self.entry("FUTURE", 300, posting_date="2026-10-23"),
			self.entry("NO-EXPIRY", 400, expiry_date=None)]
		result = self.loyalty_snapshot(entries)
		self.assertEqual(len(result["loyalty_point_entries"]), 6)
		balance = result["loyalty_point_entries"][0]
		self.assertEqual(balance["available_points"], 75)
		self.assertEqual(balance["earned_points"], 700)
		self.assertEqual(balance["used_points"], 25)
		self.assertEqual(balance["expired_points"], 200)
		self.assertEqual(result["loyalty_snapshot"],
			{"mode": "full", "company": "nesto", "as_of_date": "2026-10-22"})

	def test_loyalty_snapshot_clears_deleted_entries_without_synthetic_rows(self):
		first = self.loyalty_snapshot([self.entry("EARN", 10)])
		self.assertEqual(first["loyalty_point_entries"][0]["available_points"], 10)
		after_cancellation = self.loyalty_snapshot([])
		self.assertEqual(after_cancellation["loyalty_point_entries"], [])

	def test_loyalty_movements_do_not_cross_customer_or_program(self):
		other_customer = self.entry("OTHER-CUSTOMER", -70, redeem_against="EARN")
		other_customer.customer = "C-2"
		other_program = self.entry("OTHER-PROGRAM", -40, redeem_against="EARN")
		other_program.loyalty_program = "OTHER"
		result = self.loyalty_snapshot([self.entry("EARN", 100), other_customer, other_program])
		self.assertEqual(result["loyalty_point_entries"][0]["available_points"], 100)

	def test_customer_program_totals_repeat_on_each_entry_without_replacing_ledger_fields(self):
		entries = [self.entry("EARN", 100), self.entry("SPEND", -20, redeem_against="EARN")]
		result = self.loyalty_snapshot(entries)
		for row in result["loyalty_point_entries"]:
			self.assertEqual((row["earned_points"], row["used_points"], row["expired_points"], row["available_points"]),
				(100, 20, 0, 80))
			self.assertEqual(row["as_of_date"], "2026-10-22")
		self.assertEqual(result["loyalty_point_entries"][1]["loyalty_points"], -20)
		self.assertEqual(result["loyalty_point_entries"][1]["redeem_against"], "EARN")

	def test_expired_points_exclude_used_points_and_restore_into_original_bucket(self):
		entries = [self.entry("EXPIRED", 100, expiry_date="2026-10-21"),
			self.entry("SPEND", -30, redeem_against="EXPIRED"),
			self.entry("RESTORE", 10, redeem_against="EXPIRED")]
		balance = self.loyalty_snapshot(entries)["loyalty_point_entries"][0]
		self.assertEqual(balance["earned_points"], 100)
		self.assertEqual(balance["used_points"], 20)
		self.assertEqual(balance["expired_points"], 80)
		self.assertEqual(balance["available_points"], 0)

	def test_expiry_today_stays_available_and_future_earning_is_not_earned_yet(self):
		entries = [self.entry("TODAY", 50, expiry_date="2026-10-22"),
			self.entry("FUTURE", 200, posting_date="2026-10-23")]
		balance = self.loyalty_snapshot(entries)["loyalty_point_entries"][0]
		self.assertEqual(balance["earned_points"], 50)
		self.assertEqual(balance["used_points"], 0)
		self.assertEqual(balance["expired_points"], 0)
		self.assertEqual(balance["available_points"], 50)
