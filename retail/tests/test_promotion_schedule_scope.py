import unittest
from datetime import timedelta
from unittest.mock import patch
import frappe
from retail.promotions.schedule import is_active, pricing_rule_condition
from retail.promotions.promo_price import row_matches_item
from retail.retail_app.doctype.promo_price.promo_price import PromoPrice


class TestPromotionScheduleScope(unittest.TestCase):
	def test_dates_hours_and_overnight(self):
		for fields, time, expected in [
			({}, '03:00:00', True),
			({'active_from_time': '00:00', 'active_to_time': '02:00'}, timedelta(0), True),
			({'active_from_time': '09:00', 'active_to_time': '12:00'}, '12:00:00.5', False),
			({'active_from_time': '09:00', 'active_to_time': '12:00'}, '09:00:00', True),
			({'active_from_time': '09:00', 'active_to_time': '12:00'}, '12:00:01', False),
			({'active_from_time': '22:00', 'active_to_time': '02:00'}, '01:00:00', True),
			({'active_from_time': '22:00', 'active_to_time': '02:00'}, '12:00:00', False),
			({'active_from': '2026-10-15'}, '09:00:00', False),
			({'active_to': '2026-10-13'}, '09:00:00', False),
		]:
			promotion = frappe._dict(fields)
			with self.subTest(fields=fields, time=time):
				self.assertEqual(is_active(promotion, frappe._dict(posting_date='2026-10-14', posting_time=time)), expected)
				condition = pricing_rule_condition(promotion)
				if condition:
					self.assertEqual(bool(frappe.safe_eval(condition, None, {'posting_time': time})), expected)
		promotion = frappe._dict(active_from_time='09:00', active_to_time='12:00')
		self.assertTrue(frappe.safe_eval(pricing_rule_condition(promotion), None, {'posting_time': timedelta(hours=9)}))

	def test_brand_matching(self):
		row = frappe._dict(brand='BRAND', item='', item_group='', uom='')
		self.assertTrue(row_matches_item(row, frappe._dict(item_code='ITEM', brand='BRAND')))
		self.assertFalse(row_matches_item(row, frappe._dict(item_code='ITEM', brand='OTHER')))

	def test_scope_rejects_hidden_targets(self):
		row = frappe._dict(idx=1, item='ITEM', item_group='GROUP')
		with patch('frappe.throw', side_effect=frappe.ValidationError):
			with self.assertRaises(frappe.ValidationError):
				PromoPrice.validate_products(frappe._dict(promotion_scope='ITEM', products=[row]))

	def test_brand_and_whole_bill_discount(self):
		for scope, brand in [('BRAND', 'BRAND'), ('WHOLE BILL', '')]:
			row = frappe._dict(idx=1, item='', item_group='', brand=brand, current_price_including_tax=0,
				discount_percent=10, discount_amount=0, promo_price=0, promo_price_including_tax=0)
			PromoPrice.validate_products(frappe._dict(promotion_scope=scope, products=[row]))
			self.assertEqual(row.discount_percent, 10)
