import unittest
import frappe
from erpnext.accounts.report.gross_profit.gross_profit import GrossProfitGenerator


class TestGrossProfitPostedCost(unittest.TestCase):
	def cost(self, entries, qty=1):
		generator = GrossProfitGenerator.__new__(GrossProfitGenerator)
		rows = [frappe._dict(voucher_type='Sales Invoice', voucher_no='SI',
			voucher_detail_no='ROW', **entry) for entry in entries]
		return generator.calculate_buying_amount_from_sle(
			frappe._dict(qty=qty), rows, 'Sales Invoice', 'SI', 'ROW', 'ITEM')

	def test_uses_posted_movement_not_neighbour_balance(self):
		self.assertAlmostEqual(self.cost([
			dict(qty=-1, stock_value=151.9, stock_value_difference=-1.55),
		]), 1.55)

	def test_combines_split_ledger_rows(self):
		self.assertEqual(self.cost([
			dict(qty=-1, stock_value_difference=-10),
			dict(qty=-2, stock_value_difference=-30),
		], qty=3), 40)

	def test_return_cost_is_negative(self):
		self.assertEqual(self.cost([dict(qty=2, stock_value_difference=20)], qty=-2), -20)

	def test_partial_delivery_cost_is_prorated(self):
		self.assertEqual(self.cost([dict(qty=-10, stock_value_difference=-50)], qty=2), 10)

	def test_actual_zero_cost_stays_zero(self):
		self.assertEqual(self.cost([dict(qty=-1, stock_value_difference=0)]), 0)
