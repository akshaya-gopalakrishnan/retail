"""Voucher regressions; run run_integration on the disposable local test site."""
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate

from retail.api import gift_vouchers as api


class TestVoucherAmounts(unittest.TestCase):
	def test_money_rejects_invalid_or_nonpositive_amounts(self):
		with patch.object(frappe, "throw", side_effect=frappe.ValidationError):
			for value in (0, -1, "NaN", "Infinity", "0.001", None, "invalid"):
				with self.subTest(value=value), self.assertRaises(frappe.ValidationError):
					api.money(value)
		self.assertEqual(api.money("12.34"), 12.34)

	def test_expiry_uses_server_date(self):
		voucher = frappe._dict(status="Unused", balance_amount=10, expiry_date="2020-01-01")
		with patch.object(api, "nowdate", return_value="2026-09-18"):
			self.assertEqual(api.invalid_reason(voucher), "Expired")


def run_integration():
	if frappe.local.site != "retail-test.localhost":
		raise RuntimeError("This test only runs on retail-test.localhost and rolls back its business data.")
	from retail.api import pos_sync
	from retail import pos_operations
	frappe.set_user("Administrator")
	frappe.flags.in_test = True
	results = []
	try:
		counter = frappe.get_doc("POS Branch Counter", "Business Demo Branch-COUNTER-1")
		base = {"branch": counter.branch, "counter_code": counter.counter_code}
		token = frappe.generate_hash(length=12)
		code = "PGV-" + token.upper().encode().hex().upper().ljust(32, "0")[:32]
		voucher = frappe.get_doc({"doctype": "Gift Voucher Ledger", "voucher_code": code,
			"voucher_amount": 100, "balance_amount": 100, "company": counter.company,
			"currency": frappe.db.get_value("Company", counter.company, "default_currency"),
			"status": "Unused", "issued_date": nowdate(), "expiry_date": add_days(nowdate(), 2)})
		voucher.insert(ignore_permissions=True)
		reference = "test-redeem-" + token
		request = {**base, "voucher_code": code, "amount": 30,
			"redemption_reference": reference, "external_pos_reference": "test-sale-" + token}
		first = api.redeem_gift_voucher(request)
		assert first["balance_after"] == 70, first
		assert api.redeem_gift_voucher(request)["duplicate"] is True
		assert frappe.db.get_value("Gift Voucher Ledger", code, "balance_amount") == 70
		results.append("real database debit and identical retry debit exactly once")
		frappe.db.savepoint("expected_failure")
		try:
			api.redeem_gift_voucher({**request, "amount": 31})
		except frappe.ValidationError:
			frappe.db.rollback(save_point="expected_failure")
		else:
			raise AssertionError("Changed retry accepted")
		frappe.db.savepoint("expected_failure")
		try:
			api.redeem_gift_voucher({**request, "redemption_reference": reference + "-2", "amount": 80})
		except frappe.ValidationError:
			frappe.db.rollback(save_point="expected_failure")
		else:
			raise AssertionError("Overspend accepted")
		results.append("conflicting retry and insufficient balance rejected")
		assert api.reverse_gift_voucher_redemption({**base, "redemption_reference": reference})["balance_after"] == 100
		assert api.reverse_gift_voucher_redemption({**base, "redemption_reference": reference})["duplicate"]
		results.append("reversal and reversal retry restore once")

		# Use a real fixture item/account; keep stock and fiscal setup out of this test.
		item = frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1}, "name")
		frappe.db.set_value("Item", item, "is_stock_item", 0)
		frappe.clear_document_cache("Item", item)
		if not frappe.db.exists("POS Opening Entry", {"pos_profile": counter.pos_profile, "status": "Open", "docstatus": 1}):
			pos_sync._make_pos_opening_entry(frappe._dict(external_pos_reference="opening-" + token), counter)
		mode = frappe.db.get_value("Mode of Payment", {"type": "Cash", "enabled": 1}, "name")
		issued_code = "PGV-" + "F" + token.upper().encode().hex().upper().ljust(31, "0")[:31]
		sale = {**base, "external_pos_reference": "issue-" + token,
			"customer": counter.default_customer, "posting_date": nowdate(), "update_stock": 0,
			"grand_total": 11.23, "vat_amount": 1.23,
			"items": [{"item_code": item, "qty": 1, "rate": 10, "rate_includes_vat": 0,
				"vat_rate": 12.3, "amount": 10, "net_amount": 10, "vat_amount": 1.23}],
			"payments": [{"mode_of_payment": mode, "amount": 11.23}],
			"issued_vouchers": [{"voucher_code": issued_code, "voucher_amount": 17,
				"issued_date": "2026-01-01", "expiry_date": "2027-12-31", "promotion": "OFFLINE-OLD-RULE"}]}
		response = pos_sync.create_pos_invoice(sale)
		assert response.get("status") == "Success", response
		invoice = frappe.get_doc("POS Invoice", response["invoice_name"])
		assert invoice.docstatus == 1 and invoice.grand_total == 11.23, invoice.as_dict()
		assert invoice.total_taxes_and_charges == 1.23
		registered = frappe.get_doc("Gift Voucher Ledger", issued_code)
		assert registered.voucher_amount == 17 and str(registered.issued_date) == "2026-01-01"
		assert str(registered.expiry_date) == "2027-12-31"
		assert frappe.db.exists("External POS Rate Audit", {"pos_invoice": invoice.name,
			"promo_reference": "OFFLINE-OLD-RULE"})
		assert pos_sync.create_pos_invoice(sale)["duplicate"] is True
		results.append("submitted invoice preserves POS rate, VAT, total, voucher code/value/dates; mismatch audited; sync retry safe")

		# Spend before the invoice exists, then sync the discounted bill.
		paid_ref = "paid-" + token
		paid = {**base, "voucher_code": issued_code, "amount": 5,
			"external_pos_reference": paid_ref, "redemption_reference": "pay-" + token}
		assert api.redeem_gift_voucher(paid)["balance_after"] == 12
		sale2 = {**sale, "external_pos_reference": paid_ref, "issued_vouchers": [],
			"discount_amount": 5, "grand_total": 6.23,
			"items": [{**sale["items"][0], "net_amount": 5}],
			"payments": [{"mode_of_payment": mode, "amount": 6.23}],
			"voucher_redemption": {"voucher_code": issued_code, "amount": 5, "redemption_reference": "pay-" + token}}
		response2 = pos_sync.create_pos_invoice(sale2)
		assert response2.get("status") == "Success", response2
		assert frappe.db.get_value("Gift Voucher Ledger", issued_code, "balance_amount") == 12
		receipt = pos_operations.find("Voucher Redemption", "pay-" + token)
		assert receipt.linked_invoice == response2["invoice_name"]
		results.append("online debit linked to later invoice without double debit")
		frappe.get_doc("POS Invoice", response2["invoice_name"]).cancel()
		assert frappe.db.get_value("Gift Voucher Ledger", issued_code, "balance_amount") == 17
		results.append("invoice cancellation reverses its recorded debit exactly once")
		# Standard ERP counter flow uses the same locked debit service.
		erp_invoice = frappe.copy_doc(invoice)
		erp_invoice.external_pos_reference = None
		erp_invoice.pos_sync_source = None
		erp_invoice.custom_pos_completed_payload = None
		erp_invoice.custom_gift_voucher_code = issued_code
		erp_invoice.custom_gift_voucher_amount = 0
		erp_invoice.custom_gift_voucher_discount_applied = 0
		for payment in erp_invoice.payments:
			payment.amount = payment.base_amount = 0
		erp_invoice.insert(ignore_permissions=True)
		first_discount = erp_invoice.custom_gift_voucher_amount
		erp_invoice.save(ignore_permissions=True)
		assert erp_invoice.custom_gift_voucher_amount == first_discount
		erp_invoice.submit()
		assert frappe.db.get_value("Gift Voucher Ledger", issued_code, "balance_amount") == 17 - first_discount
		results.append("ERP invoice repeated validation and submission use the same voucher balance")
		merge = frappe.new_doc("POS Invoice Merge Log")
		merge.customer = invoice.customer
		merge.posting_date = nowdate()
		consolidated = merge.process_merging_into_sales_invoice([frappe.get_doc("POS Invoice", invoice.name)])
		assert consolidated.grand_total == 11.23 and consolidated.total_taxes_and_charges == 1.23
		assert not frappe.db.exists("Gift Voucher Ledger", {"issued_against_type": "Sales Invoice", "issued_against": consolidated.name})
		results.append("consolidation retains POS totals and does not issue another voucher")
		return {"passed": results, "business_data": "rolled back"}
	finally:
		frappe.db.rollback()
		if "item" in locals():
			frappe.clear_document_cache("Item", item)


