import random

import frappe
from frappe import flt
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, nowdate

from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from erpnext.accounts.doctype.sales_invoice.test_sales_invoice import create_sales_invoice
from erpnext.accounts.report.gross_profit.gross_profit import execute as execute_gross_profit
from erpnext.accounts.doctype.pos_profile.test_pos_profile import make_pos_profile
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
from erpnext.stock.doctype.delivery_note.test_delivery_note import create_delivery_note
from erpnext.stock.doctype.item.test_item import create_item
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

from retail.retail_app.retail_dashboard import get_today_profit


class TestRetailTodayProfit(FrappeTestCase):
	def setUp(self):
		self.company = "_Test Company"
		self.warehouse = "Stores - _TC"
		self.customer = "_Test Customer"
		self.item = f"_Test Retail Dashboard Item {random.randint(10000, 99999)}"
		self.item_code = create_item(
			self.item,
			company=self.company,
			is_stock_item=1,
			warehouse=self.warehouse,
			valuation_rate=100,
		).name
		self.pos_profile = make_pos_profile(company=self.company)
		self.today = getdate(nowdate())

		make_stock_entry(
			item_code=self.item_code,
			company=self.company,
			to_warehouse=self.warehouse,
			qty=10,
			rate=100,
		)

	def tearDown(self):
		frappe.db.rollback()

	def _gross_profit_report_for_today(self):
		_, rows = execute_gross_profit(
			frappe._dict({
				"company": self.company,
				"from_date": self.today,
				"to_date": self.today,
				"group_by": "Invoice",
				"include_returned_invoices": 1,
			})
		)
		return flt(rows[-1].gross_profit) if rows else 0.0

	def _create_sales_invoice(self, **kwargs):
		args = {
			"company": self.company,
			"customer": self.customer,
			"debit_to": "Debtors - _TC",
			"item_code": self.item_code,
			"item_name": self.item_code,
			"warehouse": self.warehouse,
			"income_account": "Sales - _TC",
			"expense_account": "Cost of Goods Sold - _TC",
			"cost_center": "_Test Cost Center - _TC",
			"currency": "INR",
			"posting_date": self.today,
			"qty": 1,
			"rate": 125,
		}
		args.update(kwargs)
		invoice = create_sales_invoice(**args)
		return invoice

	def test_normal_sale_matches_gross_profit_report(self):
		report_before = self._gross_profit_report_for_today()
		card_before = get_today_profit(company=self.company)

		self._create_sales_invoice()

		report_after = self._gross_profit_report_for_today()
		card_after = get_today_profit(company=self.company)
		expected_profit = 25.0

		self.assertEqual(flt(card_after - card_before), expected_profit)
		self.assertEqual(flt(report_after - report_before), flt(card_after - card_before))

	def test_delivery_note_based_sale_matches_gross_profit_report(self):
		report_before = self._gross_profit_report_for_today()
		card_before = get_today_profit(company=self.company)

		dn = create_delivery_note(
			company=self.company,
			customer=self.customer,
			item=self.item_code,
			warehouse=self.warehouse,
			rate=125,
			cost_center="_Test Cost Center - _TC",
			expense_account="Cost of Goods Sold - _TC",
		)
		si = make_sales_invoice(dn.name)
		si.submit()

		report_after = self._gross_profit_report_for_today()
		card_after = get_today_profit(company=self.company)
		self.assertEqual(flt(report_after - report_before), flt(card_after - card_before))
		self.assertEqual(flt(card_after - card_before), 25.0)

	def test_pos_sale_matches_gross_profit_report(self):
		report_before = self._gross_profit_report_for_today()
		card_before = get_today_profit(company=self.company)

		pos_sale = create_sales_invoice(
			company=self.company,
			customer=self.customer,
			debit_to="Debtors - _TC",
			item_code=self.item_code,
			warehouse=self.warehouse,
			income_account="Sales - _TC",
			expense_account="Cost of Goods Sold - _TC",
			cost_center="_Test Cost Center - _TC",
			currency="INR",
			posting_date=self.today,
			qty=1,
			rate=125,
			is_pos=1,
			do_not_save=True,
		)
		pos_sale.pos_profile = self.pos_profile.name
		pos_sale.append("payments", {"mode_of_payment": "Cash", "amount": 125})
		pos_sale.insert()
		pos_sale.submit()

		report_after = self._gross_profit_report_for_today()
		card_after = get_today_profit(company=self.company)
		self.assertEqual(flt(report_after - report_before), flt(card_after - card_before))
		self.assertEqual(flt(card_after - card_before), 25.0)

	def test_return_sales_is_negative_and_matches_gross_profit_report(self):
		self._create_sales_invoice()
		report_after_sale = self._gross_profit_report_for_today()
		card_after_sale = get_today_profit(company=self.company)

		source_invoice = frappe.get_all("Sales Invoice", filters={"company": self.company, "posting_date": self.today}, order_by="creation desc", limit=1, pluck="name")[0]
		r = make_sales_return(source_invoice)
		r.insert()
		r.submit()

		report_after_return = self._gross_profit_report_for_today()
		card_after_return = get_today_profit(company=self.company)

		self.assertEqual(flt(report_after_return - report_after_sale), flt(card_after_return - card_after_sale))
		self.assertLess(card_after_return - card_after_sale, 0)
		self.assertEqual(flt(card_after_return - card_after_sale), -25.0)
