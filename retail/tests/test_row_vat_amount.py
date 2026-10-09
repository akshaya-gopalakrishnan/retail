import unittest
from unittest.mock import patch

import frappe
from retail.domains.transactions.vat import set_row_vat_amounts


class Row(frappe._dict):
	@property
	def meta(self):
		return frappe._dict(has_field=lambda field: True)

	def precision(self, field):
		return 2


class TestRowVatAmount(unittest.TestCase):
	def test_qty_times_rate_ignores_stale_amounts(self):
		for amount, rates, expected in [
			(200, '{"VAT": 5}', 10),
			(-200, '{"VAT": 5}', -10),
			(0, '{"VAT": 5}', 0),
			(200, '{"VAT": 0}', 0),
			(99.99, '{"VAT": 5}', 5),
		]:
			with self.subTest(amount=amount, rates=rates):
				row = Row(item_code="ITEM", qty=2, rate=amount / 2, net_amount=0, amount=250, item_tax_rate=rates)
				doc = frappe._dict(items=[row])
				with patch.object(frappe, 'get_system_settings', return_value="Banker's Rounding"):
					set_row_vat_amounts(doc)
				self.assertEqual(row.custom_vat_amount, expected)

	def test_template_fallback_for_order_rows(self):
		row = Row(item_code="ITEM", doctype="Sales Order Item", qty=2, rate=100, amount=0)
		doc = frappe._dict(doctype="Sales Order", items=[row])
		with patch('retail.domains.transactions.vat.get_transaction_item_vat_rate', return_value=5), patch.object(
			frappe, 'get_system_settings', return_value="Banker's Rounding"
		):
			set_row_vat_amounts(doc)
		self.assertEqual(row.custom_vat_amount, 10)
