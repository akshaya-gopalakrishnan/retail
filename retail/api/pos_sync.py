import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from erpnext.accounts.report.customer_ledger_summary.customer_ledger_summary import (
	PartyLedgerSummaryReport,
)

from retail.pos_login import hash_quick_pin, make_quick_pin_hash, validate_quick_pin


SYNC_SOURCE = "Offline POS"
INTEGRATION_ROLE = "POS Integration User"


def _as_dict(data=None, **kwargs):
	if isinstance(data, str):
		data = json.loads(data)
	if data is None:
		data = _request_json_payload() or _request_form_payload()
	if not isinstance(data, dict):
		frappe.throw(_("Payload must be a JSON object."))
	payload = frappe._dict(data)
	payload.update({key: value for key, value in kwargs.items() if value is not None})
	return payload


def _request_json_payload():
	if not getattr(frappe.local, "request", None):
		return {}

	request = frappe.local.request
	if not request or not request.is_json:
		return {}

	data = request.get_json(silent=True)
	if not data:
		return {}
	return data


def _request_form_payload():
	form_dict = getattr(frappe.local, "form_dict", None)
	if not form_dict:
		return {}

	return {key: value for key, value in form_dict.items() if key not in ("cmd", "data") and value is not None}


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
	counter_doc = frappe.get_doc("POS Branch Counter", name)
	if not cint(counter_doc.allow_offline_sync):
		frappe.throw(_("Offline sync is disabled for counter {0}.").format(counter_code))
	# A production integration user may be assigned to one terminal only. System
	# Managers retain access for support and setup.
	if (
		counter_doc.get("integration_user")
		and counter_doc.integration_user != frappe.session.user
		and "System Manager" not in frappe.get_roles()
	):
		frappe.throw(_("This API user is not assigned to counter {0}.").format(counter_code))
	return counter_doc


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


def _existing_invoice(external_reference):
	"""Find an invoice reference across both invoice doctypes.

	A cancelled document intentionally does not reserve its external reference.
	"""
	if not external_reference:
		frappe.throw(_("external_pos_reference is required."))
	for doctype in ("POS Invoice", "Sales Invoice"):
		fields = ["name", "docstatus", "grand_total", "outstanding_amount"]
		existing = frappe.db.get_value(
			doctype,
			{"external_pos_reference": external_reference, "docstatus": ["!=", 2]},
			fields,
			as_dict=True,
		)
		if existing:
			existing.doctype = doctype
			return existing
	return None


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


def _previous_success(external_reference):
	if not external_reference:
		frappe.throw(_("external_pos_reference is required."))
	return frappe.db.get_value(
		"POS Sync Log",
		{"external_reference": external_reference, "status": ["in", ["Success", "Duplicate"]]},
		["erpnext_docname", "response_json"],
		as_dict=True,
		order_by="creation desc",
	)


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
			docname=(
				response.get("invoice_name")
				or response.get("pos_invoice_name")
				or response.get("payment_entry")
				or response.get("return_invoice")
				or response.get("pos_opening_entry")
				or response.get("pos_closing_entry")
				or response.get("cash_movement")
				or response.get("cashier_shift")
				or response.get("counter_session")
			),
		)
		return response
	except Exception as exc:
		frappe.db.rollback()
		error = frappe.get_traceback()
		_sync_log(sync_type, external_reference, payload, status="Failed", error_message=error)
		return {"status": "Failed", "error": str(exc)}


def _cashier_employee(payload, required=False):
	employee = payload.get("cashier_employee") or payload.get("cashier_id")
	if not employee:
		if required:
			frappe.throw(_("cashier_employee is required."))
		return None
	employee_name = _resolve_employee_identifier(employee)
	if not employee_name:
		frappe.throw(_("Cashier Employee {0} was not found.").format(employee))
	return employee_name


def _resolve_employee_identifier(employee):
	if frappe.db.exists("Employee", employee):
		return employee

	employee_meta = frappe.get_meta("Employee")
	for fieldname in ("employee", "employee_number", "attendance_device_id", "user_id", "cell_number"):
		if not employee_meta.has_field(fieldname):
			continue
		employee_name = frappe.db.get_value("Employee", {fieldname: employee}, "name")
		if employee_name:
			return employee_name
	return None


def _business_date(payload):
	return payload.get("business_date") or payload.get("posting_date") or frappe.utils.today()


def _assert_day_not_closed(branch, business_date=None):
	if not branch:
		return
	business_date = business_date or frappe.utils.today()
	closed = frappe.db.get_value(
		"POS Branch Day Closing",
		{"branch": branch, "business_date": business_date, "docstatus": 1},
		"name",
	)
	if closed:
		frappe.throw(_("POS day is already closed for {0} on {1}: {2}.").format(branch, business_date, closed))


def _submitted_day_closing(branch, business_date=None):
	business_date = business_date or frappe.utils.today()
	return frappe.db.get_value(
		"POS Branch Day Closing",
		{"branch": branch, "business_date": business_date, "docstatus": 1},
		"name",
	)


def _cashier_name(employee):
	return frappe.db.get_value("Employee", employee, "employee_name") if employee else None


def _active_cashier_shift(cashier_employee):
	return frappe.db.get_value(
		"POS Cashier Shift",
		{"cashier_employee": cashier_employee, "status": ["in", ["Open", "Paused"]]},
		"name",
		order_by="creation desc",
	)


def _active_counter_session(counter_name):
	return frappe.db.get_value(
		"POS Counter Session",
		{"counter": counter_name, "status": "Active"},
		["name", "cashier_shift", "cashier_employee", "pos_opening_entry"],
		as_dict=True,
		order_by="creation desc",
	)


def _cashier_shift_doc(name):
	if not name or not frappe.db.exists("POS Cashier Shift", name):
		frappe.throw(_("POS Cashier Shift is required."))
	return frappe.get_doc("POS Cashier Shift", name)


def _counter_session_doc(name):
	if not name or not frappe.db.exists("POS Counter Session", name):
		frappe.throw(_("POS Counter Session is required."))
	return frappe.get_doc("POS Counter Session", name)


def _cash_amount(rows, key):
	total = 0
	for row in rows or []:
		row = frappe._dict(row)
		mode = row.get("mode_of_payment") or row.get("mode")
		if frappe.db.get_value("Mode of Payment", mode, "type") == "Cash":
			total += flt(row.get(key) or row.get("amount"))
	return total


def _expected_cash_for_shift(cashier_shift):
	if not cashier_shift or not frappe.db.has_column("POS Invoice", "pos_cashier_shift"):
		return 0
	opening_amount = flt(frappe.db.get_value("POS Cashier Shift", cashier_shift, "opening_amount"))
	cash_sales = flt(
		frappe.db.sql(
			"""
			select sum(p.amount)
			from `tabSales Invoice Payment` p
			inner join `tabPOS Invoice` i on i.name = p.parent
			inner join `tabMode of Payment` m on m.name = p.mode_of_payment
			where i.docstatus = 1
				and i.pos_cashier_shift = %s
				and m.type = 'Cash'
			""",
			(cashier_shift,),
		)[0][0]
		)
	movements = _cash_movement_totals_for_shift(cashier_shift)
	return opening_amount + cash_sales + movements.cash_in - movements.cash_out


