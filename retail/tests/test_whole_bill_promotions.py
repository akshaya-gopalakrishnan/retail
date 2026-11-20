import unittest
from unittest.mock import patch

import frappe
from erpnext.accounts.doctype.pricing_rule import utils as core
from retail.promotions.whole_bill import bill_totals, choose_rules


class TestWholeBillPromotions(unittest.TestCase):
	def setUp(self):
		self.rows = [frappe._dict(name="A", item_code="A", qty=3, price_list_rate=23.81, rate=11.91),
			frappe._dict(name="B", item_code="B", qty=15, price_list_rate=2.5, rate=1.25)]
		self.doc = frappe._dict(items=self.rows)
		self.whole = self.rule("WHOLE", promotional_scheme="SCHEME", priority=4, mixed_conditions=1, min_amt=100)
		self.args = frappe._dict(self.rows[0], stock_qty=3, currency="AED", price_list="Standard Selling")

	def rule(self, name, **fields):
		return frappe._dict(dict(dict(name=name, min_qty=0, max_qty=0, min_amt=0, max_amt=0,
			priority=0, currency="AED", rate_or_discount="Discount Percentage"), **fields))

	def choose(self, rules):
		with patch.object(frappe, "get_cached_doc", return_value=frappe._dict()):
			return choose_rules(core, self.args, self.doc, rules, {"SCHEME"})

	def test_two_individually_small_rows_qualify_together(self):
		self.assertAlmostEqual(bill_totals(self.doc, self.args)[1], 108.93)
		self.assertEqual(self.choose([self.whole])[0].name, "WHOLE")
		self.assertEqual(self.whole.min_amt, 100)  # Cached definitions are never mutated.

	def test_threshold_uses_original_prices_and_current_row_identity(self):
		self.args.update(child_docname="A", qty=1)
		self.assertAlmostEqual(bill_totals(self.doc, self.args)[1], 61.31)
		self.assertEqual(self.choose([self.whole]), [])

	def test_specific_rule_competes_by_numeric_priority(self):
		for scope in ("Item Code", "Brand", "Item Group"):
			with self.subTest(scope=scope):
				specific = self.rule("SPECIFIC", apply_on=scope, priority=1)
				self.assertEqual(self.choose([self.whole, specific])[0].name, "SPECIFIC")
				specific.priority = 5
				self.assertEqual(self.choose([specific, self.whole])[0].name, "WHOLE")

	def test_ineligible_high_priority_specific_rule_does_not_block_whole_bill(self):
		self.assertEqual(self.choose([self.rule("SPECIFIC", priority=1, min_qty=10), self.whole])[0].name, "WHOLE")

	def test_whole_bill_winner_does_not_overwrite_other_rows_winners(self):
		winner = self.choose([self.whole])[0]
		self.assertFalse(winner.mixed_conditions)
		self.assertFalse(winner.apply_rule_on_other_items)

	def test_duplicate_items_are_counted_per_row_and_free_rows_do_not_qualify_bill(self):
		self.rows[1].item_code = "A"
		self.assertAlmostEqual(bill_totals(self.doc, self.args)[1], 108.93)
		self.rows[1].custom_foc_parent = "A"
		self.assertEqual(self.choose([self.whole]), [])


class TestInclusivePromotionPriority(unittest.TestCase):
    def test_fixed_price_does_not_override_higher_priority_whole_bill_percentage(self):
        from retail.promotions.promo_price import get_matching_inclusive_promo_row
        item = frappe._dict(name='A', item_code='A', qty=3, uom='Nos', price_list_rate=23.81, rate=11.91)
        doc = frappe._dict(doctype='Sales Invoice', items=[item,
            frappe._dict(name='B', item_code='B', qty=15, price_list_rate=2.5, rate=1.25)])
        fixed_row = frappe._dict(item='A', promo_price_including_tax=20)
        fixed = frappe._dict(promotion_scope='ITEM', products=[fixed_row], priority=3, modified='2026-11-18')
        whole = frappe._dict(promotion_scope='WHOLE BILL', products=[frappe._dict(discount_percent=50)],
            priority=2, min_sales_value=100, modified='2026-11-18')
        self.assertIsNone(get_matching_inclusive_promo_row(doc, item, [fixed, whole]))
        fixed.priority = 1
        self.assertIs(get_matching_inclusive_promo_row(doc, item, [fixed, whole]), fixed_row)


    def test_priority_applies_without_a_whole_bill_candidate(self):
        with patch.object(frappe, 'get_cached_doc', return_value=frappe._dict()):
            rules = [frappe._dict(name=name, priority=priority, currency='AED', min_qty=0,
                max_qty=0, min_amt=0, max_amt=0) for name, priority in [('BRAND',2),('GROUP',3),('ITEM',1)]]
            args = frappe._dict(qty=1, stock_qty=1, price_list_rate=10, currency='AED')
            self.assertEqual(choose_rules(core,args,frappe._dict(items=[]),rules,set())[0].name,'ITEM')
