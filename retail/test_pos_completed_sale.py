"""Completed sales regressions; integration fixtures are always rolled back."""
import json
import unittest
from unittest.mock import patch

import frappe

from retail.pos_completed_sale import audit_validation


class TestCompletedValidation(unittest.TestCase):
	def setUp(self):
		frappe.local.message_log = []

	def test_completed_policy_failure_becomes_one_audit_reason(self):
		doc = frappe._dict(doctype="POS Invoice", pos_sync_source="Offline POS",
			custom_pos_completed_payload='{"items": [{}]}', flags=frappe._dict())
		def reject():
			frappe.local.message_log.append("rejected")
			raise frappe.ValidationError("Shift closed")
		for _ in range(2):
			audit_validation(doc, "Session", reject)
		self.assertEqual(len(doc.flags.pos_mismatch_reasons), 1)
		self.assertIn("Shift closed", doc.flags.pos_mismatch_reasons[0])
		self.assertEqual(frappe.local.message_log, [])

	def test_regular_invoice_still_rejects_policy_failure(self):
		doc = frappe._dict(doctype="POS Invoice", flags=frappe._dict())
		with self.assertRaises(frappe.ValidationError):
			audit_validation(doc, "Policy", lambda: self.reject(frappe.ValidationError))

	def test_programming_failure_is_not_reported_as_posted(self):
		doc = frappe._dict(doctype="POS Invoice", pos_sync_source="Offline POS",
			custom_pos_completed_payload='{"items": [{}]}', flags=frappe._dict())
		with self.assertRaises(RuntimeError):
			audit_validation(doc, "Policy", lambda: self.reject(RuntimeError))

	@staticmethod
	def reject(exception):
		raise exception("Failure")


def run_integration():
	if frappe.local.site != "retail-test.localhost":
		raise RuntimeError("Rollback-only regression restricted to retail-test.localhost")
	from retail.api import pos_sync
	from retail import pos_rate_audit
	frappe.set_user("Administrator")
	frappe.flags.in_test = True
	results = []
	try:
		base = json.loads(frappe.db.get_value("POS Sync Log", "PSL-2644", "request_json"))
		token = frappe.generate_hash(length=12)

		def sale(suffix, **changes):
			payload = {**base, "external_pos_reference": f"completed-test-{token}-{suffix}", **changes}
			response = pos_sync.create_pos_invoice(payload)
			assert response["status"] == "Success", response
			doc = frappe.get_doc("POS Invoice", response["invoice_name"])
			assert doc.docstatus == 1
			audits = frappe.get_all("External POS Rate Audit", filters={"pos_invoice": doc.name},
				fields=["name", "reason", "cashier", "cashier_employee", "item_code"])
			return payload, response, doc, audits

		payload, response, doc, audits = sale("original")
		assert doc.grand_total == 1250, doc.grand_total
		assert doc.total_taxes_and_charges == base["vat_amount"]
		assert abs(doc.net_total + doc.total_taxes_and_charges - doc.grand_total) < 0.000001
		assert any("ERP rounded line totals" in a.reason for a in audits), audits
		assert any(a.cashier == "cashier@gmail.com" and a.cashier_employee == "E-1" for a in audits)
		assert pos_sync.create_pos_invoice(payload)["duplicate"] is True
		assert frappe.db.count("POS Invoice", {"external_pos_reference": payload["external_pos_reference"]}) == 1
		results.append("PSL-2644 payload posts at 1250 with original VAT, mapped cashier, audits, and idempotent retry")

		def closed(*args, **kwargs):
			frappe.throw("Regression: day is closed")
		with patch.object(pos_sync, "_assert_day_not_closed", side_effect=closed):
			_, _, _, audits = sale("closed")
		assert any("day is closed" in a.reason for a in audits), audits
		results.append("closed day becomes an audit reason")

		counter = frappe.get_doc("POS Branch Counter", {"branch": base["branch"], "counter_code": base["counter_code"]})
		frappe.db.set_value("POS Profile", counter.pos_profile, "allow_partial_payment", 0)
		_, _, doc, audits = sale("partial", grand_total=1250,
			payments=[{**base["payments"][0], "amount": 1}])
		assert doc.outstanding_amount == 1249, doc.outstanding_amount
		assert any("Payment policy" in a.reason for a in audits), audits
		results.append("partial payment posts with original paid amount and outstanding balance; policy mismatch audited")

		_, _, doc, audits = sale("credit", grand_total=1250, payments=[])
		assert doc.outstanding_amount == 1250, doc.outstanding_amount
		assert any("Payment policy" in a.reason for a in audits), audits
		results.append("unpaid completed credit sale posts despite partial-payment policy")

		with patch.object(pos_rate_audit, "audit_cashier_fields", return_value={"cashier": "NONEXISTENT-CASHIER"}):
			_, response, _, audits = sale("bad-audit-link")
		assert any("Detailed audit could not be saved" in a.reason for a in audits), audits
		assert not response["audit_warnings"], response
		results.append("invalid audit cashier falls back to a report row without rejecting sale")

		_, _, doc, audits = sale("inconsistent", grand_total=120, vat_amount=5,
			items=[{**base["items"][0], "qty": 1, "rate": 100, "rate_includes_vat": 0,
				"amount": 100, "net_amount": 100}], payments=[{**base["payments"][0], "amount": 120}])
		assert doc.grand_total == 120 and doc.net_total == 115 and doc.total_taxes_and_charges == 5
		assert any("line net amounts + VAT differ" in a.reason for a in audits), audits
		assert any(a.item_code == base["items"][0]["item_code"] for a in audits), audits
		results.append("inconsistent line sum preserves POS final bill and VAT with explicit adjustment audit")

		from retail.retail_app.doctype.external_pos_rate_audit.external_pos_rate_audit import ExternalPOSRateAudit
		with patch.object(ExternalPOSRateAudit, "insert", side_effect=frappe.ValidationError("Audit storage unavailable")):
			_, response, doc, audits = sale("audit-unavailable")
		assert response["audit_warnings"] and not audits, response
		receipt = frappe.db.get_value("POS Sync Log", {"external_reference": doc.external_pos_reference,
			"sync_type": "POS Sale"}, "response_json")
		assert json.loads(receipt)["audit_warnings"], receipt
		results.append("audit-store failure preserves submitted sale and recoverable audit details in operation receipt")

		_, _, _, audits = sale("voucher-mismatch", voucher_redemption={
			"amount": 1, "redemption_reference": "missing-receipt-" + token})
		assert any("redemption" in a.reason.lower() for a in audits), audits
		results.append("missing voucher receipt audited without fabricating a voucher debit")

		def out_of_stock(*args, **kwargs):
			frappe.throw("Regression: insufficient stock")
		with patch("erpnext.accounts.doctype.pos_invoice.pos_invoice.POSInvoice.validate_stock_availablility", side_effect=out_of_stock):
			_, _, _, audits = sale("stock")
		assert any("insufficient stock" in a.reason for a in audits), audits
		results.append("stock validation mismatch audited and completed sale submitted")
		return {"passed": results, "business_data": "rolled back"}
	finally:
		frappe.db.rollback()