def _cash_movement_totals_for_shift(cashier_shift):
	totals = frappe._dict(cash_in=0, cash_out=0)
	if not cashier_shift or not frappe.db.table_exists("POS Cash Movement"):
		return totals
	rows = frappe.db.sql(
		"""
		select movement_type, sum(amount) as amount
		from `tabPOS Cash Movement`
		where docstatus != 2 and cashier_shift = %s
		group by movement_type
		""",
		(cashier_shift,),
		as_dict=True,
	)
	for row in rows:
		if row.movement_type == "Cash In":
			totals.cash_in = flt(row.amount)
		elif row.movement_type == "Cash Out":
			totals.cash_out = flt(row.amount)
	return totals


def _refresh_cashier_shift_cash_totals(cashier_shift):
	if not cashier_shift:
		return frappe._dict(cash_in=0, cash_out=0, expected_cash=0)
	movements = _cash_movement_totals_for_shift(cashier_shift)
	expected_cash = _expected_cash_for_shift(cashier_shift)
	values = {
		"expected_cash": expected_cash,
	}
	if frappe.db.has_column("POS Cashier Shift", "cash_in_amount"):
		values["cash_in_amount"] = movements.cash_in
	if frappe.db.has_column("POS Cashier Shift", "cash_out_amount"):
		values["cash_out_amount"] = movements.cash_out
	frappe.db.set_value("POS Cashier Shift", cashier_shift, values, update_modified=False)
	return frappe._dict(cash_in=movements.cash_in, cash_out=movements.cash_out, expected_cash=expected_cash)


def _normalize_cash_movement_type(payload):
	movement_type = payload.get("movement_type") or payload.get("type") or payload.get("transaction_type")
	if movement_type:
		normalized = str(movement_type).strip().lower().replace("_", " ").replace("-", " ")
		if normalized in ("cash in", "cashin", "in", "cash add", "cash received"):
			return "Cash In"
		if normalized in ("cash out", "cashout", "out", "petty cash", "expense", "cash used"):
			return "Cash Out"
		if normalized == "ps payment cashin cashout":
			action = str(payload.get("action") or payload.get("direction") or "").strip().lower()
			if action in ("in", "cash in", "cashin"):
				return "Cash In"
			if action in ("out", "cash out", "cashout", "expense", "petty cash"):
				return "Cash Out"

	amount = flt(payload.get("amount"))
	if amount < 0:
		return "Cash Out"
	if amount > 0:
		return "Cash In"
	frappe.throw(_("movement_type is required for cash movement."))


def _movement_amount(payload):
	amount = abs(flt(payload.get("amount")))
	if amount <= 0:
		frappe.throw(_("amount is required and must be greater than zero."))
	return amount


@frappe.whitelist()
def create_pos_cash_movement(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		previous = _previous_success(payload.external_pos_reference)
		if previous and previous.response_json:
			response = json.loads(previous.response_json)
			response["status"] = "Duplicate"
			return response

		existing = _existing_doc("POS Cash Movement", payload.external_pos_reference)
		if existing:
			return {
				"status": "Duplicate",
				"cash_movement": existing.name,
				"external_pos_reference": payload.external_pos_reference,
			}

		counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
		cashier_employee, cashier_shift, counter_session = _validate_active_counter_session(payload, counter_doc)
		movement_type = _normalize_cash_movement_type(payload)
		amount = _movement_amount(payload)
		doc = frappe.get_doc(
			{
				"doctype": "POS Cash Movement",
				"external_pos_reference": payload.external_pos_reference,
				"branch": counter_doc.branch,
				"counter": counter_doc.name,
				"counter_code": counter_doc.counter_code,
				"terminal_id": payload.get("pos_terminal_id") or counter_doc.terminal_id,
				"cashier_employee": cashier_employee,
				"cashier_shift": cashier_shift,
				"counter_session": counter_session,
				"movement_type": movement_type,
				"amount": amount,
				"posting_datetime": (
					payload.get("posting_datetime")
					or payload.get("transaction_datetime")
					or payload.get("pos_local_created_at")
					or now_datetime()
				),
				"description": payload.get("description") or payload.get("reason") or payload.get("remarks"),
				"expense_account": payload.get("expense_account"),
				"source_account": payload.get("source_account"),
				"device_api_user": frappe.session.user,
			}
		)
		doc.insert(ignore_permissions=True)
		totals = _refresh_cashier_shift_cash_totals(cashier_shift)
		return {
			"status": "Success",
			"cash_movement": doc.name,
			"external_pos_reference": payload.external_pos_reference,
			"cashier_shift": cashier_shift,
			"counter_session": counter_session,
			"movement_type": movement_type,
			"amount": amount,
			"cash_in_amount": totals.cash_in,
			"cash_out_amount": totals.cash_out,
			"expected_cash": totals.expected_cash,
		}

	return _run("Cash Movement", payload, handler)


sync_cash_movement = create_pos_cash_movement


def _mark_offline_fields(doc, counter_doc=None, cashier_employee=None, cashier_shift=None, counter_session=None):
	values = {
		"pos_branch_counter": counter_doc.name if counter_doc else None,
		"pos_cashier_employee": cashier_employee,
		"pos_cashier_shift": cashier_shift,
		"pos_counter_session": counter_session,
	}
	for fieldname, value in values.items():
		if value and doc.meta.has_field(fieldname):
			doc.set(fieldname, value)


def _db_set_values(doc, values, update_modified=False):
	for fieldname, value in values.items():
		doc.db_set(fieldname, value, update_modified=update_modified)


def _make_pos_opening_entry(payload, counter_doc, cashier_employee=None, cashier_shift=None, counter_session=None):
	entry = frappe.new_doc("POS Opening Entry")
	entry.company = counter_doc.company
	entry.pos_profile = counter_doc.pos_profile
	entry.user = frappe.session.user
	entry.period_start_date = payload.get("opened_at") or payload.get("started_at") or now_datetime()
	entry.posting_date = payload.get("posting_date") or frappe.utils.today()
	_mark_offline_fields(entry, counter_doc, cashier_employee, cashier_shift, counter_session)

	balances = payload.get("opening_balances") or []
	if not balances:
		balances = [
			{"mode_of_payment": row.mode_of_payment, "opening_amount": 0}
			for row in frappe.get_all("POS Payment Method", {"parent": counter_doc.pos_profile}, ["mode_of_payment"])
		]
	for row in balances:
		entry.append("balance_details", {"mode_of_payment": row.get("mode_of_payment"), "opening_amount": flt(row.get("opening_amount"))})
	if not entry.balance_details:
		frappe.throw(_("opening_balances is required when the POS Profile has no payment methods."))
	entry.insert(ignore_permissions=True)
	entry.submit()
	return entry


def _close_pos_opening_entry(opening_name, closing_balances=None, counter_doc=None, cashier_employee=None, cashier_shift=None, counter_session=None):
	if not opening_name:
		return None
	opening = frappe.get_doc("POS Opening Entry", opening_name)
	if opening.get("status") != "Open":
		existing_closing = frappe.db.get_value(
			"POS Closing Entry",
			{"pos_opening_entry": opening_name, "docstatus": 1},
			"name",
			order_by="creation desc",
		)
		return frappe.get_doc("POS Closing Entry", existing_closing) if existing_closing else None

	from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening

	closing = make_closing_entry_from_opening(opening)
	_mark_offline_fields(closing, counter_doc, cashier_employee, cashier_shift, counter_session)
	actuals = {row.get("mode_of_payment"): flt(row.get("closing_amount")) for row in closing_balances or []}
	for row in closing.payment_reconciliation:
		row.closing_amount = actuals.get(row.mode_of_payment, row.expected_amount)
	closing.insert(ignore_permissions=True)
	closing.submit()
	return closing


def _validate_active_counter_session(payload, counter_doc):
	_assert_day_not_closed(counter_doc.branch, _business_date(payload))
	cashier_shift = payload.get("cashier_shift") or payload.get("cashier_shift_id")
	counter_session = payload.get("counter_session") or payload.get("counter_session_id")
	cashier_employee = _cashier_employee(payload)
	if not (cashier_shift or counter_session or cashier_employee):
		return None, None, None
	if not cashier_shift or not counter_session or not cashier_employee:
		frappe.throw(_("cashier_employee, cashier_shift, and counter_session are required together."))

	shift = _cashier_shift_doc(cashier_shift)
	session = _counter_session_doc(counter_session)
	if shift.cashier_employee != cashier_employee:
		frappe.throw(_("Cashier does not match the cashier shift."))
	if session.cashier_shift != shift.name or session.cashier_employee != cashier_employee:
		frappe.throw(_("Counter session does not match the cashier shift."))
	if session.counter != counter_doc.name:
		frappe.throw(_("Counter session belongs to another counter."))
	if shift.status != "Open" or session.status != "Active":
		frappe.throw(_("Cashier shift and counter session must be active before billing."))
	return cashier_employee, shift.name, session.name


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

	doc = frappe.new_doc("POS Invoice")
	# These values are owned by the server-side counter configuration.  A
	# terminal must not be able to redirect sales into another ledger/location.
	doc.company = counter_doc.company
	doc.customer = customer
	doc.posting_date = payload.get("posting_date") or frappe.utils.today()
	if payload.get("posting_time"):
		doc.posting_time = payload.get("posting_time")
	doc.update_stock = cint(payload.get("update_stock", 1))
	doc.set_warehouse = counter_doc.warehouse
	doc.cost_center = counter_doc.cost_center
	doc.pos_profile = counter_doc.pos_profile
	doc.is_return = 1 if is_return else 0
	doc.return_against = payload.get("original_pos_invoice") if is_return else None

	doc.external_pos_reference = payload.external_pos_reference
	doc.pos_bill_no = payload.get("pos_bill_no")
	doc.pos_branch = counter_doc.branch
	doc.pos_counter = counter_doc.name
	doc.pos_terminal_id = payload.get("pos_terminal_id") or counter_doc.terminal_id
	doc.pos_shift_no = payload.get("pos_shift_no")
	doc.pos_cashier = payload.get("cashier") or frappe.session.user
	cashier_employee, cashier_shift, counter_session = _validate_active_counter_session(payload, counter_doc)
	doc.pos_cashier_employee = cashier_employee
	doc.pos_cashier_shift = cashier_shift
	doc.pos_counter_session = counter_session
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

	default_warehouse = counter_doc.warehouse
	default_cost_center = counter_doc.cost_center

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
				"warehouse": default_warehouse,
				"cost_center": default_cost_center,
			},
		)


