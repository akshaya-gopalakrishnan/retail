"""Online-only gift voucher spending, shared by POS APIs and ERP hooks."""
from decimal import Decimal, InvalidOperation
from datetime import datetime

import frappe
from frappe.utils import flt, getdate, get_time, get_system_timezone, now_datetime, nowdate

from retail import pos_operations
from retail.pos_item_identity import with_item_identity
from retail.promotions.api_payload import promotion_payload


def money(value):
	try:
		amount = Decimal(str(value))
		valid = amount.is_finite() and amount > 0 and amount < Decimal("1000000000000") and amount == amount.quantize(Decimal("0.01"))
	except (InvalidOperation, ValueError):
		frappe.throw("A valid monetary amount is required.")
	if not valid:
		frappe.throw("Amount must be positive with at most two decimal places.")
	return float(amount)


def context(data=None, **kwargs):
	from retail.api.pos_sync import _as_dict, _assert_pos_user, _counter
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)
	counter = _counter(payload.get("branch"), payload.get("counter_code"))
	return payload, counter


def read_voucher(code, company, *, lock=False):
	if not isinstance(code, str) or not code:
		frappe.throw("voucher_code is required.")
	voucher = frappe.get_doc("Gift Voucher Ledger", code, for_update=lock)
	if voucher.company != company:
		frappe.throw("Voucher belongs to another company.", frappe.PermissionError)
	return voucher


def invalid_reason(voucher):
	if voucher.get("voucher_card_batch"):
		if voucher.get("card_archived"):
			return "Archived"
		if voucher.get("card_blocked"):
			return "Blocked"
		if voucher.get("valid_from") and getdate(voucher.valid_from) > getdate(nowdate()):
			return "Not yet valid"
	if voucher.status not in ("Unused", "Partially Used"):
		return voucher.status
	if voucher.expiry_date and getdate(voucher.expiry_date) < getdate(nowdate()):
		return "Expired"
	if flt(voucher.balance_amount) <= 0:
		return "No balance"
	if voucher.get("voucher_card_batch") and voucher.get("use_redemption_hours"):
		now = now_datetime()
		if voucher.get("valid_from") and now < datetime.combine(getdate(voucher.valid_from), get_time(voucher.active_from_time)):
			return "Not yet valid"
		if voucher.get("expiry_date") and now > datetime.combine(getdate(voucher.expiry_date), get_time(voucher.active_to_time)):
			return "Expired"
	return None


def voucher_result(voucher):
	reason = invalid_reason(voucher)
	result = {"voucher_code": voucher.name,
		"barcode": voucher.get("voucher_code") or voucher.name,
		"serial_no": voucher.get("card_number") or None,
		"voucher_amount": flt(voucher.voucher_amount),
		"balance_amount": flt(voucher.balance_amount), "status": voucher.status,
		"expiry_date": str(voucher.expiry_date) if voucher.expiry_date else None,
		"company": voucher.company, "currency": voucher.get("currency") or
		frappe.get_cached_value("Company", voucher.company, "default_currency"),
		"valid": not reason, "reason": reason, "server_date": nowdate()}
	if voucher.get("voucher_card_batch"):
		from retail.voucher_cards import batch_for
		batch = batch_for(voucher)
		result.update(voucher_card_batch=voucher.voucher_card_batch,
			valid_from=str(voucher.valid_from) if voucher.get("valid_from") else None,
			use_activation_times=bool(voucher.get("use_redemption_hours")),
			use_redemption_hours=bool(voucher.get("use_redemption_hours")),
			active_from_time=str(get_time(voucher.active_from_time)) if voucher.get("use_redemption_hours") else None,
			active_to_time=str(get_time(voucher.active_to_time)) if voucher.get("use_redemption_hours") else None,
			server_time=str(now_datetime().time()), server_timezone=get_system_timezone(),
			online_redemption_required=True, all_products=bool(batch.all_products),
			eligibility=[{k: row.get(k) for k in ("item_code", "brand", "item_group")} for row in batch.restrictions])
	return result


