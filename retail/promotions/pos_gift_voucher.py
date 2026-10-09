"""Register the customer-facing POS promise; ERP expectations are audit-only."""
import re

import frappe
from frappe.utils import add_days, flt, getdate

from retail import pos_operations
from retail.api.gift_vouchers import money, voucher_result


def register(doc):
	from retail.promotions import gift_voucher as rules
	payload = frappe.parse_json(doc.get("custom_pos_completed_payload") or "{}")
	rows = payload.get("issued_vouchers") or []
	expected = {}
	audit_error = None
	try:
		for promotion in rules.get_active_promotions(doc):
			eligible = rules.get_eligible_amount(doc, promotion)
			if eligible >= flt(promotion.min_sales_value):
				expected[promotion.name] = {"amount": rules.get_voucher_amount(eligible, promotion),
					"expiry_date": str(add_days(doc.posting_date, promotion.expiry_days)) if promotion.expiry_days else None}
	except Exception as exc:
		audit_error = f"ERP promotion comparison unavailable: {type(exc).__name__}"
	seen = set()
	for index, row in enumerate(rows):
		code = row.get("voucher_code")
		if not isinstance(code, str) or not re.fullmatch(r"PGV-[0-9A-F]{32}", code):
			frappe.throw("POS voucher_code must be PGV- followed by 32 uppercase hexadecimal characters.")
		if code in seen:
			frappe.throw("Duplicate voucher_code in the same sale.")
		seen.add(code)
		amount = money(row.get("voucher_amount"))
		if not row.get("issued_date"):
			frappe.throw("issued_date is required for each POS voucher.")
		issued_date = getdate(row["issued_date"])
		expiry_date = getdate(row["expiry_date"]) if row.get("expiry_date") else None
		promotion = row.get("promotion")
		voucher = frappe.new_doc("Gift Voucher Ledger")
		voucher.update({"voucher_code": code, "voucher_amount": amount, "balance_amount": amount,
			"status": "Unused", "issued_date": issued_date, "expiry_date": expiry_date,
			"promotion": promotion if promotion and frappe.db.exists("Gift Voucher Promotion", promotion) else None,
			"pos_promotion_reference": promotion, "issued_against_type": doc.doctype, "issued_against": doc.name,
			"issuance_key": pos_operations.key("POS voucher", f"{doc.external_pos_reference}:{index}"),
			"external_pos_reference": doc.external_pos_reference,
			"customer": row.get("customer") or doc.customer, "company": doc.company,
			"warehouse": doc.set_warehouse, "currency": doc.currency})
		# Never upsert: a conflicting code must not replace an existing customer's value.
		voucher.insert(ignore_permissions=True)
		comparison = expected.pop(promotion, None)
		if (audit_error or not comparison or flt(comparison["amount"]) != amount
			or comparison["expiry_date"] != (str(expiry_date) if expiry_date else None)
			or issued_date != getdate(doc.posting_date)):
			write_audit(doc, row, comparison or {}, audit_error or "POS voucher differs from current ERP promotion; POS values retained.")
	for promotion, comparison in expected.items():
		write_audit(doc, {"promotion": promotion, "voucher_amount": 0}, comparison,
			"ERP would issue a voucher, but POS issued none. No extra voucher generated.")
	if audit_error and not rows:
		write_audit(doc, {"issued_vouchers": []}, {}, audit_error)


def write_audit(doc, actual, expected, reason):
	from retail.pos_rate_audit import audit_cashier_fields, insert_audit

	return insert_audit(doc, {
		**audit_cashier_fields(doc),
		"promo_reference": actual.get("promotion"), "reason": reason,
		"pos_gross_amount": flt(actual.get("voucher_amount")),
		"erp_expected_gross_amount": flt(expected.get("amount")),
		"amount_difference": flt(actual.get("voucher_amount")) - flt(expected.get("amount")),
		"pos_calculation_json": pos_operations.canonical(actual),
		"erp_calculation_json": pos_operations.canonical(expected),
	})


def issued_for(doc):
	return [voucher_result(frappe.get_doc("Gift Voucher Ledger", name)) for name in
		frappe.get_all("Gift Voucher Ledger", filters={"issued_against_type": doc.doctype,
			"issued_against": doc.name}, pluck="name", order_by="name")]
