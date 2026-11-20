import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retail.domains.purchase import sales_order_mapping as mapping


class TestSalesOrderPurchaseMapping(unittest.TestCase):
	def setUp(self):
		flags = patch.object(frappe.local, 'flags', frappe._dict(in_test=True), create=True)
		flags.start()
		self.addCleanup(flags.stop)

	def test_copied_sales_vat_is_cleared_before_purchase_calculation(self):
		for buying_rate in (14.29, 0):
			row = frappe._dict(rate=buying_rate, qty=1, sales_order='SO-18',
				custom_rate_including_vat=25, custom_amount_including_vat=25, custom_vat_amount=1.19)
			doc = SimpleNamespace(doctype='Purchase Order', items=[row])
			def calculate(target):
				self.assertIs(target, doc)
				self.assertEqual((row.custom_rate_including_vat, row.custom_amount_including_vat,
					row.custom_vat_amount), (0, 0, 0))
				self.assertEqual((row.rate, row.qty, row.sales_order), (buying_rate, 1, 'SO-18'))
			with patch.object(mapping, 'native_make_purchase_order', return_value=doc) as native, patch.object(
				mapping, 'set_vat_rates', side_effect=calculate
			) as vat:
				self.assertIs(mapping.make_purchase_order('SO-18', [{'item_code': 'I-49'}]), doc)
				native.assert_called_once_with('SO-18', [{'item_code': 'I-49'}], None)
				vat.assert_called_once()

	def test_empty_selection_does_not_calculate(self):
		with patch.object(mapping, 'native_make_purchase_order', return_value=None), patch.object(mapping, 'set_vat_rates') as vat:
			self.assertIsNone(mapping.make_purchase_order('SO-18'))
			vat.assert_not_called()