def debit(code, amount, company, currency=None, *, items=None, bill_total=None, eligible_limit=None, reference=None):
	voucher = read_voucher(code, company, lock=True)
	reason = invalid_reason(voucher)
	if reason:
		frappe.throw(f"Voucher cannot be redeemed: {reason}.")
	if voucher.get("voucher_card_batch"):
		from retail.voucher_cards import card_money, eligible_amount
		amount = card_money(amount)
		if eligible_limit is None:
			if bill_total is None:
				frappe.throw("Voucher cards require bill_total before voucher redemption.")
			eligible_limit = eligible_amount(voucher, items, bill_total)
		if amount > eligible_limit:
			frappe.throw("Voucher amount exceeds the eligible bill amount.")
	else:
		amount = money(amount)
	default_currency = frappe.get_cached_value("Company", company, "default_currency")
	if (voucher.get("currency") or default_currency) != (currency or default_currency):
		frappe.throw("Voucher currency does not match the transaction currency.")
	if Decimal(str(amount)) > Decimal(str(voucher.balance_amount)):
		frappe.throw("Insufficient voucher balance.")
	balance = flt(Decimal(str(voucher.balance_amount)) - Decimal(str(amount)), 2)
	frappe.db.set_value("Gift Voucher Ledger", code, {
		"balance_amount": balance, "status": "Redeemed" if balance == 0 else "Partially Used",
		"redeemed_date": nowdate(),
	})
	if voucher.get("voucher_card_batch"):
		from retail.voucher_cards import record
		voucher.balance_amount = balance
		record(voucher, "Redeemed", amount, reference)
	return {"status": "Success", "approved": True, "voucher_code": code,
		"amount": amount, "balance_after": balance}


@frappe.whitelist(methods=["GET", "POST"])
def get_gift_voucher(data=None, **kwargs):
	payload, counter = context(data, **kwargs)
	try:
		voucher = read_voucher(payload.get("voucher_code"), counter.company)
	except frappe.DoesNotExistError:
		return {"found": False, "valid": False, "reason": "Not registered"}
	result = {"found": True, **voucher_result(voucher)}
	if voucher.get("voucher_card_batch") and payload.get("bill_total") is not None:
		from retail.voucher_cards import eligible_amount
		result["maximum_redeemable_amount"] = min(flt(voucher.balance_amount),
			eligible_amount(voucher, payload.get("items"), payload.get("bill_total"))) if result["valid"] else 0
	return result


@frappe.whitelist(methods=["POST"])
def redeem_gift_voucher(data=None, **kwargs):
	payload, counter = context(data, **kwargs)
	reference = payload.get("redemption_reference")
	pos_operations.key("sale", payload.get("external_pos_reference"))
	card_batch = frappe.db.get_value("Gift Voucher Ledger", payload.get("voucher_code"), "voucher_card_batch")
	from retail.voucher_cards import card_money
	request = {"voucher_code": payload.get("voucher_code"), "amount":
		card_money(payload.get("amount")) if card_batch else money(payload.get("amount")),
		"company": counter.company, "counter": counter.name,
		"external_pos_reference": payload.external_pos_reference}
	if card_batch:
		request.update(items=payload.get("items"), bill_total=payload.get("bill_total"))
	def action():
		return {**debit(request["voucher_code"], request["amount"], counter.company,
			items=request.get("items"), bill_total=request.get("bill_total"), reference=reference),
			"redemption_reference": reference}
	return pos_operations.execute("Voucher Redemption", reference, request, action, request["voucher_code"])


