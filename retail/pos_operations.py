"""Durable operation receipts. The unique key and effects commit together."""
import hashlib
import json

import frappe
from frappe.utils import now_datetime


def canonical(value):
	return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def key(kind, reference):
	if not isinstance(reference, str) or not reference.strip() or len(reference) > 512:
		frappe.throw("A non-empty reference of at most 512 characters is required.")
	return hashlib.sha256(f"{kind}:{reference}".encode()).hexdigest()


def find(kind, reference):
	return frappe.db.get_value("POS Sync Log", {"operation_key": key(kind, reference)},
		["name", "request_json", "response_json", "status", "voucher_code", "linked_invoice", "linked_invoice_type"],
		as_dict=True, for_update=True)


def execute(kind, reference, request, action, voucher_code=None):
	"""Claim before the effect; concurrent inserts wait on the UNIQUE index.

	A savepoint permits a current read after the losing insert, including under
	MariaDB REPEATABLE READ. No helper commits the caller's transaction.
	"""
	operation_key = key(kind, reference)
	if len(reference) > 140:
		frappe.throw("Operation references must not exceed 140 characters.")
	encoded = canonical(request)
	frappe.db.savepoint("pos_operation_claim")
	doc = frappe.get_doc({
		"doctype": "POS Sync Log", "sync_type": kind, "operation_key": operation_key,
		"external_reference": reference, "status": "Pending", "request_json": encoded,
		"voucher_code": voucher_code, "attempt_count": 1,
		"created_at": now_datetime(), "last_attempt_at": now_datetime(),
	})
	doc.flags.allow_operation_write = True
	try:
		doc.insert(ignore_permissions=True)
	except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
		frappe.db.rollback(save_point="pos_operation_claim")
		previous = find(kind, reference)
		if not previous or previous.request_json != encoded:
			frappe.throw("Reference conflict: this operation reference was used with different data.")
		if previous.status != "Success":
			frappe.throw("Operation is not complete. Retry the same reference.")
		result = json.loads(previous.response_json)
		result["duplicate"] = True
		return result
	result = action()
	from retail.pos_transaction_display import invoice_links
	links = invoice_links(result)
	from retail.pos_transaction_display import payload_transaction_type
	display_type = payload_transaction_type(kind, request.get("payload") or {})
	result.setdefault("duplicate", False)
	frappe.db.set_value("POS Sync Log", doc.name, {
		"status": "Success", "response_json": canonical(result),
		"custom_pos_transaction_type": display_type,
		**links,
		"branch": (request.get("payload") or {}).get("branch"),
		"counter": (request.get("payload") or {}).get("counter_code"),
		"erpnext_docname": result.get("invoice_name") or result.get("return_invoice")
			or result.get("payment_entry") or result.get("cash_movement")
			or result.get("cashier_shift") or result.get("counter_session") or result.get("day_closing")
			or (result.get("name") if kind == "Day Closing" else None),
	}, update_modified=False)
	return result
