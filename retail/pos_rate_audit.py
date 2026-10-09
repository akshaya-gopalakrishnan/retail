import json

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from retail.domains.item.vat_pricing import get_item_tax_rate


AUDIT_DOCTYPE = "External POS Rate Audit"
STATUS_OPEN = "Open"
STATUS_ACCEPTED = "Accepted"
STATUS_IGNORED = "Ignored"
STATUS_RECALCULATED = "Recalculated"
RATE_TOLERANCE = 0.01
VAT_TOLERANCE = 0.01


def insert_audit(doc, values):
	"""Audit failure must never undo the invoice; retain a minimal report row."""
	values = dict(values)
	values.setdefault("doctype", AUDIT_DOCTYPE)
	values.setdefault("status", STATUS_OPEN)
	values.setdefault("pos_invoice", doc.name)
	values.setdefault("external_pos_reference", doc.get("external_pos_reference"))
	values.setdefault("company", doc.company)
	values.setdefault("branch", doc.get("pos_branch"))
	values.setdefault("counter", doc.get("pos_counter"))
	values.setdefault("posting_date", doc.posting_date)
	values.setdefault("posting_time", doc.get("posting_time"))
	message_count = len(frappe.local.message_log or [])
	frappe.db.savepoint("pos_audit_insert")
	try:
		return frappe.get_doc(values).insert(ignore_permissions=True).name
	except Exception as exc:
		frappe.db.rollback(save_point="pos_audit_insert")
		frappe.local.message_log = (frappe.local.message_log or [])[:message_count]
		failure = f"Detailed audit could not be saved: {type(exc).__name__}: {exc}"
		fallback = {key: values.get(key) for key in (
			"doctype", "status", "pos_invoice", "external_pos_reference", "company",
			"branch", "counter", "posting_date", "posting_time")}
		fallback.update(reason=f"{values.get('reason') or 'POS mismatch'}. {failure}",
			pos_calculation_json=json.dumps(values, default=str),
			erp_calculation_json=values.get("erp_calculation_json"))
		try:
			return frappe.get_doc(fallback).insert(ignore_permissions=True).name
		except Exception as fallback_exc:
			frappe.db.rollback(save_point="pos_audit_insert")
			frappe.local.message_log = (frappe.local.message_log or [])[:message_count]
			# The operation receipt and API result retain this if the audit store
			# itself is unavailable, rather than falsely claiming it was recorded.
			warnings = doc.flags.get("pos_audit_warnings") or []
			warnings.append({"reason": fallback["reason"], "audit": values,
				"error": f"{type(fallback_exc).__name__}: {fallback_exc}"})
			doc.flags.pos_audit_warnings = warnings
			return None


def audit_cashier_fields(doc):
	employee = doc.get("pos_cashier_employee")
	cashier = doc.get("pos_cashier")
	if employee and frappe.db.exists("Employee", employee):
		cashier = frappe.db.get_value("Employee", employee, "user_id")
	if not cashier or not frappe.db.exists("User", cashier):
		cashier = None
	return {"cashier": cashier, "cashier_employee": employee if employee and frappe.db.exists("Employee", employee) else None}


def create_for_pos_invoice(doc, payload, counter_doc=None):
	created = []
	for idx, item in enumerate(doc.get("items") or [], start=1):
		payload_items = payload.get("items") or []
		row = frappe._dict(payload_items[idx - 1] if idx <= len(payload_items) else {})
		try:
			audit = build_audit_row(doc, item, payload, row, idx, counter_doc)
		except Exception as exc:
			# A comparison failure cannot reject completed pricing. Persist the
			# comparison failure itself for review instead of silently losing it.
			audit = frappe.get_doc({"doctype": AUDIT_DOCTYPE, "status": STATUS_OPEN,
				"pos_invoice": doc.name, "external_pos_reference": doc.external_pos_reference,
				"company": doc.company, "posting_date": doc.posting_date, "item_code": item.item_code,
				"reason": f"ERP price comparison unavailable: {type(exc).__name__}; POS values retained.",
				"pos_calculation_json": json.dumps(row, default=str)})
		if audit:
			name = insert_audit(doc, audit.as_dict())
			if name:
				created.append(name)
	for reason in doc.flags.get("pos_mismatch_reasons") or []:
		name = insert_audit(doc, {"reason": reason,
			"pos_calculation_json": json.dumps(payload, default=str), **audit_cashier_fields(doc)})
		if name:
			created.append(name)
	# Include the submitted totals, which may differ even when unit rates match.
	if doc.get("custom_pos_completed_payload"):
		from retail.promotions.pos_gift_voucher import write_audit
		try:
			expected_vat = sum(flt(item.net_amount) * flt(get_item_tax_rate(
				frappe.get_cached_value("Item", item.item_code, "custom_tax"))) / 100 for item in doc.items)
		except Exception as exc:
			write_audit(doc, payload, {}, f"ERP VAT comparison unavailable: {type(exc).__name__}; POS totals retained.")
		else:
			if abs(flt(doc.total_taxes_and_charges) - flt(expected_vat, 2)) > VAT_TOLERANCE:
				write_audit(doc, payload, {"vat_amount": flt(expected_vat, 2)},
					"POS invoice VAT differs from current ERP VAT; completed POS totals retained.")
		return frappe.get_all(AUDIT_DOCTYPE, filters={"pos_invoice": doc.name}, pluck="name")
	return created