def reverse(reference, reversal_reference, *, company, counter=None, invoice=None):
	receipt = pos_operations.find("Voucher Redemption", reference)
	if not receipt or receipt.status != "Success":
		frappe.throw("Original redemption was not found.")
	request = frappe.parse_json(receipt.request_json)
	if request["company"] != company or (counter and request.get("counter") != counter):
		frappe.throw("Redemption is outside the authorized counter/company.", frappe.PermissionError)
	if receipt.linked_invoice and receipt.linked_invoice != invoice:
		frappe.throw("Redemption is linked to an invoice. Cancel that invoice to reverse it.")
	# One reversal per debit, even if a caller sends a different reversal reference.
	reversal_request = {"redemption_reference": reference, "company": company}
	def action():
		voucher = read_voucher(request["voucher_code"], company, lock=True)
		if voucher.status == "Cancelled":
			frappe.throw("Cannot restore a cancelled voucher.")
		balance = flt(Decimal(str(voucher.balance_amount)) + Decimal(str(request["amount"])), 2)
		if balance > flt(voucher.voucher_amount):
			frappe.throw("Reversal would exceed original voucher value.")
		status = "Unused" if balance == flt(voucher.voucher_amount) else "Partially Used"
		if voucher.expiry_date and getdate(voucher.expiry_date) < getdate(nowdate()):
			status = "Expired"
		frappe.db.set_value("Gift Voucher Ledger", voucher.name, {"balance_amount": balance, "status": status})
		if voucher.get("voucher_card_batch"):
			from retail.voucher_cards import record
			voucher.balance_amount = balance
			record(voucher, "Reversed", request["amount"], reference)
		return {"status": "Success", "redemption_reference": reference,
			"voucher_code": voucher.name, "amount": request["amount"], "balance_after": balance}
	return pos_operations.execute("Voucher Reversal", reference, reversal_request, action, request["voucher_code"])


@frappe.whitelist(methods=["POST"])
def reverse_gift_voucher_redemption(data=None, **kwargs):
	payload, counter = context(data, **kwargs)
	return reverse(payload.get("redemption_reference"), payload.get("redemption_reference"),
		company=counter.company, counter=counter.name)


def invoice_redemption_reference(doc):
	return doc.get("custom_gift_voucher_redemption_reference") or f"ERP:{doc.doctype}:{doc.name}"


def bind_pos_redemption(doc):
	"""Link approved debits; never debit them again on invoice retries."""
	payload = frappe.parse_json(doc.get("custom_pos_completed_payload") or "{}")
	if "voucher_redemptions" in payload:
		from retail.pos_mixed_payments import voucher_rows
		for row in sorted(voucher_rows(payload), key=lambda row: row["redemption_reference"]):
			_bind_pos_redemption(doc, row.get("voucher_code"), row.get("amount"), row.get("redemption_reference"))
		return
	return _bind_pos_redemption(doc, doc.get("custom_gift_voucher_code"),
		doc.get("custom_gift_voucher_amount"), doc.get("custom_gift_voucher_redemption_reference"))


def _bind_pos_redemption(doc, code, amount, reference):
	if not reference:
		if code:
			frappe.throw("POS voucher redemption requires its online redemption_reference.")
		return
	receipt = pos_operations.find("Voucher Redemption", reference)
	if not receipt or receipt.status != "Success":
		frappe.throw("Online redemption receipt was not found.")
	request = frappe.parse_json(receipt.request_json)
	if (request.get("company") != doc.company or request.get("counter") != doc.pos_counter
		or request.get("external_pos_reference") != doc.external_pos_reference
		or request.get("voucher_code") != code
		or flt(request.get("amount")) != flt(amount)):
		frappe.throw("Redemption receipt does not match the POS sale.")
	if pos_operations.find("Voucher Reversal", reference):
		frappe.throw("This redemption has already been reversed.")
	if receipt.linked_invoice and (receipt.linked_invoice != doc.name or receipt.linked_invoice_type != doc.doctype):
		frappe.throw("Redemption is already linked to another invoice.")
	if doc.docstatus == 1:
		frappe.db.set_value("POS Sync Log", receipt.name,
			{"linked_invoice": doc.name, "linked_invoice_type": doc.doctype}, update_modified=False)


@frappe.whitelist(methods=["GET", "POST"])
def get_gift_voucher_promotions(data=None, **kwargs):
	payload, counter = context(data, **kwargs)
	# Full scoped snapshot includes disabled/expired rules so terminals can remove them.
	filters = {"modified": [">", payload.modified_after]} if payload.get("modified_after") else {}
	rows = []
	for name in frappe.get_all("Gift Voucher Promotion", filters=filters, pluck="name", order_by="modified, name"):
		doc = frappe.get_doc("Gift Voucher Promotion", name)
		if doc.company and doc.company != counter.company:
			continue
		if doc.warehouse and doc.warehouse != counter.warehouse:
			continue
		rows.append(promotion_payload(doc))
	return with_item_identity({"promotions": rows, "server_date": nowdate(),
		"server_time": now_datetime(), "server_timezone": get_system_timezone()}, counter.warehouse)
