import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime


SYNC_SOURCE = "Offline POS"
INTEGRATION_ROLE = "POS Integration User"


def _as_dict(data=None, **kwargs):
	if isinstance(data, str):
		data = json.loads(data)
	if data is None:
		data = {}
	if not isinstance(data, dict):
		frappe.throw(_("Payload must be a JSON object."))
	payload = frappe._dict(data)
	payload.update({key: value for key, value in kwargs.items() if value is not None})
	return payload


def _json(data):
	return json.dumps(data, default=str, indent=2, sort_keys=True)


def _assert_pos_user():
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication is required."))
	if "System Manager" in frappe.get_roles() or INTEGRATION_ROLE in frappe.get_roles():
		return
	frappe.throw(_("User requires {0} role.").format(INTEGRATION_ROLE))


def _counter(branch, counter_code):
	if not branch or not counter_code:
		frappe.throw(_("Branch and counter_code are required."))

	name = frappe.db.get_value(
		"POS Branch Counter",
		{"branch": branch, "counter_code": counter_code, "is_active": 1},
		"name",
	)
	if not name:
		frappe.throw(_("Active POS Branch Counter not found for {0} / {1}.").format(branch, counter_code))
	return frappe.get_doc("POS Branch Counter", name)


def _existing_doc(doctype, external_reference):
	if not external_reference:
		frappe.throw(_("external_pos_reference is required."))

	fields = ["name", "docstatus"]
	if doctype == "Sales Invoice":
		fields.extend(["grand_total", "outstanding_amount"])

	return frappe.db.get_value(
		doctype,
		{"external_pos_reference": external_reference, "docstatus": ["!=", 2]},
		fields,
		as_dict=True,
	)