def _append_invoice_payments(doc, payload, counter_doc, is_return=False):
	if not payload.get("payments"):
		return

	doc.set("payments", [])
	paid_amount = 0
	for row in payload.get("payments"):
		row = frappe._dict(row)
		amount = flt(row.get("amount"))
		if is_return:
			amount = -abs(amount)
		paid_amount += amount
		doc.append(
			"payments",
			{
				"mode_of_payment": row.get("mode_of_payment") or row.get("mode"),
				"amount": amount,
				"reference_no": row.get("reference_no"),
				"account": _payment_account(counter_doc, row),
			},
		)
	doc.paid_amount = paid_amount
	doc.base_paid_amount = paid_amount * flt(doc.get("conversion_rate") or 1)


def _link_return_items_to_original(doc):
	original_items = frappe.get_all(
		"POS Invoice Item",
		filters={"parent": doc.return_against},
		fields=["name", "item_code"],
		order_by="idx asc",
	)
	items_by_code = {}
	for row in original_items:
		items_by_code.setdefault(row.item_code, []).append(row.name)

	for row in doc.items:
		if row.get("pos_invoice_item"):
			continue
		matches = items_by_code.get(row.item_code) or []
		if not matches:
			continue
		if row.meta.has_field("pos_invoice"):
			row.pos_invoice = doc.return_against
		if row.meta.has_field("pos_invoice_item"):
			row.pos_invoice_item = matches.pop(0)


def _set_profile_taxes(doc, counter_doc):
	"""Taxes are server-owned: the terminal never selects an account head."""
	tax_template = frappe.db.get_value("POS Profile", counter_doc.pos_profile, "taxes_and_charges")
	if tax_template:
		doc.taxes_and_charges = tax_template


def _pos_tax_config(counter_doc):
	"""Expose display-relevant POS tax configuration without exposing accounts."""
	template = frappe.db.get_value("POS Profile", counter_doc.pos_profile, "taxes_and_charges")
	taxes = []
	if template:
		taxes = frappe.get_all(
			"Sales Taxes and Charges",
			filters={"parent": template, "parenttype": "Sales Taxes and Charges Template"},
			fields=["charge_type", "rate", "included_in_print_rate", "idx"],
			order_by="idx asc",
			limit_page_length=0,
		)
	return {"tax_template": template, "taxes": taxes}


def _cashier_master_rows(branch=None, modified_after=None):
	filters = [["status", "=", "Active"]]
	if modified_after:
		filters.append(["modified", ">", modified_after])

	fields = ["name", "employee", "employee_name", "status", "modified"]
	for fieldname in (
		"branch",
		"company",
		"designation",
		"cell_number",
		"user_id",
		"employee_number",
		"pos_login_enabled",
		"pos_quick_pin_hash",
		"pos_quick_pin_salt",
	):
		if frappe.get_meta("Employee").has_field(fieldname):
			fields.append(fieldname)

	rows = frappe.get_all(
		"Employee",
		filters=filters,
		fields=fields,
		limit_page_length=0,
	)
	if branch and frappe.get_meta("Employee").has_field("branch"):
		rows = [row for row in rows if not row.get("branch") or row.get("branch") == branch]
	for row in rows:
		row.login_id = row.get("employee_number") or row.get("employee") or row.get("name")
		row.operator_group = row.get("designation")
		row.quick_pin_hash = row.get("pos_quick_pin_hash")
		row.quick_pin_salt = row.get("pos_quick_pin_salt")
		if "pos_login_enabled" in row and not cint(row.get("pos_login_enabled")):
			row.disabled = 1
	return rows


def _hash_quick_pin(quick_pin, salt):
	return hash_quick_pin(quick_pin, salt)


def _validate_vat(doc, payload):
	"""Check the POS-provided VAT against ERPNext's configured-tax calculation."""
	provided = payload.get("vat_amount")
	if provided is None and payload.get("taxes"):
		provided = sum(flt(row.get("tax_amount")) for row in payload.taxes)
	if provided is None:
		frappe.throw(_("vat_amount is required for external POS invoices."))
	if abs(flt(provided) - flt(doc.total_taxes_and_charges)) > 0.01:
		frappe.throw(
			_("VAT mismatch. POS sent {0}; configured ERPNext taxes calculate {1}.").format(
				flt(provided), flt(doc.total_taxes_and_charges)
			)
		)