def build_audit_row(doc, item, payload, payload_row, idx, counter_doc=None):
	item_doc = frappe.get_cached_doc("Item", item.item_code)
	vat_rate = flt(get_item_tax_rate(item.get("item_tax_template") or item_doc.get("custom_tax")))
	pos_gross_rate = _payload_gross_rate(payload_row, item_doc, vat_rate)
	pos_gross_amount = flt(pos_gross_rate * flt(item.qty), 2)
	erp_expected_gross_rate = _erp_expected_gross_rate(item_doc, payload_row)
	erp_expected_gross_amount = flt(erp_expected_gross_rate * flt(item.qty), 2)
	pos_vat_amount = _payload_vat_amount(payload_row, pos_gross_rate, item.qty, vat_rate)
	erp_vat_amount = flt(erp_expected_gross_amount - (erp_expected_gross_amount / (1 + vat_rate / 100)), 2) if vat_rate else 0

	rate_difference = flt(pos_gross_rate - erp_expected_gross_rate, 2)
	amount_difference = flt(pos_gross_amount - erp_expected_gross_amount, 2)
	vat_difference = flt(pos_vat_amount - erp_vat_amount, 2)

	template_changed = bool(payload_row.get("sales_vat_template") or payload_row.get("item_tax_template")) and (
		(payload_row.get("sales_vat_template") or payload_row.get("item_tax_template")) != item_doc.get("custom_tax"))
	if (
		not template_changed
		and abs(rate_difference) <= RATE_TOLERANCE
		and abs(amount_difference) <= RATE_TOLERANCE
		and abs(vat_difference) <= VAT_TOLERANCE
	):
		return None

	reason = _reason(item_doc, payload_row, pos_gross_rate, erp_expected_gross_rate, pos_vat_amount, erp_vat_amount)
	audit = frappe.new_doc(AUDIT_DOCTYPE)
	audit.update(
		{
			"status": STATUS_OPEN,
			"pos_invoice": doc.name,
			"external_pos_reference": doc.get("external_pos_reference"),
			"posting_date": doc.posting_date,
			"posting_time": doc.get("posting_time"),
			"company": doc.company,
			"branch": doc.get("pos_branch"),
			"counter": doc.get("pos_counter"),
			"counter_code": payload.get("counter_code") or (counter_doc.get("counter_code") if counter_doc else None),
			**audit_cashier_fields(doc),
			"item_code": item.item_code,
			"item_name": item.item_name,
			"uom": item.get("uom"),
			"qty": item.qty,
			"pos_gross_rate": pos_gross_rate,
			"erp_expected_gross_rate": erp_expected_gross_rate,
			"rate_difference": rate_difference,
			"pos_gross_amount": pos_gross_amount,
			"erp_expected_gross_amount": erp_expected_gross_amount,
			"amount_difference": amount_difference,
			"difference_percent": flt((rate_difference / erp_expected_gross_rate) * 100, 2) if erp_expected_gross_rate else 0,
			"vat_rate": vat_rate,
			"pos_vat_amount": pos_vat_amount,
			"erp_expected_vat_amount": erp_vat_amount,
			"vat_difference": vat_difference,
			"promo_reference": payload_row.get("promo_reference") or payload_row.get("promo_id") or payload_row.get("promotion_id"),
			"reason": reason,
			"pos_calculation_json": json.dumps(payload_row, default=str, indent=2, sort_keys=True),
			"erp_calculation_json": json.dumps(
				{
					"item_master_gross_rate": flt(item_doc.get("custom_sales_gross_rate")),
					"item_tax_template": item.get("item_tax_template") or item_doc.get("custom_tax"),
					"vat_rate": vat_rate,
					"invoice_item_rate_excluding_vat": flt(item.rate),
					"invoice_item_net_amount": flt(item.net_amount),
				},
				default=str,
				indent=2,
				sort_keys=True,
			),
		}
	)
	return audit


def _payload_gross_rate(payload_row, item_doc, vat_rate):
	vat_rate = flt(payload_row.get("vat_rate", vat_rate))
	rate = flt(payload_row.get("rate"))
	discount = flt(payload_row.get("discount_amount"))
	if cint(payload_row.get("rate_includes_vat", item_doc.get("custom_sales_rate_includes_vat", 1))):
		return flt(rate - discount, 2)
	return flt((rate - discount) * (1 + vat_rate / 100), 2)


def _payload_vat_amount(payload_row, gross_rate, qty, vat_rate):
	provided = payload_row.get("vat_amount", payload_row.get("tax_amount"))
	if provided is not None:
		return flt(provided, 2)
	gross_amount = flt(gross_rate * flt(qty), 2)
	return flt(gross_amount - (gross_amount / (1 + vat_rate / 100)), 2) if vat_rate else 0