def _sync_log(sync_type, external_reference, payload, response=None, status="Pending", error_message=None, docname=None):
	doc = frappe.get_doc(
		{
			"doctype": "POS Sync Log",
			"sync_type": sync_type,
			"external_reference": external_reference,
			"erpnext_docname": docname,
			"status": status,
			"request_json": _json(payload) if payload else None,
			"response_json": _json(response) if response else None,
			"error_message": error_message,
			"attempt_count": 1,
			"branch": payload.get("branch") if isinstance(payload, dict) else None,
			"counter": payload.get("counter_code") if isinstance(payload, dict) else None,
			"created_at": now_datetime(),
			"last_attempt_at": now_datetime(),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def _run(sync_type, payload, handler):
	external_reference = payload.get("external_pos_reference")
	try:
		response = handler()
		_sync_log(
			sync_type,
			external_reference,
			payload,
			response=response,
			status=response.get("status", "Success"),
			docname=response.get("invoice_name") or response.get("payment_entry") or response.get("return_invoice"),
		)
		return response
	except Exception as exc:
		frappe.db.rollback()
		error = frappe.get_traceback()
		_sync_log(sync_type, external_reference, payload, status="Failed", error_message=error)
		return {"status": "Failed", "error": str(exc)}


def _legacy_counter_name(counter_doc):
	for value in (counter_doc.counter_code, counter_doc.counter_name):
		if value and frappe.db.exists("Counter", value):
			return value
		if value:
			name = frappe.db.get_value("Counter", {"counter_name": value}, "name")
			if name:
				return name
	return None


def _resolve_item(row):
	item_code = row.get("item_code")
	barcode = row.get("barcode")
	if not item_code and barcode:
		item_code = frappe.db.get_value("Item Barcode", {"barcode": barcode}, "parent")
	if not item_code or not frappe.db.exists("Item", item_code):
		frappe.throw(_("Item not found for row {0}.").format(row))
	return item_code


def _payment_account(counter_doc, payment):
	if payment.get("account"):
		return payment.get("account")

	mode = payment.get("mode_of_payment")
	mode_type = frappe.db.get_value("Mode of Payment", mode, "type") if mode else None
	if mode_type == "Cash":
		return counter_doc.cash_account
	if mode_type in ("Bank", "Card"):
		return counter_doc.card_account
	return None


def _base_invoice(payload, counter_doc, is_return=False):
	customer = payload.get("customer") or counter_doc.default_customer
	if not customer:
		frappe.throw(_("Customer is required or default_customer must be set on the POS Branch Counter."))

	doc = frappe.new_doc("Sales Invoice")
	doc.company = payload.get("company") or counter_doc.company
	doc.customer = customer
	doc.posting_date = payload.get("posting_date") or frappe.utils.today()
	if payload.get("posting_time"):
		doc.posting_time = payload.get("posting_time")
	doc.is_pos = cint(payload.get("is_pos", 1))
	doc.update_stock = cint(payload.get("update_stock", 1))
	doc.set_warehouse = payload.get("warehouse") or counter_doc.warehouse
	doc.cost_center = payload.get("cost_center") or counter_doc.cost_center
	doc.pos_profile = payload.get("pos_profile") or counter_doc.pos_profile
	doc.is_return = 1 if is_return else 0
	doc.return_against = payload.get("original_sales_invoice") if is_return else None

	doc.external_pos_reference = payload.external_pos_reference
	doc.pos_bill_no = payload.get("pos_bill_no")
	doc.pos_branch = counter_doc.branch
	doc.pos_counter = counter_doc.name
	doc.pos_terminal_id = payload.get("pos_terminal_id") or counter_doc.terminal_id
	doc.pos_shift_no = payload.get("pos_shift_no")
	doc.pos_cashier = payload.get("cashier") or frappe.session.user
	doc.pos_sync_source = SYNC_SOURCE
	doc.pos_sync_datetime = now_datetime()
	doc.pos_local_created_at = payload.get("pos_local_created_at")
	doc.pos_original_reference = payload.get("original_external_pos_reference")

	legacy_counter = _legacy_counter_name(counter_doc)
	if legacy_counter and doc.meta.has_field("custom_counter"):
		doc.custom_counter = legacy_counter

	return doc


def _append_invoice_items(doc, payload, counter_doc, is_return=False):
	items = payload.get("items") or []
	if not items:
		frappe.throw(_("At least one item is required."))

	default_warehouse = payload.get("warehouse") or counter_doc.warehouse
	default_cost_center = payload.get("cost_center") or counter_doc.cost_center

	for row in items:
		row = frappe._dict(row)
		qty = flt(row.get("qty"))
		if is_return:
			qty = -abs(qty)
		elif qty <= 0:
			frappe.throw(_("Item quantity must be greater than zero."))

		doc.append(
			"items",
			{
				"item_code": _resolve_item(row),
				"qty": qty,
				"rate": flt(row.get("rate")),
				"discount_amount": flt(row.get("discount_amount")),
				"warehouse": row.get("warehouse") or default_warehouse,
				"cost_center": row.get("cost_center") or default_cost_center,
			},
		)


def _append_invoice_payments(doc, payload, counter_doc, is_return=False):
	if not payload.get("payments"):
		return

	doc.set("payments", [])
	for row in payload.get("payments"):
		row = frappe._dict(row)
		amount = flt(row.get("amount"))
		if is_return:
			amount = -abs(amount)
		doc.append(
			"payments",
			{
				"mode_of_payment": row.get("mode_of_payment") or row.get("mode"),
				"amount": amount,
				"reference_no": row.get("reference_no"),
				"account": _payment_account(counter_doc, row),
			},
		)


def _append_taxes(doc, payload):
	if not payload.get("taxes"):
		return

	doc.set("taxes", [])
	for row in payload.get("taxes"):
		row = frappe._dict(row)
		doc.append(
			"taxes",
			{
				"charge_type": row.get("charge_type") or "On Net Total",
				"account_head": row.get("account_head"),
				"description": row.get("description") or row.get("account_head"),
				"rate": flt(row.get("rate")),
				"tax_amount": flt(row.get("tax_amount")),
				"included_in_print_rate": cint(row.get("included_in_print_rate")),
			},
		)


@frappe.whitelist()
def health_check(branch=None, counter_code=None):
	_assert_pos_user()
	response = {
		"status": "OK",
		"server_time": now_datetime(),
	}
	if branch and counter_code:
		counter_doc = _counter(branch, counter_code)
		response.update(
			{
				"company": counter_doc.company,
				"branch": counter_doc.branch,
				"warehouse": counter_doc.warehouse,
				"cost_center": counter_doc.cost_center,
				"counter": counter_doc.name,
				"terminal_id": counter_doc.terminal_id,
			}
		)
	return response


@frappe.whitelist()
def get_pos_master_data(branch=None, counter_code=None, modified_after=None):
	_assert_pos_user()
	counter_doc = _counter(branch, counter_code)
	modified_filter = [["modified", ">", modified_after]] if modified_after else []

	return {
		"status": "Success",
		"server_time": now_datetime(),
		"counter": counter_doc.as_dict(),
		"items": frappe.get_all(
			"Item",
			filters=[["disabled", "=", 0], *modified_filter],
			fields=["name", "item_code", "item_name", "item_group", "stock_uom", "is_stock_item", "modified"],
			limit_page_length=0,
		),
		"item_barcodes": frappe.get_all(
			"Item Barcode",
			filters=modified_filter,
			fields=["parent as item_code", "barcode", "uom", "modified"],
			limit_page_length=0,
		),
		"item_prices": frappe.get_all(
			"Item Price",
			filters=modified_filter,
			fields=["name", "item_code", "price_list", "uom", "currency", "price_list_rate", "modified"],
			limit_page_length=0,
		),
		"customers": frappe.get_all(
			"Customer",
			filters=[["disabled", "=", 0], *modified_filter],
			fields=["name", "customer_name", "customer_group", "territory", "modified"],
			limit_page_length=0,
		),
		"modes_of_payment": frappe.get_all(
			"Mode of Payment",
			filters=modified_filter,
			fields=["name", "type", "enabled", "modified"],
			limit_page_length=0,
		),
		"counters": frappe.get_all(
			"POS Branch Counter",
			filters={"branch": branch, "is_active": 1},
			fields=[
				"name",
				"branch",
				"warehouse",
				"cost_center",
				"counter_code",
				"counter_name",
				"terminal_id",
				"pos_profile",
			],
			limit_page_length=0,
		),
	}


@frappe.whitelist()
def create_pos_sales_invoice(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		existing = _existing_doc("Sales Invoice", payload.external_pos_reference)
		if existing:
			return {
				"status": "Duplicate",
				"invoice_name": existing.name,
				"docstatus": existing.docstatus,
				"grand_total": existing.grand_total,
				"outstanding_amount": existing.outstanding_amount,
			}

		counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
		doc = _base_invoice(payload, counter_doc)
		_append_invoice_items(doc, payload, counter_doc)
		_append_taxes(doc, payload)
		_append_invoice_payments(doc, payload, counter_doc)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return {
			"status": "Success",
			"invoice_name": doc.name,
			"docstatus": doc.docstatus,
			"grand_total": doc.grand_total,
			"outstanding_amount": doc.outstanding_amount,
		}

	return _run("Sales Invoice", payload, handler)


@frappe.whitelist()
def create_pos_payment_entry(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		existing = _existing_doc("Payment Entry", payload.external_pos_reference)
		if existing:
			return {"status": "Duplicate", "payment_entry": existing.name, "docstatus": existing.docstatus}

		counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
		sales_invoice = payload.get("sales_invoice") or frappe.db.get_value(
			"Sales Invoice", {"external_pos_reference": payload.get("sales_invoice_external_reference")}, "name"
		)
		if not sales_invoice:
			frappe.throw(_("Sales Invoice is required for payment sync."))

		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		account = payload.get("account") or counter_doc.cash_account or counter_doc.card_account
		doc = get_payment_entry("Sales Invoice", sales_invoice, bank_account=account)
		doc.mode_of_payment = payload.get("payment_mode") or payload.get("mode_of_payment")
		doc.reference_no = payload.get("reference_no") or payload.external_pos_reference
		doc.reference_date = payload.get("posting_date") or frappe.utils.today()
		doc.posting_date = payload.get("posting_date") or frappe.utils.today()
		doc.external_pos_reference = payload.external_pos_reference
		doc.pos_branch = counter_doc.branch
		doc.pos_counter = counter_doc.name
		doc.pos_terminal_id = payload.get("pos_terminal_id") or counter_doc.terminal_id
		doc.pos_sync_source = SYNC_SOURCE
		doc.pos_sync_datetime = now_datetime()

		amount = flt(payload.get("paid_amount"))
		if amount:
			doc.paid_amount = amount
			doc.received_amount = amount
			for row in doc.references:
				row.allocated_amount = min(amount, flt(row.outstanding_amount or row.total_amount))
		doc.save(ignore_permissions=True)
		doc.submit()
		return {"status": "Success", "payment_entry": doc.name, "docstatus": doc.docstatus}

	return _run("Payment Entry", payload, handler)


@frappe.whitelist()
def create_pos_return_invoice(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		existing = _existing_doc("Sales Invoice", payload.external_pos_reference)
		if existing:
			return {
				"status": "Duplicate",
				"return_invoice": existing.name,
				"docstatus": existing.docstatus,
				"grand_total": existing.grand_total,
			}

		if not payload.get("original_sales_invoice") and payload.get("original_external_pos_reference"):
			payload.original_sales_invoice = frappe.db.get_value(
				"Sales Invoice",
				{"external_pos_reference": payload.original_external_pos_reference, "docstatus": 1},
				"name",
			)
		if not payload.get("original_sales_invoice"):
			frappe.throw(_("original_sales_invoice or original_external_pos_reference is required."))

		counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
		doc = _base_invoice(payload, counter_doc, is_return=True)
		_append_invoice_items(doc, payload, counter_doc, is_return=True)
		_append_taxes(doc, payload)
		_append_invoice_payments(doc, payload, counter_doc, is_return=True)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return {
			"status": "Success",
			"return_invoice": doc.name,
			"docstatus": doc.docstatus,
			"grand_total": doc.grand_total,
			"outstanding_amount": doc.outstanding_amount,
		}

	return _run("Return", payload, handler)


@frappe.whitelist()
def get_sync_status(data=None, external_references=None):
	_assert_pos_user()
	payload = _as_dict(data) if data else frappe._dict()
	refs = external_references or payload.get("external_references") or []
	if isinstance(refs, str):
		refs = json.loads(refs)

	result = {}
	for ref in refs:
		sales_invoice = frappe.db.get_value(
			"Sales Invoice",
			{"external_pos_reference": ref, "docstatus": ["!=", 2]},
			["name", "docstatus", "grand_total", "outstanding_amount"],
			as_dict=True,
		)
		payment_entry = frappe.db.get_value(
			"Payment Entry",
			{"external_pos_reference": ref, "docstatus": ["!=", 2]},
			["name", "docstatus"],
			as_dict=True,
		)
		log = frappe.db.get_value(
			"POS Sync Log",
			{"external_reference": ref},
			["name", "sync_type", "status", "erpnext_docname", "error_message"],
			as_dict=True,
			order_by="creation desc",
		)
		result[ref] = {
			"sales_invoice": sales_invoice,
			"payment_entry": payment_entry,
			"latest_log": log,
			"status": "Synced" if sales_invoice or payment_entry else (log.status if log else "Not Found"),
		}
	return {"status": "Success", "references": result}


def validate_external_reference(doc: Document, method=None):
	if not doc.get("external_pos_reference"):
		return

	duplicate = frappe.db.get_value(
		doc.doctype,
		{
			"external_pos_reference": doc.external_pos_reference,
			"name": ["!=", doc.name],
			"docstatus": ["!=", 2],
		},
		"name",
	)
	if duplicate:
		frappe.throw(
			_("External POS reference {0} is already used by {1}.").format(
				frappe.bold(doc.external_pos_reference), frappe.bold(duplicate)
			)
		)
