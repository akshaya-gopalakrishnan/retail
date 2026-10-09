"""Purchase history tests use rolled-back ledger-free source fixtures.

Fixtures are inserted directly because this suite tests reporting, not ERPNext posting.
No test source transaction survives the savepoint rollback.
"""

import unittest
from unittest.mock import patch
from uuid import uuid4

import frappe

from retail.domains.purchase import history


class TestPurchaseHistory(unittest.TestCase):
	def setUp(self):
		self.user = frappe.session.user
		frappe.set_user("Administrator")
		frappe.db.savepoint("purchase_history_test")
		self.company = frappe.db.get_value("Company", {}, "name")
		if not self.company:
			self.skipTest("Requires a company")
		self.supplier = self.master("Supplier", supplier_name="History Supplier", supplier_type="Company")
		self.other_supplier = self.master("Supplier", supplier_name="Other History Supplier", supplier_type="Company")
		self.item = self.master("Item", item_name="History Test Item", stock_uom="Nos", is_stock_item=1)
		self.doc = frappe.get_doc({
			"doctype": "Purchase Invoice", "name": "new-history-invoice", "__islocal": 1,
			"company": self.company, "supplier": self.supplier, "conversion_rate": 1,
			"posting_date": "2026-03-01", "posting_time": "12:00:00", "docstatus": 0,
			"items": [{"name": "new-history-row", "item_code": self.item, "qty": 10,
				"net_amount": 120, "base_net_amount": 120, "conversion_factor": 1, "stock_uom": "Nos"}],
		})

	def tearDown(self):
		frappe.set_user(self.user)
		frappe.db.rollback(save_point="purchase_history_test")

	def master(self, doctype, **values):
		doc = frappe.get_doc({"doctype": doctype, "name": "history-test-" + uuid4().hex, **values})
		doc.db_insert()
		return doc.name

	def purchase(self, doctype="Purchase Receipt", rate=10, qty=10, supplier=None,
		date="2026-01-01", factor=1, foc=0, status=1, is_return=0, receipt=None, **values):
		doc = frappe.get_doc({"doctype": doctype, "name": "history-test-" + uuid4().hex,
			"company": self.company, "supplier": supplier or self.supplier,
			"currency": "AED", "conversion_rate": 1, "posting_date": date,
			"posting_time": "10:00:00", "docstatus": status, "is_return": is_return, **values})
		row = doc.append("items", {"item_code": self.item, "qty": qty, "rate": rate,
			"net_rate": rate, "net_amount": qty * rate, "base_net_amount": qty * rate,
			"uom": "Nos", "stock_uom": "Nos", "conversion_factor": factor, "custom_foc_qty": foc})
		if receipt:
			row.purchase_receipt, row.pr_detail = receipt.name, receipt.items[0].name
		doc.db_insert()
		row.db_insert()
		return doc

	def compare(self):
		return history.get_comparisons(self.doc.as_dict())["rows"][0]

	def test_first_purchase_and_draft_cancelled_return_exclusion(self):
		for status in (0, 2):
			self.purchase(status=status)
		self.purchase(is_return=1, qty=-1)
		self.assertIsNone(self.compare()["baseline"])
		self.assertFalse(self.compare()["higher"])
		self.assertEqual(history.get_history(self.doc.as_dict(), self.item)["total"], 1)

	def test_higher_equal_lower_zero_and_other_supplier(self):
		self.purchase(rate=10)
		self.purchase(rate=5, supplier=self.other_supplier)
		result = self.compare()
		self.assertTrue(result["higher"])
		self.assertEqual(result["percent"], 20)
		self.doc.items[0].net_amount = 100
		self.doc.items[0].base_net_amount = 100
		self.assertFalse(self.compare()["higher"])
		self.doc.items[0].net_amount = 90
		self.doc.items[0].base_net_amount = 90
		self.assertFalse(self.compare()["higher"])
		self.purchase(rate=0, date="2026-02-01")
		result = self.compare()
		self.assertTrue(result["higher"])
		self.assertIsNone(result["percent"])
		other = history.get_history(self.doc.as_dict(), self.item, scope="others")
		self.assertEqual(other["total"], 1)
		self.assertEqual(other["rows"][0]["supplier"], self.other_supplier)

	def test_receipt_10_bill_9_one_chain_and_no_mutation(self):
		receipt = self.purchase(rate=10)
		invoice = self.purchase("Purchase Invoice", rate=9, date="2026-02-01", receipt=receipt)
		before = self.doc.as_json()
		result = self.compare()
		self.assertEqual(result["baseline"]["rate"], 9)
		data = history.get_history(self.doc.as_dict(), self.item)
		self.assertEqual(data["total"], 1)
		self.assertEqual(data["rows"][0]["receipt"].comparable_rate, 10)
		self.assertEqual(data["rows"][0]["invoices"][0].name, invoice.name)
		self.assertEqual(data["rows"][0]["status"], "Fully billed")
		self.assertEqual(self.doc.as_json(), before)
		self.assertEqual(frappe.db.get_value("Purchase Receipt Item", receipt.items[0].name, "rate"), 10)

	def test_partial_billing_and_weighted_invoice_cost(self):
		receipt = self.purchase(qty=100)
		self.purchase("Purchase Invoice", rate=9, qty=40, receipt=receipt)
		data = history.get_history(self.doc.as_dict(), self.item)
		self.assertEqual(data["rows"][0]["status"], "Partly billed")
		self.purchase("Purchase Invoice", rate=11, qty=60, receipt=receipt, date="2026-02-01")
		data = history.get_history(self.doc.as_dict(), self.item)
		self.assertEqual(data["total"], 1)
		self.assertEqual(data["rows"][0]["status"], "Fully billed")
		self.assertAlmostEqual(data["rows"][0]["rate"], 10.2)

	def test_conversion_foc_and_net_discount_amount(self):
		self.purchase(rate=120, qty=10, factor=12, foc=2)
		self.doc.items[0].net_amount = 120
		self.doc.items[0].qty = 10
		self.doc.items[0].custom_foc_qty = 2
		self.doc.items[0].conversion_factor = 1
		self.doc.conversion_rate = 2
		self.doc.items[0].base_net_amount = 240
		result = self.compare()
		self.assertAlmostEqual(result["baseline"]["rate"], 1200 / 144)
		self.assertEqual(result["current_rate"], 20)
		self.doc.items[0].net_amount = 0
		self.doc.items[0].base_net_amount = 0
		self.assertEqual(self.compare()["current_rate"], 0)

	def test_cutoff_and_current_receipt_excluded_from_baseline(self):
		old = self.purchase(date="2026-01-01", rate=8)
		receipt = self.purchase(date="2026-02-01", rate=10)
		self.purchase(date="2026-04-01", rate=2)
		self.doc.items[0].purchase_receipt = receipt.name
		self.doc.items[0].pr_detail = receipt.items[0].name
		result = self.compare()
		self.assertEqual(result["baseline"]["name"], old.name)
		self.assertEqual(result["linked_receipt"].name, receipt.name)
		self.doc.posting_date = "2026-01-01"
		self.doc.posting_time = "09:00:00"
		self.assertIsNone(self.compare()["baseline"])

	def test_cancelled_bill_falls_back_to_receipt_and_returns_separate(self):
		receipt = self.purchase(rate=10)
		self.purchase("Purchase Invoice", rate=9, receipt=receipt, status=2)
		self.purchase("Purchase Invoice", rate=8, qty=-1, is_return=1, receipt=receipt)
		self.assertEqual(self.compare()["baseline"]["rate"], 10)
		self.assertEqual(history.get_history(self.doc.as_dict(), self.item)["total"], 2)

	def test_same_receipt_paid_and_free_rows_are_not_previous_purchases(self):
		receipt = self.purchase(rate=10, foc=2)
		free = receipt.append("items", {"item_code": self.item, "qty": 2, "rate": 0,
			"net_rate": 0, "net_amount": 0, "base_net_amount": 0,
			"uom": "Nos", "stock_uom": "Nos", "conversion_factor": 1})
		free.db_insert()
		self.doc.items[0].purchase_receipt = receipt.name
		self.doc.items[0].pr_detail = receipt.items[0].name
		self.doc.append("items", {"name": "new-free-row", "item_code": self.item,
			"qty": 2, "net_amount": 0, "base_net_amount": 0, "conversion_factor": 1,
			"purchase_receipt": receipt.name, "pr_detail": free.name})
		for result in history.get_comparisons(self.doc.as_dict())["rows"]:
			self.assertIsNone(result["baseline"])
			self.assertIsNone(result["difference"])
			self.assertFalse(result["higher"])
		self.assertAlmostEqual(self.compare()["current_rate"], 10)
		old = self.purchase(rate=8, date="2025-12-01")
		for result in history.get_comparisons(self.doc.as_dict())["rows"]:
			self.assertEqual(result["baseline"]["name"], old.name)

	def test_same_receipt_bill_excluded_when_receipt_not_visible(self):
		receipt = self.purchase(rate=0)
		self.purchase("Purchase Invoice", rate=0, receipt=receipt)
		self.doc.items[0].purchase_receipt = receipt.name
		self.doc.items[0].pr_detail = "another-row-of-the-same-receipt"
		read_rows = history._read_rows
		def visible_rows(doctype, *args, **kwargs):
			return ([], False) if doctype == "Purchase Receipt" else read_rows(doctype, *args, **kwargs)
		with patch.object(history, "_read_rows", side_effect=visible_rows):
			result = self.compare()
		self.assertIsNone(result["baseline"])
		self.assertFalse(result["higher"])

	def test_company_isolation_pagination_date_filter(self):
		for day in range(1, 5):
			self.purchase(date=f"2026-01-0{day}")
		self.purchase(company="Different Company")
		data = history.get_history(self.doc.as_dict(), self.item, start=2, page_length=2)
		self.assertEqual(data["total"], 4)
		self.assertEqual(len(data["rows"]), 2)
		self.assertEqual(data["rows"][0]["date"], "2026-01-02")
		data = history.get_history(self.doc.as_dict(), self.item, from_date="2026-01-03")
		self.assertEqual(data["total"], 2)

	def test_submission_warning_and_failure_do_not_mutate_or_block(self):
		self.purchase(rate=10)
		before = self.doc.as_json()
		with patch.object(history.frappe, "msgprint") as message:
			history.warn_before_submit(self.doc)
			self.assertEqual(message.call_args.kwargs["indicator"], "red")
		self.assertEqual(self.doc.as_json(), before)
		with patch.object(history, "_load_history", side_effect=RuntimeError("unavailable")), \
			patch.object(history.frappe, "log_error"), patch.object(history.frappe, "msgprint") as message:
			history.warn_before_submit(self.doc)
			self.assertEqual(message.call_args.kwargs["indicator"], "orange")

	def test_document_permission_and_cost_permission(self):
		self.purchase()
		with patch.object(history, "get_permitted_fields", return_value=["name"]):
			result = self.compare()
			self.assertIsNone(result["baseline"])
			self.assertTrue(result["limited_access"])
		with patch.object(history.frappe, "has_permission", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				self.compare()

	def test_return_document_never_warns(self):
		self.purchase(rate=10)
		self.doc.is_return = 1
		self.assertFalse(self.compare()["higher"])
		with patch.object(history.frappe, "msgprint") as message:
			history.warn_before_submit(self.doc)
			message.assert_not_called()

	def test_stock_context_is_read_only_and_reports_opening_stock(self):
		entry = frappe.get_doc({"doctype": "Stock Entry", "name": "history-test-" + uuid4().hex,
			"company": self.company, "purpose": "Material Receipt", "docstatus": 1,
			"posting_date": "2026-01-01", "posting_time": "10:00:00", "is_opening": "Yes"})
		item = entry.append("items", {"item_code": self.item, "qty": 10})
		entry.db_insert()
		item.db_insert()
		context = history.get_stock_context(self.doc.as_dict(), self.item)
		self.assertEqual(len(context), 1)
		self.assertEqual(context[0].name, entry.name)
		self.assertEqual(context[0].doctype, "Stock Entry")
		self.assertIsNone(self.compare()["baseline"])

	def test_supplier_user_permission_filters_other_suppliers(self):
		self.purchase()
		self.purchase(supplier=self.other_supplier)
		user = frappe.get_doc({"doctype": "User", "name": "history-test-" + uuid4().hex + "@example.invalid",
			"enabled": 1, "user_type": "System User", "first_name": "History Test", "email": "test@example.invalid"})
		user.db_insert()
		for role in ("Purchase User", "Stock User", "Accounts User"):
			user.append("roles", {"role": role}).db_insert()
		permission = frappe.get_doc({"doctype": "User Permission", "name": "history-test-" + uuid4().hex,
			"user": user.name, "allow": "Supplier", "for_value": self.supplier, "apply_to_all_doctypes": 1})
		permission.db_insert()
		frappe.clear_cache(user=user.name)
		try:
			frappe.set_user(user.name)
			self.assertEqual(history.get_history(self.doc.as_dict(), self.item)["total"], 1)
			self.assertEqual(history.get_history(self.doc.as_dict(), self.item, scope="others")["total"], 0)
		finally:
			frappe.set_user("Administrator")
			frappe.clear_cache(user=user.name)

	def test_submitted_current_invoice_is_not_its_own_baseline(self):
		self.purchase("Purchase Invoice", rate=8)
		invoice = self.purchase("Purchase Invoice", rate=12, date="2026-02-01")
		result = history.get_comparisons(invoice.as_dict())["rows"][0]
		self.assertEqual(result["baseline"]["rate"], 8)

	def test_context_and_date_validation(self):
		with self.assertRaises(frappe.ValidationError):
			history.get_comparisons({"doctype": "Sales Invoice"})
		with self.assertRaises(frappe.ValidationError):
			history.get_history(self.doc.as_dict(), self.item, scope="invalid")

	def test_current_base_amount_uses_company_currency_rounding(self):
		self.purchase(rate=36.69)
		self.doc.items[0].qty = 1
		self.doc.items[0].net_amount = 9.99
		self.doc.items[0].base_net_amount = 36.69
		self.doc.conversion_rate = 3.6725
		self.assertEqual(self.compare()["current_rate"], 36.69)
		self.assertFalse(self.compare()["higher"])

	def test_receipt_free_stock_allocated_to_partial_bills_without_double_counting(self):
		receipt = self.purchase(qty=100, foc=10)
		self.purchase("Purchase Invoice", rate=9, qty=40, foc=10, receipt=receipt)
		self.purchase("Purchase Invoice", rate=9, qty=60, foc=0, receipt=receipt)
		result = history.get_history(self.doc.as_dict(), self.item)["rows"][0]
		self.assertAlmostEqual(result["rate"], 900 / 110)
		self.assertEqual(sum(row.effective_qty for row in result["invoices"]), 110)
		self.doc.items[0].purchase_receipt = receipt.name
		self.doc.items[0].pr_detail = receipt.items[0].name
		self.assertAlmostEqual(self.compare()["current_rate"], 120 / 11)

	def test_later_bill_does_not_change_backdated_baseline(self):
		receipt = self.purchase(rate=10, per_billed=100)
		self.purchase("Purchase Invoice", rate=9, receipt=receipt, date="2026-04-01")
		result = self.compare()
		self.assertEqual(result["baseline"]["rate"], 10)
		self.assertEqual(result["baseline"]["rate_basis"], "Receipt reference cost")
		self.assertEqual(result["baseline"]["status"], "Receipt rate — bill outside visible history")