@frappe.whitelist()
def health_check(branch=None, counter_code=None):
	_assert_pos_user()
	payload = _as_dict(None, branch=branch, counter_code=counter_code)
	branch = payload.get("branch")
	counter_code = payload.get("counter_code")
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
				"printer_name": counter_doc.get("printer_name"),
			}
		)
	return response


@frappe.whitelist()
def get_pos_master_data(branch=None, counter_code=None, modified_after=None):
	_assert_pos_user()
	payload = _as_dict(None, branch=branch, counter_code=counter_code, modified_after=modified_after)
	branch = payload.get("branch")
	counter_code = payload.get("counter_code")
	modified_after = payload.get("modified_after")
	counter_doc = _counter(branch, counter_code)
	modified_filter = [["modified", ">", modified_after]] if modified_after else []
	packing_fields = [
		"name",
		"packing_code",
		"packing_name",
		"parent as item_code",
		"idx",
		"barcode",
		"barcode_type",
		"uom",
		"conversion_factor",
		"purchase_rate",
		"selling_rate",
		"purchase_net_rate",
		"purchase_vat_amount",
		"purchase_gross_rate",
		"selling_net_rate",
		"selling_vat_amount",
		"selling_gross_rate",
		"packing_margin",
		"modified",
	]
	packing_filters = [
		["parenttype", "=", "Item"],
		["parentfield", "=", "custom_retail_packing_detail"],
	]
	if modified_after:
		packing_filters.append(["modified", ">", modified_after])
	packing_details = frappe.get_all(
		"Retail Packing Detail",
		filters=packing_filters,
		fields=packing_fields,
		order_by="parent asc, idx asc",
		limit_page_length=0,
	)
	packing_parent_items = sorted({row.item_code for row in packing_details if row.item_code})
	item_or_filters = None
	if modified_after:
		item_or_filters = [["modified", ">", modified_after]]
		if packing_parent_items:
			item_or_filters.append(["name", "in", packing_parent_items])

	items = frappe.get_all(
		"Item",
		filters=[] if item_or_filters else modified_filter,
		or_filters=item_or_filters,
		fields=[
			"name",
			"item_code",
			"item_name",
			"custom_arabic_item_name as arabic_item_name",
			"item_group",
			"stock_uom",
			"is_stock_item",
			"custom_scale_item as is_scalable_item",
			"custom_scale_barcode_type as scale_barcode_type",
			"custom_is_open_price as is_open_price",
			"custom_is_fast_plu_item as is_fast_plu_item",
			"disabled",
			"owner as created_by",
			"creation as created_on",
			"modified_by",
			"modified",
			"modified as modified_on",
		],
		limit_page_length=0,
	)
	item_codes = [item.item_code for item in items if item.item_code]
	all_item_packings = []
	if item_codes:
		all_item_packings = frappe.get_all(
			"Retail Packing Detail",
			filters=[
				["parenttype", "=", "Item"],
				["parentfield", "=", "custom_retail_packing_detail"],
				["parent", "in", item_codes],
			],
			fields=packing_fields,
			order_by="parent asc, idx asc",
			limit_page_length=0,
		)
	packings_by_item = {}
	for packing in all_item_packings:
		packings_by_item.setdefault(packing.item_code, []).append(packing)
	for item in items:
		item["packings"] = packings_by_item.get(item.item_code, [])

	return {
		"status": "Success",
		"server_time": now_datetime(),
		"counter": counter_doc.as_dict(),
		"tax_config": _pos_tax_config(counter_doc),
		"items": items,
			"item_barcodes": frappe.get_all(
				"Item Barcode",
				filters=modified_filter,
				fields=["parent as item_code", "barcode", "uom", "modified"],
				limit_page_length=0,
			),
			"packing_details": packing_details,
		"item_prices": frappe.get_all(
			"Item Price",
			filters=modified_filter,
			fields=["name", "item_code", "price_list", "uom", "currency", "price_list_rate", "modified"],
			limit_page_length=0,
		),
		"scale_barcode_formats": frappe.get_all(
			"Scale Barcode Format",
			filters={"enabled": 1},
			fields=[
				"name",
				"format_name",
				"prefix",
				"total_length",
				"prefix_start",
				"prefix_length",
				"plu_start",
				"plu_length",
				"value_start",
				"value_length",
				"value_type",
				"decimal_places",
				"check_digit_enabled",
				"check_digit_method",
				"modified",
			],
			limit_page_length=0,
		),
		"customers": frappe.get_all(
			"Customer",
			filters=[["disabled", "=", 0], *modified_filter],
			fields=["name", "customer_name", "customer_group", "territory", "modified"],
			limit_page_length=0,
		),
		"cashiers": _cashier_master_rows(branch, modified_after),
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
				"printer_name",
				"pos_profile",
			],
			limit_page_length=0,
		),
	}


@frappe.whitelist()
def set_cashier_quick_pin(data=None, **kwargs):
	_assert_pos_user()
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only System Manager can set cashier quick PIN."))
	payload = _as_dict(data, **kwargs)
	employee = payload.get("cashier_employee") or payload.get("employee")
	quick_pin = payload.get("quick_pin")
	if not employee or not frappe.db.exists("Employee", employee):
		frappe.throw(_("Cashier Employee is required."))
	validate_quick_pin(quick_pin)
	if not frappe.get_meta("Employee").has_field("pos_quick_pin_hash"):
		frappe.throw(_("POS quick PIN fields are not installed. Run migration."))
	salt, pin_hash = make_quick_pin_hash(quick_pin)
	frappe.db.set_value(
		"Employee",
		employee,
		{
			"pos_login_enabled": 1,
			"pos_quick_pin_salt": salt,
			"pos_quick_pin_hash": pin_hash,
		},
	)
	return {"status": "Success", "cashier_employee": employee}


@frappe.whitelist()
def verify_cashier_quick_pin(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)
	employee = payload.get("cashier_employee") or payload.get("employee")
	quick_pin = payload.get("quick_pin")
	if not employee or not quick_pin:
		frappe.throw(_("cashier_employee and quick_pin are required."))
	if not frappe.get_meta("Employee").has_field("pos_quick_pin_hash"):
		frappe.throw(_("POS quick PIN fields are not installed. Run migration."))
	row = frappe.db.get_value(
		"Employee",
		employee,
		["status", "pos_login_enabled", "pos_quick_pin_salt", "pos_quick_pin_hash"],
		as_dict=True,
	)
	if not row or row.status != "Active" or not cint(row.pos_login_enabled):
		return {"status": "Failed", "verified": 0}
	verified = _hash_quick_pin(str(quick_pin), row.pos_quick_pin_salt) == row.pos_quick_pin_hash
	return {"status": "Success" if verified else "Failed", "verified": 1 if verified else 0, "cashier_employee": employee}


