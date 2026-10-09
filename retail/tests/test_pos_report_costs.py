"""Exercise the report SQL against isolated sales/ledger fixtures."""
import re
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retail.retail_app.report import pos_report_utils as reports


class TestPOSReportCosts(unittest.TestCase):
	def setUp(self):
		self.db = sqlite3.connect(":memory:")
		self.db.row_factory = sqlite3.Row
		self.addCleanup(self.db.close)
		self.db.executescript("""
			create table `tabPOS Invoice` (name text, consolidated_invoice text,
				docstatus integer, is_return integer, posting_date text);
			create table `tabPOS Invoice Item` (name text, parent text, item_code text,
				item_name text, item_group text, warehouse text, stock_qty real, qty real,
				base_net_amount real);
			create table `tabSales Invoice` (name text, docstatus integer);
			create table `tabSales Invoice Item` (name text, parent text, pos_invoice_item text);
			create table `tabStock Ledger Entry` (voucher_detail_no text, voucher_no text,
				voucher_type text, is_cancelled integer, stock_value_difference real);
		""")

	def sale(self, name, amount=100, consolidated=None, returned=False):
		self.db.execute("insert into `tabPOS Invoice` values (?, ?, 1, ?, '2026-09-18')",
			(name, consolidated, int(returned)))
		self.db.execute("insert into `tabPOS Invoice Item` values (?, ?, 'ITEM', 'Item', 'Group', 'WH', ?, ?, ?)",
			(name + '-item', name, -1 if returned else 1, -1 if returned else 1, amount))

	def ledger(self, detail, voucher, value, kind='Sales Invoice', cancelled=0):
		self.db.execute("insert into `tabStock Ledger Entry` values (?, ?, ?, ?, ?)",
			(detail, voucher, kind, cancelled, value))

	def consolidated(self, pos, invoice='SI', status=1):
		self.db.execute("insert into `tabSales Invoice` values (?, ?)", (invoice, status))
		self.db.execute("insert into `tabSales Invoice Item` values (?, ?, ?)",
			(invoice + '-item', invoice, pos + '-item'))

	def results(self):
		def sql(query, values, as_dict):
			query = re.sub(r'%\((\w+)\)s', r':\1', query)
			return [frappe._dict(dict(row)) for row in self.db.execute(query, values)]
		with patch.object(frappe, 'db', SimpleNamespace(sql=sql)), patch.object(reports, '_', side_effect=lambda s: s):
			return [fn(frappe._dict({'from_date': '2026-09-18', 'to_date': '2026-09-18'}))
				for fn in (reports.pos_item_wise_sales, reports.pos_category_sales)]

	def test_consolidated_split_cost_preferred_without_multiplying_sales(self):
		self.sale('POS', consolidated='SI')
		self.consolidated('POS')
		self.ledger('SI-item', 'SI', -25)
		self.ledger('SI-item', 'SI', -35)
		self.ledger('SI-item', 'SI', -999, cancelled=1)
		self.ledger('POS-item', 'POS', -50, kind='POS Invoice')
		for result in self.results():
			row = result[1][0]
			self.assertEqual((row.net_amount, row.cost_amount, row.gross_profit, row.margin_percent), (100, 60, 40, 40))
			self.assertEqual(row.cost_status, 'Posted')

	def test_direct_pos_cost_supported(self):
		self.sale('POS')
		self.ledger('POS-item', 'POS', -60, kind='POS Invoice')
		for result in self.results():
			self.assertEqual(result[1][0].cost_amount, 60)

	def test_returns_reverse_cost(self):
		self.sale('POS', amount=-100, consolidated='SI', returned=True)
		self.consolidated('POS')
		self.ledger('SI-item', 'SI', 60)
		for result in self.results():
			row = result[1][0]
			self.assertEqual((row.net_amount, row.cost_amount, row.gross_profit), (-100, -60, -40))

	def test_partial_costs_do_not_create_misleading_group_profit_or_totals(self):
		self.sale('POSTED')
		self.ledger('POSTED-item', 'POSTED', -60, kind='POS Invoice')
		self.sale('OPEN')
		for result in self.results():
			row = result[1][0]
			self.assertEqual(row.net_amount, 200)
			self.assertEqual(row.missing_cost_rows, 1)
			self.assertIsNone(row.cost_amount)
			self.assertIsNone(row.gross_profit)
			self.assertIsNone(row.margin_percent)
			self.assertTrue(result[2])
			self.assertTrue(result[5])

	def test_zero_posted_cost_is_valid(self):
		self.sale('POS', consolidated='SI')
		self.consolidated('POS')
		self.ledger('SI-item', 'SI', 0)
		for result in self.results():
			row = result[1][0]
			self.assertEqual((row.cost_amount, row.gross_profit, row.missing_cost_rows), (0, 100, 0))

	def test_cancelled_sales_invoice_cost_is_not_used(self):
		self.sale('POS', consolidated='SI')
		self.consolidated('POS', status=2)
		self.ledger('SI-item', 'SI', -60)
		for result in self.results():
			self.assertIsNone(result[1][0].gross_profit)