def _erp_expected_gross_rate(item_doc, payload_row=None):
	gross = item_doc.get("custom_sales_gross_rate")
	if gross:
		return flt(gross, 2)
	vat_rate = get_item_tax_rate(item_doc.get("custom_tax"))
	return flt(flt(item_doc.get("standard_rate")) * (1 + flt(vat_rate) / 100), 2)


def _reason(item_doc, payload_row, pos_rate, erp_rate, pos_vat, erp_vat):
	if abs(flt(pos_vat) - flt(erp_vat)) > VAT_TOLERANCE:
		return _("VAT amount differs from ERP expected VAT.")
	if abs(flt(pos_rate) - flt(erp_rate)) <= RATE_TOLERANCE:
		return _("Rounding difference.")
	if payload_row.get("promo_reference") or payload_row.get("promo_id") or payload_row.get("promotion_id"):
		return _("POS applied a promotion or manual price that differs from the current ERP selling rate.")
	if item_doc.get("modified"):
		return _("Current ERP selling rate differs from POS rate. Item was last updated at {0}.").format(item_doc.modified)
	return _("Unknown reason.")


@frappe.whitelist()
def accept(name):
	return _set_status(name, STATUS_ACCEPTED)


@frappe.whitelist()
def ignore(name):
	return _set_status(name, STATUS_IGNORED)


@frappe.whitelist()
def accept_all(names=None, filters=None):
	names = _resolve_names(names, filters)
	for name in names:
		_set_status(name, STATUS_ACCEPTED)
	return {"status": "Success", "updated": len(names)}


@frappe.whitelist()
def recalculate(name):
	doc = frappe.get_doc(AUDIT_DOCTYPE, name)
	doc.check_permission("write")
	if not doc.item_code:
		frappe.throw("Voucher/invoice comparisons are historical snapshots. Accept or ignore this audit.")
	item_doc = frappe.get_cached_doc("Item", doc.item_code)
	erp_rate = _erp_expected_gross_rate(item_doc)
	erp_amount = flt(erp_rate * flt(doc.qty), 2)
	vat_rate = flt(doc.vat_rate)
	erp_vat = flt(erp_amount - (erp_amount / (1 + vat_rate / 100)), 2) if vat_rate else 0
	doc.erp_expected_gross_rate = erp_rate
	doc.erp_expected_gross_amount = erp_amount
	doc.erp_expected_vat_amount = erp_vat
	doc.rate_difference = flt(doc.pos_gross_rate - erp_rate, 2)
	doc.amount_difference = flt(doc.pos_gross_amount - erp_amount, 2)
	doc.vat_difference = flt(doc.pos_vat_amount - erp_vat, 2)
	doc.difference_percent = flt((doc.rate_difference / erp_rate) * 100, 2) if erp_rate else 0
	doc.reason = _reason(item_doc, {}, doc.pos_gross_rate, erp_rate, doc.pos_vat_amount, erp_vat)
	doc.status = STATUS_RECALCULATED
	doc.reviewed_by = frappe.session.user
	doc.reviewed_on = now_datetime()
	doc.save(ignore_permissions=True)
	return {"status": "Success", "name": doc.name}


def _set_status(name, status):
	doc = frappe.get_doc(AUDIT_DOCTYPE, name)
	doc.check_permission("write")
	doc.status = status
	doc.reviewed_by = frappe.session.user
	doc.reviewed_on = now_datetime()
	doc.save(ignore_permissions=True)
	return {"status": "Success", "name": doc.name}


def _resolve_names(names=None, filters=None):
	if isinstance(names, str):
		names = json.loads(names) if names.strip().startswith("[") else [names]
	if names:
		return names
	if isinstance(filters, list):
		filters = _filters_list_to_dict(filters)
	else:
		filters = frappe._dict(json.loads(filters) if isinstance(filters, str) else (filters or {}))
	db_filters = {"status": STATUS_OPEN}
	for field in ("company", "branch", "counter", "cashier", "cashier_employee", "item_code"):
		if filters.get(field):
			db_filters[field] = filters[field]
	if filters.get("from_date"):
		db_filters["posting_date"] = [">=", filters.from_date]
	if filters.get("to_date"):
		db_filters["posting_date"] = ["between", [filters.get("from_date") or filters.to_date, filters.to_date]]
	return frappe.get_all(AUDIT_DOCTYPE, filters=db_filters, pluck="name")


def _filters_list_to_dict(filters):
	values = {}
	for row in filters or []:
		if isinstance(row, dict) and len(row) >= 4:
			fieldname = row.get("fieldname") or row.get(1)
			value = row.get("value") or row.get(3)
			if fieldname and value:
				values[fieldname] = value
		elif isinstance(row, (list, tuple)) and len(row) >= 4:
			values[row[1]] = row[3]
	return frappe._dict(values)