@frappe.whitelist()
def create_pos_invoice(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		existing = _existing_invoice(payload.external_pos_reference)
		if existing:
			return {
				"status": "Duplicate",
				"pos_invoice_name": existing.name,
				"invoice_name": existing.name,  # compatibility with the first contract
				"doctype": existing.doctype,
				"docstatus": existing.docstatus,
				"grand_total": existing.grand_total,
				"outstanding_amount": existing.outstanding_amount,
			}

		counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
		_assert_day_not_closed(counter_doc.branch, _business_date(payload))
		if not payload.get("payments"):
			frappe.throw(_("Credit POS sales are not supported. Submit a payment or create the credit sale through the backend Sales Invoice process."))
		doc = _base_invoice(payload, counter_doc)
		_append_invoice_items(doc, payload, counter_doc)
		_set_profile_taxes(doc, counter_doc)
		_append_invoice_payments(doc, payload, counter_doc)
		doc.insert(ignore_permissions=True)
		_validate_vat(doc, payload)
		doc.submit()
		return {
			"status": "Success",
			"pos_invoice_name": doc.name,
			"invoice_name": doc.name,
			"doctype": "POS Invoice",
			"docstatus": doc.docstatus,
			"grand_total": doc.grand_total,
			"outstanding_amount": doc.outstanding_amount,
		}

	return _run("Sales Invoice", payload, handler)


@frappe.whitelist()
def create_pos_sales_invoice(data=None, **kwargs):
	"""Deprecated compatibility alias; use create_pos_invoice for new clients."""
	return create_pos_invoice(data, **kwargs)


@frappe.whitelist()
def create_pos_payment_entry(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		existing = _existing_doc("Payment Entry", payload.external_pos_reference)
		if existing:
			return {"status": "Duplicate", "payment_entry": existing.name, "docstatus": existing.docstatus}

		counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
		_assert_day_not_closed(counter_doc.branch, _business_date(payload))
		sales_invoice = payload.get("sales_invoice")
		if (
			not sales_invoice
			and payload.get("sales_invoice_external_reference")
			and frappe.db.has_column("Sales Invoice", "external_pos_reference")
		):
			sales_invoice = frappe.db.get_value(
				"Sales Invoice", {"external_pos_reference": payload.get("sales_invoice_external_reference")}, "name"
			)
		if not sales_invoice:
			frappe.throw(_("Sales Invoice is required for payment sync."))

		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		account = _payment_account(
			counter_doc,
			{"mode_of_payment": payload.get("payment_mode") or payload.get("mode_of_payment")},
		)
		if not account:
			frappe.throw(_("No account is configured for the requested payment mode on this counter."))
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
		cashier_employee, cashier_shift, counter_session = _validate_active_counter_session(payload, counter_doc)
		doc.pos_cashier_employee = cashier_employee
		doc.pos_cashier_shift = cashier_shift
		doc.pos_counter_session = counter_session

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
		existing = _existing_invoice(payload.external_pos_reference)
		if existing:
			return {
				"status": "Duplicate",
				"return_invoice": existing.name,
				"docstatus": existing.docstatus,
				"grand_total": existing.grand_total,
			}

		if not payload.get("original_pos_invoice") and payload.get("original_external_pos_reference"):
			payload.original_pos_invoice = frappe.db.get_value(
				"POS Invoice",
				{"external_pos_reference": payload.original_external_pos_reference, "docstatus": 1},
				"name",
			)
		if not payload.get("original_pos_invoice"):
			frappe.throw(_("original_pos_invoice or original_external_pos_reference is required."))

		counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
		_assert_day_not_closed(counter_doc.branch, _business_date(payload))
		doc = _base_invoice(payload, counter_doc, is_return=True)
		_append_invoice_items(doc, payload, counter_doc, is_return=True)
		_link_return_items_to_original(doc)
		_set_profile_taxes(doc, counter_doc)
		_append_invoice_payments(doc, payload, counter_doc, is_return=True)
		doc.insert(ignore_permissions=True)
		_validate_vat(doc, payload)
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
		pos_invoice = frappe.db.get_value(
			"POS Invoice",
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
		is_synced = bool(pos_invoice or payment_entry or (log and log.status in ("Success", "Duplicate") and log.erpnext_docname))
		result[ref] = {
			"pos_invoice": pos_invoice,
			"payment_entry": payment_entry,
			"latest_log": log,
			"status": "Synced" if is_synced else (log.status if log else "Not Found"),
		}
	return {"status": "Success", "references": result}


@frappe.whitelist()
def get_cashier_shift_status(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)
	counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
	cashier_employee = _cashier_employee(payload, required=True)

	shift_name = _active_cashier_shift(cashier_employee)
	shift = frappe.get_doc("POS Cashier Shift", shift_name).as_dict() if shift_name else None
	counter_session = _active_counter_session(counter_doc.name)
	cashier_session = None
	if shift_name:
		cashier_session = frappe.db.get_value(
			"POS Counter Session",
			{"cashier_shift": shift_name, "status": "Active"},
			["name", "counter", "counter_code", "terminal_id", "pos_opening_entry"],
			as_dict=True,
		)

	can_use_counter = not counter_session or counter_session.cashier_employee == cashier_employee
	return {
		"status": "Success",
		"cashier_employee": cashier_employee,
		"cashier_name": _cashier_name(cashier_employee),
		"cashier_shift": shift,
		"cashier_active_counter_session": cashier_session,
		"counter_active_session": counter_session,
		"can_use_counter": can_use_counter,
		"recommended_action": (
			"OpenNewShift"
			if not shift
			else "ContinueSession"
			if cashier_session and cashier_session.counter == counter_doc.name
			else "TransferOrResume"
			if can_use_counter
			else "CounterBusy"
		),
	}


@frappe.whitelist()
def open_cashier_shift(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		previous = _previous_success(payload.external_pos_reference)
		if previous and previous.response_json:
			response = json.loads(previous.response_json)
			response["status"] = "Duplicate"
			return response

		counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
		_assert_day_not_closed(counter_doc.branch, _business_date(payload))
		cashier_employee = _cashier_employee(payload, required=True)
		active_shift = _active_cashier_shift(cashier_employee)
		if active_shift:
			frappe.throw(_("Cashier already has an open shift: {0}. Use resume_cashier_shift.").format(active_shift))
		active_session = _active_counter_session(counter_doc.name)
		if active_session:
			frappe.throw(_("Counter is already used by cashier {0}.").format(active_session.cashier_employee))

		shift = frappe.get_doc(
			{
				"doctype": "POS Cashier Shift",
				"branch": counter_doc.branch,
				"cashier_employee": cashier_employee,
				"cashier_name": _cashier_name(cashier_employee),
				"status": "Open",
				"opening_time": payload.get("opened_at") or now_datetime(),
				"opening_amount": _cash_amount(payload.get("opening_balances"), "opening_amount"),
				"device_api_user": frappe.session.user,
				"external_open_reference": payload.external_pos_reference,
			}
		)
		shift.insert(ignore_permissions=True)

		session = frappe.get_doc(
			{
				"doctype": "POS Counter Session",
				"cashier_shift": shift.name,
				"branch": counter_doc.branch,
				"counter": counter_doc.name,
				"counter_code": counter_doc.counter_code,
				"terminal_id": payload.get("pos_terminal_id") or counter_doc.terminal_id,
				"status": "Active",
				"cashier_employee": cashier_employee,
				"started_at": payload.get("opened_at") or now_datetime(),
				"opened_by_api_user": frappe.session.user,
				"opening_external_reference": payload.external_pos_reference,
			}
		)
		session.insert(ignore_permissions=True)

		opening = _make_pos_opening_entry(payload, counter_doc, cashier_employee, shift.name, session.name)
		session.db_set("pos_opening_entry", opening.name, update_modified=False)
		_db_set_values(
			shift,
			{
				"current_counter": counter_doc.name,
				"current_counter_session": session.name,
				"device_api_user": frappe.session.user,
			},
			update_modified=False,
		)
		return {
			"status": "Success",
			"cashier_shift": shift.name,
			"counter_session": session.name,
			"pos_opening_entry": opening.name,
			"cashier_employee": cashier_employee,
			"counter": counter_doc.name,
			"counter_code": counter_doc.counter_code,
		}

	return _run("Shift Opening", payload, handler)


@frappe.whitelist()
def pause_cashier_shift(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		previous = _previous_success(payload.external_pos_reference)
		if previous and previous.response_json:
			response = json.loads(previous.response_json)
			response["status"] = "Duplicate"
			return response

		shift = _cashier_shift_doc(payload.get("cashier_shift") or payload.get("cashier_shift_id"))
		session = _counter_session_doc(payload.get("counter_session") or payload.get("counter_session_id"))
		_assert_day_not_closed(shift.branch, _business_date(payload))
		if session.cashier_shift != shift.name:
			frappe.throw(_("Counter session does not belong to this cashier shift."))
		if shift.status not in ("Open", "Paused"):
			frappe.throw(_("Only an open cashier shift can be paused."))
		if session.status != "Active":
			frappe.throw(_("Only an active counter session can be paused."))

		release_counter = cint(payload.get("release_counter", 1))
		closing = None
		if release_counter:
			counter_doc = frappe.get_doc("POS Branch Counter", session.counter)
			closing = _close_pos_opening_entry(
				session.pos_opening_entry,
				payload.get("closing_balances"),
				counter_doc,
				shift.cashier_employee,
				shift.name,
				session.name,
			)
			_db_set_values(
				session,
				{
					"status": "Paused",
					"ended_at": payload.get("paused_at") or now_datetime(),
					"pause_external_reference": payload.external_pos_reference,
					"pos_closing_entry": closing.name if closing else session.pos_closing_entry,
				},
				update_modified=False,
			)
			_db_set_values(shift, {"status": "Paused", "current_counter": None, "current_counter_session": None}, update_modified=False)
		else:
			_db_set_values(session, {"pause_external_reference": payload.external_pos_reference}, update_modified=False)
			_db_set_values(shift, {"status": "Paused"}, update_modified=False)

		return {
			"status": "Success",
			"cashier_shift": shift.name,
			"counter_session": session.name,
			"counter_released": bool(release_counter),
			"pos_closing_entry": closing.name if closing else None,
		}

	return _run("Shift Pause", payload, handler)


@frappe.whitelist()
def resume_cashier_shift(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		previous = _previous_success(payload.external_pos_reference)
		if previous and previous.response_json:
			response = json.loads(previous.response_json)
			response["status"] = "Duplicate"
			return response

		counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
		_assert_day_not_closed(counter_doc.branch, _business_date(payload))
		shift = _cashier_shift_doc(payload.get("cashier_shift") or payload.get("cashier_shift_id"))
		if shift.status not in ("Open", "Paused"):
			frappe.throw(_("Only an open or paused cashier shift can be resumed."))

		active_session = _active_counter_session(counter_doc.name)
		if active_session and active_session.cashier_shift != shift.name:
			frappe.throw(_("Counter is already used by cashier {0}.").format(active_session.cashier_employee))

		current_session = frappe.db.get_value(
			"POS Counter Session",
			{"cashier_shift": shift.name, "status": "Active"},
			["name", "counter", "pos_opening_entry"],
			as_dict=True,
		)
		if current_session and current_session.counter != counter_doc.name:
			frappe.throw(_("Cashier shift is active on another counter. Pause/release it before transfer."))
		if current_session and current_session.counter == counter_doc.name:
			_db_set_values(shift, {"status": "Open", "current_counter": counter_doc.name, "current_counter_session": current_session.name}, update_modified=False)
			return {
				"status": "Success",
				"action": "Continued",
				"cashier_shift": shift.name,
				"counter_session": current_session.name,
				"pos_opening_entry": current_session.pos_opening_entry,
			}

		session = frappe.get_doc(
			{
				"doctype": "POS Counter Session",
				"cashier_shift": shift.name,
				"branch": counter_doc.branch,
				"counter": counter_doc.name,
				"counter_code": counter_doc.counter_code,
				"terminal_id": payload.get("pos_terminal_id") or counter_doc.terminal_id,
				"status": "Active",
				"cashier_employee": shift.cashier_employee,
				"started_at": payload.get("resumed_at") or now_datetime(),
				"opened_by_api_user": frappe.session.user,
				"resume_external_reference": payload.external_pos_reference,
			}
		)
		session.insert(ignore_permissions=True)
		opening = _make_pos_opening_entry(payload, counter_doc, shift.cashier_employee, shift.name, session.name)
		session.db_set("pos_opening_entry", opening.name, update_modified=False)
		_db_set_values(
			shift,
			{"status": "Open", "current_counter": counter_doc.name, "current_counter_session": session.name, "device_api_user": frappe.session.user},
			update_modified=False,
		)
		return {
			"status": "Success",
			"action": "Resumed",
			"cashier_shift": shift.name,
			"counter_session": session.name,
			"pos_opening_entry": opening.name,
			"counter": counter_doc.name,
			"counter_code": counter_doc.counter_code,
		}

	return _run("Shift Resume", payload, handler)


@frappe.whitelist()
def close_cashier_shift(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		previous = _previous_success(payload.external_pos_reference)
		if previous and previous.response_json:
			response = json.loads(previous.response_json)
			response["status"] = "Duplicate"
			return response

		shift = _cashier_shift_doc(payload.get("cashier_shift") or payload.get("cashier_shift_id"))
		_assert_day_not_closed(shift.branch, _business_date(payload))
		if shift.status == "Closed":
			return {"status": "Duplicate", "cashier_shift": shift.name}
		if shift.status not in ("Open", "Paused"):
			frappe.throw(_("Only an open or paused cashier shift can be closed."))

		active_sessions = frappe.get_all(
			"POS Counter Session",
			filters={"cashier_shift": shift.name, "status": "Active"},
			fields=["name", "counter", "pos_opening_entry"],
		)
		closing_names = []
		for session_row in active_sessions:
			session = frappe.get_doc("POS Counter Session", session_row.name)
			counter_doc = frappe.get_doc("POS Branch Counter", session.counter)
			closing = _close_pos_opening_entry(
				session.pos_opening_entry,
				payload.get("closing_balances"),
				counter_doc,
				shift.cashier_employee,
				shift.name,
				session.name,
			)
			_db_set_values(
				session,
				{
					"status": "Closed",
					"ended_at": payload.get("closed_at") or now_datetime(),
					"closing_external_reference": payload.external_pos_reference,
					"pos_closing_entry": closing.name if closing else session.pos_closing_entry,
				},
				update_modified=False,
			)
			if closing:
				closing_names.append(closing.name)

		frappe.db.set_value(
			"POS Counter Session",
			{"cashier_shift": shift.name, "status": "Paused"},
			{
				"status": "Closed",
				"closing_external_reference": payload.external_pos_reference,
			},
			update_modified=False,
		)

		closing_amount = _cash_amount(payload.get("closing_balances"), "closing_amount")
		movements = _cash_movement_totals_for_shift(shift.name)
		expected_cash = _expected_cash_for_shift(shift.name)
		values = {
			"status": "Closed",
			"closing_time": payload.get("closed_at") or now_datetime(),
			"expected_cash": expected_cash,
			"closing_amount": closing_amount,
			"variance": closing_amount - expected_cash,
			"external_close_reference": payload.external_pos_reference,
			"current_counter": None,
			"current_counter_session": None,
		}
		if frappe.db.has_column("POS Cashier Shift", "cash_in_amount"):
			values["cash_in_amount"] = movements.cash_in
		if frappe.db.has_column("POS Cashier Shift", "cash_out_amount"):
			values["cash_out_amount"] = movements.cash_out
		_db_set_values(shift, values, update_modified=False)
		return {"status": "Success", "cashier_shift": shift.name, "pos_closing_entries": closing_names}

	return _run("Shift Closing", payload, handler)


@frappe.whitelist()
def reopen_cashier_shift(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)
	reason = payload.get("reason") or payload.get("reopen_reason")
	if not reason:
		frappe.throw(_("reopen_reason is required."))

	shift = _cashier_shift_doc(payload.get("cashier_shift") or payload.get("cashier_shift_id"))
	business_date = payload.get("business_date") or (str(shift.opening_time)[:10] if shift.opening_time else frappe.utils.today())
	closed_day = _submitted_day_closing(shift.branch, business_date)
	if closed_day:
		frappe.throw(_("Cancel day closing {0} before reopening this cashier shift.").format(closed_day))
	if shift.status != "Closed":
		frappe.throw(_("Only a closed cashier shift can be reopened."))

	_db_set_values(
		shift,
		{
			"status": "Paused",
			"closing_time": None,
			"closing_amount": 0,
			"variance": 0,
			"external_close_reference": None,
			"current_counter": None,
			"current_counter_session": None,
			"reopened_at": now_datetime(),
			"reopened_by": frappe.session.user,
			"reopen_reason": reason,
			"reopen_count": cint(shift.get("reopen_count")) + 1,
		},
		update_modified=True,
	)
	_sync_log(
		"Shift Reopen",
		payload.get("external_pos_reference"),
		payload,
		response={"cashier_shift": shift.name, "status": "Success"},
		status="Success",
		docname=shift.name,
	)
	return {"status": "Success", "cashier_shift": shift.name, "shift_status": "Paused"}


@frappe.whitelist()
def make_branch_day_closing(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)
	branch = payload.get("branch")
	business_date = payload.get("business_date") or payload.get("posting_date") or frappe.utils.today()
	if not branch:
		frappe.throw(_("Branch is required."))
	from retail.retail_app.doctype.pos_branch_day_closing.pos_branch_day_closing import make_day_closing

	return make_day_closing(branch, business_date)


@frappe.whitelist()
def cancel_branch_day_closing(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)
	branch = payload.get("branch")
	business_date = payload.get("business_date") or payload.get("posting_date") or frappe.utils.today()
	reason = payload.get("reason") or payload.get("cancel_reason")
	if not branch:
		frappe.throw(_("Branch is required."))
	from retail.retail_app.doctype.pos_branch_day_closing.pos_branch_day_closing import cancel_day_closing

	return cancel_day_closing(branch, business_date, reason)


@frappe.whitelist()
def submit_branch_day_closing(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)
	branch = payload.get("branch")
	business_date = payload.get("business_date") or payload.get("posting_date") or frappe.utils.today()
	if not branch:
		frappe.throw(_("Branch is required."))
	from retail.retail_app.doctype.pos_branch_day_closing.pos_branch_day_closing import submit_day_closing

	return submit_day_closing(branch, business_date)


@frappe.whitelist()
def open_pos_shift(data=None, **kwargs):
	"""Open the ERPNext POS shift required before submitting POS Invoices."""
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		if not payload.get("external_pos_reference"):
			frappe.throw(_("external_pos_reference is required."))
		previous = frappe.db.get_value(
			"POS Sync Log",
			{"external_reference": payload.external_pos_reference, "status": ["in", ["Success", "Duplicate"]]},
			"erpnext_docname",
			order_by="creation desc",
		)
		if previous:
			return {"status": "Duplicate", "pos_opening_entry": previous}
		counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
		_assert_day_not_closed(counter_doc.branch, _business_date(payload))
		open_entry = frappe.db.get_value(
			"POS Opening Entry",
			{"pos_profile": counter_doc.pos_profile, "user": frappe.session.user, "status": "Open", "docstatus": 1},
			"name",
		)
		if open_entry:
			frappe.throw(
				_("An open POS shift ({0}) already exists for this terminal. Use its original external_pos_reference or close it first.").format(
					open_entry
				)
			)

		entry = frappe.new_doc("POS Opening Entry")
		entry.company = counter_doc.company
		entry.pos_profile = counter_doc.pos_profile
		entry.user = frappe.session.user
		entry.period_start_date = payload.get("opened_at") or now_datetime()
		entry.posting_date = payload.get("posting_date") or frappe.utils.today()
		balances = payload.get("opening_balances") or []
		if not balances:
			balances = [
				{"mode_of_payment": row.mode_of_payment, "opening_amount": 0}
				for row in frappe.get_all("POS Payment Method", {"parent": counter_doc.pos_profile}, ["mode_of_payment"])
			]
		for row in balances:
			entry.append("balance_details", {"mode_of_payment": row.get("mode_of_payment"), "opening_amount": flt(row.get("opening_amount"))})
		if not entry.balance_details:
			frappe.throw(_("opening_balances is required when the POS Profile has no payment methods."))
		entry.insert(ignore_permissions=True)
		entry.submit()
		return {"status": "Success", "pos_opening_entry": entry.name, "opened_at": entry.period_start_date}

	return _run("Shift Opening", payload, handler)


@frappe.whitelist()
def close_pos_shift(data=None, **kwargs):
	"""Create the ERPNext reconciliation/closing entry for the active terminal shift."""
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		if not payload.get("external_pos_reference"):
			frappe.throw(_("external_pos_reference is required."))
		previous = frappe.db.get_value(
			"POS Sync Log",
			{"external_reference": payload.external_pos_reference, "status": ["in", ["Success", "Duplicate"]]},
			"erpnext_docname",
			order_by="creation desc",
		)
		if previous:
			return {"status": "Duplicate", "pos_closing_entry": previous}
		counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
		_assert_day_not_closed(counter_doc.branch, _business_date(payload))
		opening_name = payload.get("pos_opening_entry") or frappe.db.get_value(
			"POS Opening Entry",
			{"pos_profile": counter_doc.pos_profile, "user": frappe.session.user, "status": "Open", "docstatus": 1},
			"name",
		)
		if not opening_name:
			frappe.throw(_("No open POS shift exists for this terminal."))
		from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening

		closing = make_closing_entry_from_opening(frappe.get_doc("POS Opening Entry", opening_name))
		actuals = {row.get("mode_of_payment"): flt(row.get("closing_amount")) for row in payload.get("closing_balances", [])}
		for row in closing.payment_reconciliation:
			row.closing_amount = actuals.get(row.mode_of_payment, row.expected_amount)
		closing.insert(ignore_permissions=True)
		closing.submit()
		return {"status": "Success", "pos_closing_entry": closing.name, "pos_opening_entry": opening_name, "closing_status": closing.status}

	return _run("Shift Closing", payload, handler)


@frappe.whitelist()
def upsert_customer(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)

	def handler():
		_counter(payload.get("branch"), payload.get("counter_code"))
		external_id = payload.get("external_customer_id")
		if not external_id:
			frappe.throw(_("external_customer_id is required."))
		name = frappe.db.get_value("Customer", {"external_pos_customer_id": external_id}, "name")
		values = {key: payload.get(key) for key in ("customer_name", "customer_group", "territory", "mobile_no", "email_id", "tax_id") if payload.get(key) is not None}
		values["external_pos_customer_id"] = external_id
		if name:
			frappe.db.set_value("Customer", name, values)
			return {"status": "Success", "action": "Updated", "customer": name}
		if not values.get("customer_name"):
			frappe.throw(_("customer_name is required for a new customer."))
		customer = frappe.get_doc({"doctype": "Customer", **values})
		customer.insert(ignore_permissions=True)
		return {"status": "Success", "action": "Created", "customer": customer.name}

	return _run("Customer Upsert", payload, handler)


def _default_company():
	companies = frappe.get_all("Company", pluck="name", limit=2)
	if len(companies) == 1:
		return companies[0]
	return None


def _customer_balance_details(customers=None):
	filters = {"disabled": 0}
	if customers:
		filters["name"] = ["in", customers]

	rows = frappe.get_all(
		"Customer",
		filters=filters,
		fields=[
			"name",
			"customer_name",
			"email_id",
			"mobile_no",
			"customer_primary_address",
			"primary_address",
		],
		order_by="customer_name asc",
	)

	return {row.name: row for row in rows}


def _customer_ledger_rows(company, from_date, to_date, customer=None):
	filters = frappe._dict(
		{
			"company": company,
			"from_date": getdate(from_date),
			"to_date": getdate(to_date),
			"party": customer,
		}
	)
	args = {
		"party_type": "Customer",
		"naming_by": ["Selling Settings", "cust_master_name"],
	}

	_, rows = PartyLedgerSummaryReport(filters).run(args)
	return {row.party: row for row in rows}


def _format_customer_balance(customer, ledger=None):
	ledger = ledger or frappe._dict()

	return {
		"customer": customer.name,
		"customer_name": customer.customer_name,
		"email": customer.email_id,
		"phone": customer.mobile_no,
		"opening_balance": flt(ledger.get("opening_balance")),
		"transaction_amount": flt(ledger.get("invoiced_amount")),
		"payment_amount": flt(ledger.get("paid_amount")),
		"current_balance": flt(ledger.get("closing_balance")),
		"address": customer.primary_address,
		"address_id": customer.customer_primary_address,
	}


@frappe.whitelist()
def get_customer_balances(
	company=None,
	from_date=None,
	to_date=None,
	customer=None,
	include_zero_balance=0,
):
	_assert_pos_user()

	company = company or _default_company()
	if not company:
		frappe.throw(_("Company is required."))

	from_date = from_date or frappe.db.get_default("year_start_date") or nowdate()
	to_date = to_date or nowdate()
	include_zero_balance = cint(include_zero_balance)

	if getdate(from_date) > getdate(to_date):
		frappe.throw(_("From Date must be before To Date"))

	if customer and not frappe.db.exists("Customer", customer):
		frappe.throw(_("Customer {0} was not found.").format(customer))

	ledger_by_customer = _customer_ledger_rows(company, from_date, to_date, customer=customer)
	customer_filter = [customer] if customer else None
	if not customer_filter and not include_zero_balance:
		customer_filter = ledger_by_customer.keys()

	customers = _customer_balance_details(customer_filter)
	data = []
	for customer_name, customer_row in customers.items():
		ledger = ledger_by_customer.get(customer_name)
		if not include_zero_balance and not ledger:
			continue
		data.append(_format_customer_balance(customer_row, ledger))

	return {
		"status": "Success",
		"company": company,
		"from_date": str(getdate(from_date)),
		"to_date": str(getdate(to_date)),
		"count": len(data),
		"data": data,
	}


@frappe.whitelist()
def get_warehouse_stock_snapshot(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)
	counter_doc = _counter(payload.get("branch"), payload.get("counter_code"))
	item_codes = payload.get("item_codes") or []
	filters = {"warehouse": counter_doc.warehouse}
	if item_codes:
		filters["item_code"] = ["in", item_codes]
	return {
		"status": "Success",
		"warehouse": counter_doc.warehouse,
		"generated_at": now_datetime(),
		"stock": frappe.get_all(
			"Bin",
			filters,
			[
				"item_code",
				"actual_qty",
				"actual_qty as current_stock",
				"reserved_qty",
				"projected_qty",
				"stock_value",
				"modified",
				"modified as modified_on",
			],
			limit_page_length=0,
		),
	}


@frappe.whitelist()
def get_queue_dependencies(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)
	_counter(payload.get("branch"), payload.get("counter_code"))
	dependencies = {}
	for row in payload.get("queue", []):
		row = frappe._dict(row)
		ref = row.get("external_pos_reference")
		original_ref = row.get("original_external_pos_reference")
		original_exists = not original_ref or bool(_existing_invoice(original_ref))
		dependencies[ref] = {
			"already_synced": bool(_existing_invoice(ref)),
			"original_invoice_synced": original_exists,
			"can_sync": original_exists,
		}
	return {"status": "Success", "dependencies": dependencies}


@frappe.whitelist()
def ingest_queue_errors(data=None, **kwargs):
	_assert_pos_user()
	payload = _as_dict(data, **kwargs)
	_counter(payload.get("branch"), payload.get("counter_code"))
	accepted = []
	for event in payload.get("errors", []):
		event = frappe._dict(event)
		log = _sync_log(
			"Queue Error", event.get("external_pos_reference"), payload,
			response={"client_error": event.get("error"), "queue_status": event.get("status")},
			status="Failed", error_message=event.get("error"),
		)
		accepted.append(log.name)
	return {"status": "Success", "logs": accepted}


def validate_external_reference(doc: Document, method=None):
	if not doc.get("external_pos_reference"):
		return

	doctypes = ["POS Invoice"]
	if frappe.db.has_column("Sales Invoice", "external_pos_reference"):
		doctypes.append("Sales Invoice")

	for doctype in doctypes:
		duplicate = frappe.db.get_value(
			doctype,
			{"external_pos_reference": doc.external_pos_reference, "name": ["!=", doc.name], "docstatus": ["!=", 2]},
			"name",
		)
		if duplicate:
			frappe.throw(_("External POS reference {0} is already used by {1} {2}.").format(frappe.bold(doc.external_pos_reference), doctype, frappe.bold(duplicate)))


def block_external_sales_invoice(doc: Document, method=None):
	"""The restricted POS user can only create POS Invoice documents through this API."""
	if doc.doctype == "Sales Invoice" and INTEGRATION_ROLE in frappe.get_roles() and "System Manager" not in frappe.get_roles():
		frappe.throw(
			_("External POS must use create_pos_invoice; direct Sales Invoice creation is blocked.")
		)