def run_concurrency():
	"""Independent DB connections; commit only isolated fixtures on the test site."""
	from concurrent.futures import ThreadPoolExecutor
	from threading import Barrier
	if frappe.local.site != "retail-test.localhost":
		raise RuntimeError("Concurrency fixtures are restricted to the local test site.")
	frappe.set_user("Administrator")
	counter = frappe.get_doc("POS Branch Counter", "Business Demo Branch-COUNTER-1")
	token = frappe.generate_hash(length=16).upper().encode().hex().upper()[:32]
	codes = ["PGV-" + token, "PGV-" + "F" + token[1:]]
	base = {"branch": counter.branch, "counter_code": counter.counter_code,
		"external_pos_reference": "concurrent-" + token}
	def call(request, barrier):
		frappe.init(site="retail-test.localhost", sites_path="/home/adler/frappe-bench/sites")
		frappe.connect()
		frappe.set_user("Administrator")
		try:
			barrier.wait(timeout=15)
			result = api.redeem_gift_voucher(request)
			frappe.db.commit()
			return result
		except frappe.ValidationError as exc:
			frappe.db.rollback()
			return {"rejected": str(exc)}
		finally:
			frappe.destroy()
	try:
		for code in codes:
			frappe.get_doc({"doctype": "Gift Voucher Ledger", "voucher_code": code,
				"voucher_amount": 100, "balance_amount": 100, "company": counter.company,
				"status": "Unused"}).insert(ignore_permissions=True)
		frappe.db.commit()
		barrier = Barrier(2)
		with ThreadPoolExecutor(2) as pool:
			futures = [pool.submit(call, {**base, "voucher_code": codes[0], "amount": 80,
				"redemption_reference": f"race-{token}-{i}"}, barrier) for i in range(2)]
			results = [future.result(timeout=40) for future in futures]
		assert sum(bool(row.get("approved")) for row in results) == 1, results
		assert frappe.db.get_value("Gift Voucher Ledger", codes[0], "balance_amount", for_update=True) == 20
		frappe.db.commit()
		barrier = Barrier(2)
		with ThreadPoolExecutor(2) as pool:
			request = {**base, "voucher_code": codes[1], "amount": 30, "redemption_reference": "retry-" + token}
			futures = [pool.submit(call, request, barrier) for _ in range(2)]
			retries = [future.result(timeout=40) for future in futures]
		assert all(row.get("approved") for row in retries), retries
		assert sum(bool(row.get("duplicate")) for row in retries) == 1
		assert frappe.db.get_value("Gift Voucher Ledger", codes[1], "balance_amount", for_update=True) == 70
		return {"passed": ["two simultaneous 80 debits against 100: one approved, balance 20",
			"two simultaneous identical retries: one debit, balance 70"], "fixtures": "removed"}
	finally:
		frappe.db.rollback()
		# Explicit cleanup only of these random test fixtures (not application API).
		for code in codes:
			frappe.db.delete("POS Sync Log", {"voucher_code": code})
			frappe.db.delete("Gift Voucher Ledger", {"name": code})
		frappe.db.commit()
