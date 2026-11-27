"""Driver-scoped mobile API. All stock/accounting posts use native ERP documents."""
import hashlib
import json
import math
from decimal import Decimal, InvalidOperation

import frappe
from frappe.utils import cint, flt, getdate, get_datetime, now_datetime, nowdate, get_system_timezone

ALIASES = {
	"driver_id": "driverid", "session_id": "sessionid", "van_id": "vanid",
	"organization_id": "organizationid", "customer_id": "customerid",
	"request_id": "requestid", "invoice_id": "invoiceid",
}


def _payload(data=None, **kwargs):
	if isinstance(data, str):
		data = frappe.parse_json(data)
	if data is not None and not isinstance(data, dict):
		frappe.throw("Request data must be a JSON object.")
	p = dict(data or {})
	p.update({k: v for k, v in kwargs.items() if k not in {"cmd", "csrf_token"}})
	for alias, key in ALIASES.items():
		if alias in p:
			if key in p and p[key] != p[alias]:
				frappe.throw(f"{alias} and {key} must match.")
			p[key] = p.pop(alias)
	return frappe._dict(p)


def _require():
	if frappe.session.user == "Guest":
		frappe.throw("Authentication is required.", frappe.AuthenticationError)
	from retail.module_access import require
	require("Van Sales")
	if frappe.session.user != "Administrator" and not set(frappe.get_roles()).intersection(
		{"Van Sales User", "Van Sales Manager", "System Manager"}
	):
		frappe.throw("Van Sales access is required.", frappe.PermissionError)


def _manager():
	return frappe.session.user == "Administrator" or bool(
		set(frappe.get_roles()).intersection({"Van Sales Manager", "System Manager"})
	)


def _driver(p):
	_require()
	if _manager() and p.get("driverid"):
		name = p.driverid
	else:
		names = frappe.get_all("Driver", filters={"custom_van_user": frappe.session.user}, pluck="name", limit=2)
		if len(names) != 1:
			frappe.throw("Assign exactly one Driver to this Van Sales Login.", frappe.PermissionError)
		name = names[0]
		if p.get("driverid") and p.driverid != name:
			frappe.throw("Driver does not match the authenticated user.", frappe.PermissionError)
	driver = frappe.get_doc("Driver", name)
	if driver.get("status") != "Active":
		frappe.throw("Driver is not active.", frappe.PermissionError)
	return driver


def _context(p, *, active=False, lock=False):
	driver = _driver(p)
	filters = {"driver": driver.name, "docstatus": ["<", 2]}
	if not _manager():
		filters["custom_salesperson"] = frappe.session.user
	if active:
		filters["status"] = "Open"
	if p.get("sessionid"):
		filters["name"] = p.sessionid
	else:
		filters["status"] = "Open"
	names = frappe.get_all("Van Session", filters=filters, pluck="name", limit=2)
	if len(names) > 1:
		frappe.throw("More than one matching Van Session. Send sessionid.")
	if not names and (active or p.get("sessionid")):
		frappe.throw("An assigned open Van Session is required.")
	session = None
	if names:
		if lock:
			frappe.db.sql("select name from `tabVan Session` where name=%s for update", names[0])
		session = frappe.get_doc("Van Session", names[0])
		session.check_permission("read")
		if active and (session.status != "Open" or session.docstatus == 2):
			frappe.throw("Van Session is not open.")
		van = frappe.get_doc("Van Fleet", session.van)
	else:
		vans = frappe.get_all("Van Fleet", filters={"default_driver": driver.name, "vehicle_status": "Active"}, pluck="name", limit=2)
		if len(vans) != 1:
			frappe.throw("Assign exactly one active Van Fleet to this driver, or assign a Van Session.")
		van = frappe.get_doc("Van Fleet", vans[0])
	van.check_permission("read")
	if not _manager() and (not session or session.status != "Open") and van.default_driver != driver.name:
		frappe.throw("Van is no longer assigned to this driver.", frappe.PermissionError)
	if van.vehicle_status != "Active":
		frappe.throw("Van is not active.")
	if p.get("vanid") and p.vanid != van.name:
		frappe.throw("Van does not match the driver's assignment.", frappe.PermissionError)
	warehouse = session.van_warehouse if session else van.van_warehouse
	if warehouse != van.van_warehouse:
		frappe.throw("Session warehouse does not match the van.")
	company = frappe.db.get_value("Warehouse", warehouse, "company")
	if not company:
		frappe.throw("Van warehouse must belong to a company.")
	if p.get("organizationid") and p.organizationid != company:
		frappe.throw("Company does not match the van warehouse.", frappe.PermissionError)
	if p.get("warehouse") and p.warehouse != warehouse:
		frappe.throw("Warehouse does not match the assigned van.", frappe.PermissionError)
	frappe.get_doc("Warehouse", warehouse).check_permission("read")
	return frappe._dict(driver=driver, session=session, van=van, warehouse=warehouse, company=company,
		currency=frappe.get_cached_value("Company", company, "default_currency"))


def _amount(value, label, *, zero=False):
	try:
		n = Decimal(str(value))
	except (InvalidOperation, TypeError, ValueError):
		frappe.throw(f"{label} must be a valid number.")
	if not n.is_finite() or n < 0 or (not zero and n == 0):
		frappe.throw(f"{label} must be {'non-negative' if zero else 'greater than zero'}.")
	return float(n)


def _rows(value, label, *, empty=False):
	if not isinstance(value, list) or (not value and not empty) or not all(isinstance(r, dict) for r in value):
		frappe.throw(f"{label} must be {'an' if empty else 'a non-empty'} array of objects.")
	if len(value) > 1000:
		frappe.throw(f"{label} cannot exceed 1000 rows.")
	return [frappe._dict(r) for r in value]


def _post(operation, p, handler):
	_require()
	requestid = p.get("requestid")
	if not isinstance(requestid, str) or not requestid.strip() or len(requestid) > 140:
		frappe.throw("requestid is required (maximum 140 characters). Reuse it on retries.")
	encoded = json.dumps(p, sort_keys=True, separators=(",", ":"), default=str)
	digest = hashlib.sha256(encoded.encode()).hexdigest()
	key = hashlib.sha256((frappe.session.user + "\0" + requestid).encode()).hexdigest()
	savepoint = "van_api_post"
	frappe.db.savepoint(savepoint)
	try:
		# A unique primary key plus an InnoDB row lock serializes simultaneous retries.
		frappe.db.sql("""insert into `tabVan API Request`
			(name, creation, modified, owner, modified_by, docstatus, request_id, operation, payload_hash, request_payload)
			values (%s,%s,%s,%s,%s,0,%s,%s,%s,%s)
			on duplicate key update name=name""",
			(key, now_datetime(), now_datetime(), frappe.session.user, frappe.session.user, requestid, operation, digest, encoded))
		stored = frappe.db.sql("select operation,payload_hash,response from `tabVan API Request` where name=%s for update", key, as_dict=True)[0]
		if stored.operation != operation or stored.payload_hash != digest:
			frappe.throw("requestid was already used with different data. Use a new requestid for a new action.")
		if stored.response:
			return {**frappe.parse_json(stored.response), "duplicate": True}
		result = handler()
		frappe.db.set_value("Van API Request", key, "response", frappe.as_json(result))
		return result
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise


def _session_data(ctx):
	s = ctx.session
	if not s:
		return None
	return dict(sessionid=s.name, driverid=s.driver, vanid=s.van, organizationid=ctx.company,
		warehouse=s.van_warehouse, session_date=s.session_date, session_status=s.status,
		activity_status=s.get("custom_activity_status") or "Active", open_time=s.open_time,
		close_time=s.close_time, opening_balance=s.opening_cash, closing_cash=s.closing_cash)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def driver_login(userid=None, password=None):
	from frappe.auth import LoginManager
	manager = getattr(frappe.local, "login_manager", None) or LoginManager()
	frappe.form_dict.update(usr=userid, pwd=password)
	try:
		if manager.login() is False:
			return dict(status="AuthenticationRequired", detail="Complete ERP password reset or two-factor authentication.")
		try:
			ctx = _context(frappe._dict())
		except Exception:
			manager.logout()
			raise
	finally:
		frappe.form_dict.pop("pwd", None)
	return dict(status="Success", driverid=ctx.driver.name, vanid=ctx.van.name,
		organizationid=ctx.company, sessionid=ctx.session.name if ctx.session else None)


@frappe.whitelist(methods=["GET", "POST"])
def get_active_session(data=None, **kwargs):
	ctx = _context(_payload(data, **kwargs))
	return dict(status="Success", session=_session_data(ctx))


@frappe.whitelist(methods=["POST"])
def start_session(data=None, **kwargs):
	p = _payload(data, **kwargs)
	def handler():
		driver = _driver(p)
		# Serialize starts for a driver, then for the van, before checking open sessions.
		frappe.db.sql("select name from `tabDriver` where name=%s for update", driver.name)
		if not p.get("sessionid"):
			filters = {"driver": driver.name, "status": "Draft", "docstatus": 0}
			if not _manager():
				filters["custom_salesperson"] = frappe.session.user
			if p.get("session_date"):
				filters["session_date"] = getdate(p.session_date)
			names = frappe.get_all("Van Session", filters=filters, pluck="name", limit=2)
			if len(names) == 1:
				p.sessionid = names[0]
			elif len(names) > 1:
				frappe.throw("Multiple assigned draft sessions. Send sessionid.")
		ctx = _context(p)
		frappe.db.sql("select name from `tabVan Fleet` where name=%s for update", ctx.van.name)
		if ctx.session and ctx.session.status == "Open":
			frappe.throw(f"Driver already has open session {ctx.session.name}.")
		if ctx.session:
			doc = ctx.session
			if doc.status != "Draft" or doc.docstatus != 0:
				frappe.throw("Only an assigned draft session can be started.")
		else:
			if not _manager():
				frappe.throw("A Van Sales Manager must assign a draft session first.", frappe.PermissionError)
			doc = frappe.new_doc("Van Session")
			doc.update(dict(driver=driver.name, van=ctx.van.name, van_warehouse=ctx.warehouse,
				session_date=getdate(p.get("session_date") or nowdate()), custom_salesperson=driver.get("custom_van_user")))
		if p.get("session_date") and getdate(p.session_date) != getdate(doc.session_date):
			frappe.throw("Business date must match the assigned session.")
		doc.status = "Open"
		doc.open_time = now_datetime()
		doc.opening_cash = _amount(p.get("opening_balance", 0), "Opening balance", zero=True)
		if p.get("opening_km") is not None:
			doc.opening_km = _amount(p.opening_km, "Opening KM", zero=True)
		doc.custom_app_open_time = get_datetime(p.timing) if p.get("timing") else now_datetime()
		doc.custom_activity_status = "Active"
		doc.save()
		doc.submit()
		return dict(status="Success", sessionid=doc.name, session_status=doc.status)
	return _post("start_session", p, handler)


@frappe.whitelist(methods=["POST"])
def update_session_status(data=None, **kwargs):
	p = _payload(data, **kwargs)
	def handler():
		ctx = _context(p, active=True, lock=True)
		if p.get("action") not in {"break", "resume"}:
			frappe.throw("action must be break or resume.")
		s = ctx.session
		s.custom_activity_status = "Break" if p.action == "break" else "Active"
		s.custom_activity_time = get_datetime(p.timing) if p.get("timing") else now_datetime()
		s.save()
		return dict(status="Success", sessionid=s.name, activity_status=s.custom_activity_status)
	return _post("update_session_status", p, handler)


@frappe.whitelist(methods=["POST"])
def end_session(data=None, **kwargs):
	p = _payload(data, **kwargs)
	def handler():
		ctx = _context(p, active=True, lock=True)
		s = ctx.session
		for dt in ("Sales Invoice", "Payment Entry", "Stock Entry", "Material Request"):
			if frappe.db.exists(dt, {"custom_van_session": s.name, "docstatus": 0}):
				frappe.throw(f"Finish or remove draft {dt} records before closing this session.")
		if frappe.db.exists("Van Expense", {"van_session": s.name, "docstatus": 0}):
			frappe.throw("Finish or remove draft expenses before closing this session.")
		collections = _rows(p.get("collection_details", []), "collection_details", empty=True)
		for row in collections:
			_mode_account(ctx, row.get("mode_of_payment"))
			_amount(row.get("amount"), "Collection amount", zero=True)
		s.closing_cash = _amount(p.get("closing_cash"), "Closing cash", zero=True)
		if p.get("closing_km") is not None:
			s.closing_km = _amount(p.closing_km, "Closing KM", zero=True)
		s.status = "Closed"
		s.close_time = now_datetime()
		s.custom_app_close_time = get_datetime(p.timing) if p.get("timing") else now_datetime()
		s.custom_collection_details = frappe.as_json(collections)
		if p.get("remarks") is not None:
			s.remarks = p.remarks
		s.save()
		return dict(status="Success", sessionid=s.name, session_status="Closed")
	return _post("end_session", p, handler)


def _customer(ctx, name):
	doc = frappe.get_doc("Customer", name)
	doc.check_permission("read")
	if not doc.get("custom_is_van_customer") or doc.get("custom_van_driver") != ctx.driver.name or doc.disabled:
		frappe.throw("Customer is not assigned to this driver.", frappe.PermissionError)
	return doc


def _customers(ctx):
	return frappe.get_list("Customer", filters={"custom_is_van_customer": 1,
		"custom_van_driver": ctx.driver.name, "disabled": 0},
		fields=["name", "customer_name", "customer_group", "territory", "mobile_no", "email_id", "tax_id", "modified"], limit_page_length=0)


@frappe.whitelist(methods=["POST"])
def upsert_customer(data=None, **kwargs):
	p = _payload(data, **kwargs)
	def handler():
		ctx = _context(p)
		external = p.get("external_customer_id")
		if not external or not isinstance(external, str) or len(external) > 140:
			frappe.throw("external_customer_id is required (maximum 140 characters).")
		key = hashlib.sha256((ctx.driver.name + "\0" + external).encode()).hexdigest()
		name = frappe.db.get_value("Customer", {"custom_van_external_id": key}, "name")
		if name and p.get("customerid") and p.customerid != name:
			frappe.throw("customerid conflicts with external_customer_id.")
		name = p.get("customerid") or name
		if name:
			doc = _customer(ctx, name)
			if doc.get("custom_van_external_id") not in (None, "", key):
				frappe.throw("Customer already has a different app ID.")
		else:
			doc = frappe.new_doc("Customer")
			doc.custom_is_van_customer = 1
			doc.custom_van_driver = ctx.driver.name
			doc.customer_type = "Individual"
		for field in ("customer_name", "customer_group", "territory", "mobile_no", "email_id", "tax_id"):
			if field in p:
				doc.set(field, p[field])
		doc.custom_van_external_id = key
		doc.save()
		return dict(status="Success", action="Updated" if name else "Created", customerid=doc.name, driverid=ctx.driver.name)
	return _post("upsert_customer", p, handler)


def _settings(ctx):
	van = ctx.van
	price_list = van.get("custom_selling_price_list") or frappe.db.get_single_value("Selling Settings", "selling_price_list")
	cost_center = van.get("custom_cost_center") or frappe.get_cached_value("Company", ctx.company, "cost_center")
	if not price_list:
		frappe.throw("Configure the van's Selling Price List.")
	price = frappe.get_cached_doc("Price List", price_list)
	if not price.enabled or not price.selling or price.currency != ctx.currency:
		frappe.throw("Van requires an enabled selling price list in company currency.")
	if not cost_center or frappe.db.get_value("Cost Center", cost_center, "company") != ctx.company:
		frappe.throw("Configure a Cost Center in the van's company.")
	tax = van.get("custom_sales_taxes_and_charges") or frappe.db.get_value(
		"Sales Taxes and Charges Template", {"company": ctx.company, "disabled": 0, "is_default": 1}, "name")
	if tax:
		template = frappe.get_cached_doc("Sales Taxes and Charges Template", tax)
		if template.company != ctx.company or template.disabled:
			frappe.throw("Van tax template must be enabled and belong to the van company.")
	return frappe._dict(selling_price_list=price_list, cost_center=cost_center, taxes_and_charges=tax)


def _mode_account(ctx, mode):
	if not mode or not frappe.db.get_value("Mode of Payment", mode, "enabled"):
		frappe.throw("An enabled mode_of_payment is required.")
	account = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": ctx.company}, "default_account")
	if not account:
		frappe.throw(f"Configure the company account for Mode of Payment {mode}.")
	row = frappe.db.get_value("Account", account, ["company", "is_group", "disabled", "account_type", "account_currency"], as_dict=True)
	if not row or row.company != ctx.company or row.is_group or row.disabled or row.account_type not in {"Cash", "Bank"} or row.account_currency != ctx.currency:
		frappe.throw("Payment account must be an enabled Cash/Bank ledger in company currency.")
	return account


def _modes(ctx):
	rows = frappe.get_all("Mode of Payment Account", filters={"company": ctx.company}, fields=["parent", "default_account"], limit_page_length=0)
	result = []
	for row in rows:
		if not frappe.db.get_value("Mode of Payment", row.parent, "enabled"):
			continue
		account = frappe.db.get_value("Account", row.default_account, ["disabled", "is_group", "account_currency", "account_type"], as_dict=True)
		if account and not account.disabled and not account.is_group and account.account_currency == ctx.currency and account.account_type in {"Cash", "Bank"}:
			result.append(row.parent)
	return sorted(set(result))


@frappe.whitelist(methods=["GET", "POST"])
def get_van_master_data(data=None, **kwargs):
	from retail.api.pos_sync import _catalog_master_data, _company_bill_format
	from retail.pos_item_identity import with_item_identity
	p = _payload(data, **kwargs)
	ctx = _context(p)
	settings = _settings(ctx)
	stamp = now_datetime()  # Cursor precedes reads, so concurrent edits are resent next time.
	catalog = _catalog_master_data(ctx.warehouse, p.get("modified_after"))
	catalog["item_prices"] = [r for r in catalog["item_prices"] if r.price_list == settings.selling_price_list]
	customers = _customers(ctx)  # Full assigned-customer snapshot, including after reassignment.
	return with_item_identity(dict(status="Success", server_time=stamp, server_timezone=get_system_timezone(),
		organizationid=ctx.company, driverid=ctx.driver.name, vanid=ctx.van.name, warehouse=ctx.warehouse,
		currency=ctx.currency, sessionid=ctx.session.name if ctx.session else None, **settings,
		**catalog, customers=customers, modes_of_payment=[dict(name=m) for m in _modes(ctx)],
		bill_format=_company_bill_format(ctx.company)), ctx.warehouse, known_items=catalog["items"])


# Deliberately separate from the unchanged POS endpoint with the same short name.
get_pos_master_data = get_van_master_data


def _invoice(ctx, name, *, is_return=None, submitted=False):
	doc = frappe.get_doc("Sales Invoice", name)
	doc.check_permission("read")
	if not doc.get("custom_is_van_sale") or doc.company != ctx.company or doc.get("custom_driver") != ctx.driver.name:
		frappe.throw("Invoice is not assigned to this driver/company.", frappe.PermissionError)
	_customer(ctx, doc.customer)
	if is_return is not None and cint(doc.is_return) != int(is_return):
		frappe.throw("Wrong invoice type.")
	if submitted and doc.docstatus != 1:
		frappe.throw("A submitted invoice is required.")
	return doc


def _invoices(ctx, *, returns=False, customer=None, outstanding=False, session_only=True):
	filters = {"custom_is_van_sale": 1, "custom_driver": ctx.driver.name, "company": ctx.company, "is_return": int(returns), "docstatus": ["<", 2]}
	if session_only:
		filters["custom_van_session"] = ctx.session.name
	if customer:
		_customer(ctx, customer)
		filters["customer"] = customer
	if outstanding:
		filters["docstatus"] = 1
		filters["outstanding_amount"] = ["<" if returns else ">", 0]
	return frappe.get_list("Sales Invoice", filters=filters, fields=["name as invoiceid", "customer as customerid", "customer_name", "posting_date", "grand_total", "outstanding_amount", "docstatus", "currency"], order_by="posting_date desc, name desc", limit_page_length=0)


@frappe.whitelist(methods=["GET", "POST"])
def get_sales_invoice_data(data=None, **kwargs):
	p = _payload(data, **kwargs)
	ctx = _context(p, active=True)
	if p.get("invoiceid"):
		doc = _invoice(ctx, p.invoiceid, is_return=False)
		return dict(status="Success", invoice=doc.as_dict())
	return dict(status="Success", organizationid=ctx.company, currency=ctx.currency, warehouse=ctx.warehouse,
		**_settings(ctx), modes_of_payment=_modes(ctx), invoices=_invoices(ctx))


def _item_row(row, *, returning=False):
	item = frappe.get_cached_doc("Item", row.get("item_code"))
	item.check_permission("read")
	if item.disabled or not item.is_sales_item:
		frappe.throw("Only enabled sales items may be sold.")
	qty = row.get("qty")
	try:
		qty = float(qty)
	except (TypeError, ValueError):
		frappe.throw("Item qty must be a number.")
	if not math.isfinite(qty) or (qty >= 0 if returning else qty <= 0):
		frappe.throw("Return qty must be negative." if returning else "Sale qty must be positive.")
	result = {k: row[k] for k in ("item_code", "qty", "uom", "rate", "discount_percentage", "discount_amount", "serial_no", "batch_no", "barcode") if k in row}
	result["qty"] = qty
	for field in ("rate", "discount_percentage", "discount_amount"):
		if field in result:
			result[field] = _amount(result[field], field, zero=True)
	if cint(row.get("rate_includes_vat")) and "rate" in result:
		from retail.domains.transactions.vat import get_transaction_item_vat_rate
		vat = get_transaction_item_vat_rate(item.name, child_doctype="Sales Invoice Item", parent_doctype="Sales Invoice", throw=True)
		result["rate"] = result["rate"] / (1 + vat / 100)
	if "serial_no" in result or "batch_no" in result:
		result["use_serial_batch_fields"] = 1
	return result


@frappe.whitelist(methods=["POST"])
def post_sale(data=None, **kwargs):
	p = _payload(data, **kwargs)
	def handler():
		ctx = _context(p, active=True, lock=True)
		_customer(ctx, p.get("customerid"))
		settings = _settings(ctx)
		for field in ("selling_price_list", "taxes_and_charges"):
			if p.get(field) and p[field] != settings[field]:
				frappe.throw(f"{field} must match the van settings.")
		if p.get("invoiceid"):
			doc = _invoice(ctx, p.invoiceid, is_return=False)
			if doc.docstatus != 0 or doc.custom_van_session != ctx.session.name:
				frappe.throw("Only this session's draft invoices can be changed.")
		else:
			doc = frappe.new_doc("Sales Invoice")
		doc.update(dict(company=ctx.company, customer=p.customerid, currency=ctx.currency,
			custom_is_van_sale=1, custom_van_session=ctx.session.name, **settings,
			posting_date=getdate(p.get("posting_date") or ctx.session.session_date), update_stock=1))
		if p.get("posting_time"):
			doc.set_posting_time = 1
			doc.posting_time = p.posting_time
		doc.set("items", [_item_row(r) for r in _rows(p.get("items"), "items")])
		_set_invoice_discount(doc, p)
		doc.set_missing_values()
		# ERP tax template handling remains native; do not accept client tax amounts.
		if settings.taxes_and_charges:
			from erpnext.controllers.accounts_controller import get_taxes_and_charges
			doc.set("taxes", get_taxes_and_charges("Sales Taxes and Charges Template", settings.taxes_and_charges))
		payments = _rows(p.get("payments", []), "payments", empty=True)
		action = _action(p)
		if action == "draft" and payments:
			frappe.throw("Payments can only be posted with a submitted sale.")
		doc.save()
		if action == "submit":
			doc.submit()
		paymentids = []
		for i, payment in enumerate(payments):
			doc.reload()
			amount = _amount(payment.get("amount"), "Payment amount")
			pe = _make_payment(ctx, doc.customer, payment.get("mode_of_payment"), amount,
				[frappe._dict(invoiceid=doc.name, allocated_amount=amount)], doc.posting_date, p.get("remarks"))
			paymentids.append(pe.name)
		doc.reload()
		return dict(status="Posted" if doc.docstatus == 1 else "Draft", invoiceid=doc.name,
			docstatus=doc.docstatus, grand_total=doc.grand_total, outstanding_amount=doc.outstanding_amount, paymentids=paymentids)
	return _post("post_sale", p, handler)


def _set_invoice_discount(doc, p):
	if not any(field in p for field in ("apply_discount_on", "additional_discount_percentage", "discount_amount")):
		return
	basis = p.get("apply_discount_on") or doc.get("apply_discount_on") or "Grand Total"
	if basis not in {"Net Total", "Grand Total"}:
		frappe.throw("apply_discount_on must be Net Total or Grand Total.")
	percent = _amount(p.get("additional_discount_percentage", 0), "Additional discount percentage", zero=True)
	amount = _amount(p.get("discount_amount", 0), "Invoice discount amount", zero=True)
	if percent > 100:
		frappe.throw("Additional discount percentage cannot exceed 100.")
	if percent and amount:
		frappe.throw("Send either additional_discount_percentage or discount_amount, not both.")
	doc.update(dict(apply_discount_on=basis, additional_discount_percentage=percent, discount_amount=amount))


def _action(p):
	action = p.get("action", "submit")
	if action not in {"draft", "submit"}:
		frappe.throw("action must be draft or submit.")
	return action


@frappe.whitelist(methods=["GET", "POST"])
def get_sales_return_data(data=None, **kwargs):
	p = _payload(data, **kwargs)
	ctx = _context(p, active=True)
	if p.get("returnid"):
		doc = _invoice(ctx, p.returnid, is_return=True)
		return dict(status="Success", return_invoice=doc.as_dict())
	if not p.get("invoiceid"):
		return dict(status="Success", returns=_invoices(ctx, returns=True))
	doc = _invoice(ctx, p.invoiceid, is_return=False, submitted=True)
	returned = _returned_quantities(doc.name)
	return dict(status="Success", invoiceid=doc.name, customerid=doc.customer, items=[dict(
		invoice_itemid=r.name, item_code=r.item_code, sold_qty=r.qty, returned_qty=returned.get(r.name, 0),
		returnable_qty=max(0, flt(r.qty) - returned.get(r.name, 0)), uom=r.uom, rate=r.rate) for r in doc.items])


def _returned_quantities(invoiceid):
	rows = frappe.db.sql("""select item.sales_invoice_item as rowid, -sum(item.qty) as qty
		from `tabSales Invoice Item` item inner join `tabSales Invoice` si on si.name=item.parent
		where si.return_against=%s and si.docstatus=1 group by item.sales_invoice_item""", invoiceid, as_dict=True)
	return {r.rowid: flt(r.qty) for r in rows}


@frappe.whitelist(methods=["POST"])
def post_sales_return(data=None, **kwargs):
	p = _payload(data, **kwargs)
	def handler():
		from erpnext.controllers.sales_and_purchase_return import make_return_doc
		ctx = _context(p, active=True, lock=True)
		frappe.db.sql("select name from `tabSales Invoice` where name=%s for update", p.get("invoiceid"))
		original = _invoice(ctx, p.get("invoiceid"), is_return=False, submitted=True)
		returned = _returned_quantities(original.name)
		target = frappe.new_doc("Sales Invoice")
		target.update(dict(custom_is_van_sale=1, custom_van_session=ctx.session.name))
		mapped = make_return_doc("Sales Invoice", original.name, target_doc=target)
		mapped.set("items", [])
		source = {r.name: r for r in original.items}
		seen = set()
		for row in _rows(p.get("items"), "items"):
			key = row.get("invoice_itemid")
			if key not in source or key in seen:
				frappe.throw("Each return row must identify a unique original invoice_itemid.")
			seen.add(key)
			old = source[key]
			if row.get("item_code") != old.item_code or row.get("uom", old.uom) != old.uom:
				frappe.throw("Return item and UOM must match the original invoice row.")
			fields = _item_row(row, returning=True)
			if abs(fields["qty"]) > flt(old.qty) - returned.get(key, 0) + 0.000001:
				frappe.throw("Return quantity exceeds the remaining invoiced quantity.")
			values = old.as_dict()
			for field in ("name", "parent", "parenttype", "parentfield", "idx", "creation", "modified", "docstatus", "serial_and_batch_bundle", "serial_no", "batch_no"):
				values.pop(field, None)
			values.update({k: fields[k] for k in ("qty", "serial_no", "batch_no", "use_serial_batch_fields") if k in fields})
			values["sales_invoice_item"] = key
			values["stock_qty"] = fields["qty"] * flt(old.conversion_factor or 1)
			mapped.append("items", values)
		mapped.update_outstanding_for_self = 1
		mapped.custom_van_session = ctx.session.name
		mapped.custom_van = ctx.van.name
		mapped.custom_driver = ctx.driver.name
		mapped.custom_van_warehouse = ctx.warehouse
		mapped.posting_date = getdate(p.get("posting_date") or ctx.session.session_date)
		mapped.set_posting_time = 0
		if p.get("returnid"):
			doc = _invoice(ctx, p.returnid, is_return=True)
			if doc.docstatus != 0 or doc.custom_van_session != ctx.session.name or doc.return_against != original.name:
				frappe.throw("Only this session's matching draft return can be updated.")
			for field in ("items", "taxes", "posting_date"):
				doc.set(field, mapped.get(field))
		else:
			doc = mapped
		doc.save()
		if _action(p) == "submit":
			doc.submit()
		return dict(status="Posted" if doc.docstatus == 1 else "Draft", returnid=doc.name, docstatus=doc.docstatus, grand_total=doc.grand_total)
	return _post("post_sales_return", p, handler)


@frappe.whitelist(methods=["GET", "POST"])
def get_credit_customers(data=None, **kwargs):
	p = _payload(data, **kwargs)
	ctx = _context(p)
	result = []
	for customer in _customers(ctx):
		invoices = _invoices(ctx, customer=customer.name, outstanding=True, session_only=False)
		credits = _invoices(ctx, customer=customer.name, returns=True, outstanding=True, session_only=False)
		balance = sum(flt(r.outstanding_amount) for r in invoices + credits)
		if balance:
			result.append(dict(customerid=customer.name, customer_name=customer.customer_name, currency=ctx.currency, outstanding_amount=balance))
	return dict(status="Success", customers=result)


@frappe.whitelist(methods=["GET", "POST"])
def get_customer_payment_data(data=None, **kwargs):
	p = _payload(data, **kwargs)
	ctx = _context(p, active=True)
	if not p.get("customerid"):
		payments = frappe.get_list("Payment Entry", filters={"custom_is_van_payment": 1, "custom_van_session": ctx.session.name,
			"company": ctx.company, "docstatus": ["<", 2]}, fields=["name as paymentid", "party as customerid", "paid_amount as amount", "mode_of_payment", "posting_date", "docstatus"], limit_page_length=0)
		return dict(status="Success", currency=ctx.currency, modes_of_payment=_modes(ctx), payments=payments)
	_customer(ctx, p.customerid)
	return dict(status="Success", customerid=p.customerid, currency=ctx.currency, modes_of_payment=_modes(ctx),
		invoices=_invoices(ctx, customer=p.customerid, outstanding=True, session_only=False),
		credit_notes=[dict(invoiceid=r.invoiceid, available_amount=-flt(r.outstanding_amount))
			for r in _invoices(ctx, customer=p.customerid, outstanding=True, returns=True, session_only=False)])


def _make_payment(ctx, customer, mode, amount, references, posting_date, remarks=None, *, refund=False):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	_customer(ctx, customer)
	account = _mode_account(ctx, mode)
	refs = _rows(references, "references")
	total = 0
	seen = set()
	first = None
	for row in sorted(refs, key=lambda r: r.get("invoiceid") or ""):
		if not row.get("invoiceid") or row.invoiceid in seen:
			frappe.throw("Each payment reference must identify a unique invoiceid.")
		seen.add(row.invoiceid)
		frappe.db.sql("select name from `tabSales Invoice` where name=%s for update", row.invoiceid)
		invoice = _invoice(ctx, row.invoiceid, is_return=refund, submitted=True)
		if invoice.customer != customer or invoice.currency != ctx.currency:
			frappe.throw("Payment invoices must belong to the same customer and company currency.")
		allocation = _amount(row.get("allocated_amount"), "Allocated amount")
		outstanding = -flt(invoice.outstanding_amount) if refund else flt(invoice.outstanding_amount)
		if allocation > outstanding + 0.000001:
			frappe.throw("Allocated payment exceeds current invoice outstanding.")
		row.allocated_amount = -allocation if refund else allocation
		total += allocation
		first = first or invoice
	if abs(total - amount) > 0.000001:
		frappe.throw("Payment amount must equal the sum of invoice allocations.")
	if not frappe.has_permission("Account", "read") and not frappe.has_permission("Account", "select"):
		frappe.throw("Native payment setup requires Account Select permission for this login. Ask your ERP administrator to configure the required access.", frappe.PermissionError)
	# Native setup reads the configured bank balance. Drivers do not receive
	# general Account access or that balance in this API response.
	previous = frappe.flags.get("ignore_account_permission")
	try:
		frappe.flags.ignore_account_permission = True
		pe = get_payment_entry("Sales Invoice", first.name, party_amount=amount, bank_account=account, bank_amount=amount)
	finally:
		frappe.flags.ignore_account_permission = previous
	pe.update(dict(custom_is_van_payment=1, custom_van_session=ctx.session.name,
		mode_of_payment=mode, posting_date=getdate(posting_date or ctx.session.session_date),
		paid_amount=amount, received_amount=amount, reference_no=remarks or "Van collection",
		reference_date=getdate(posting_date or ctx.session.session_date)))
	pe.set("references", [dict(reference_doctype="Sales Invoice", reference_name=r.invoiceid, allocated_amount=r.allocated_amount) for r in refs])
	pe.save()
	pe.submit()
	return pe


@frappe.whitelist(methods=["POST"])
def post_customer_payment(data=None, **kwargs):
	p = _payload(data, **kwargs)
	def handler():
		ctx = _context(p, active=True, lock=True)
		amount = _amount(p.get("amount"), "Payment amount")
		kind = p.get("payment_type", "Receive")
		if kind not in {"Receive", "Pay"}:
			frappe.throw("payment_type must be Receive or Pay (return refund).")
		pe = _make_payment(ctx, p.get("customerid"), p.get("mode_of_payment"), amount,
			p.get("references"), p.get("posting_date"), p.get("remarks"), refund=kind == "Pay")
		return dict(status="Posted", paymentid=pe.name, docstatus=pe.docstatus, amount=amount)
	return _post("post_customer_payment", p, handler)


def _source_warehouse(ctx, requested=None):
	warehouse = ctx.van.get("custom_source_warehouse")
	if not warehouse:
		frappe.throw("Configure the van's Loading / Return Warehouse.")
	if requested and requested != warehouse:
		frappe.throw("Warehouse must match the van's configured Loading / Return Warehouse.", frappe.PermissionError)
	row = frappe.get_doc("Warehouse", warehouse)
	row.check_permission("read")
	if row.company != ctx.company or row.is_group or row.disabled or warehouse == ctx.warehouse:
		frappe.throw("Loading / Return Warehouse must be a separate enabled leaf warehouse in the same company.")
	return warehouse


@frappe.whitelist(methods=["GET", "POST"])
def get_load_stock(data=None, **kwargs):
	p = _payload(data, **kwargs)
	ctx = _context(p, active=True)
	requests = frappe.get_list("Material Request", filters={"custom_is_van_stock_request": 1,
		"custom_van_session": ctx.session.name, "company": ctx.company, "docstatus": 1,
		"material_request_type": "Material Transfer", "status": ["not in", ["Stopped", "Cancelled"]]}, pluck="name", limit_page_length=0)
	loads = []
	for name in requests:
		doc = frappe.get_doc("Material Request", name)
		items = [dict(request_itemid=r.name, item_code=r.item_code, qty=max(0, flt(r.qty) - flt(r.ordered_qty) / flt(r.conversion_factor or 1)), uom=r.uom) for r in doc.items if flt(r.stock_qty) > flt(r.ordered_qty)]
		if items:
			loads.append(dict(requestid=name, vanid=ctx.van.name, source_warehouse=_source_warehouse(ctx), target_warehouse=ctx.warehouse, items=items))
	return dict(status="Success", loads=loads)


@frappe.whitelist(methods=["POST"])
def confirm_load(data=None, **kwargs):
	p = _payload(data, **kwargs)
	def handler():
		from erpnext.stock.doctype.material_request.material_request import make_stock_entry
		ctx = _context(p, active=True, lock=True)
		name = p.get("load_requestid")
		if not name:
			frappe.throw("load_requestid is required.")
		frappe.db.sql("select name from `tabMaterial Request` where name=%s for update", name)
		request = frappe.get_doc("Material Request", name)
		request.check_permission("read")
		if not request.get("custom_is_van_stock_request") or request.custom_van_session != ctx.session.name or request.company != ctx.company or request.docstatus != 1 or request.material_request_type != "Material Transfer" or request.status in {"Stopped", "Cancelled"}:
			frappe.throw("A submitted load request assigned to this session is required.", frappe.PermissionError)
		target = frappe.new_doc("Stock Entry")
		target.update(dict(custom_is_van_stock_entry=1, custom_van_session=ctx.session.name))
		doc = make_stock_entry(request.name, target_doc=target)
		if not doc.items:
			frappe.throw("This load request has already been transferred.")
		source = _source_warehouse(ctx)
		doc.update(dict(custom_is_van_stock_entry=1, custom_van_session=ctx.session.name,
			custom_van_stock_entry_type=request.custom_van_request_type or "Loading",
			company=ctx.company, posting_date=ctx.session.session_date))
		for row in doc.items:
			row.s_warehouse = source
			row.t_warehouse = ctx.warehouse
		# Tracked loads require explicit selections by request row, never client quantities.
		tracking = {r.get("request_itemid"): r for r in _rows(p.get("items", []), "items", empty=True)}
		for row in doc.items:
			for field in ("serial_no", "batch_no"):
				if tracking.get(row.material_request_item, {}).get(field):
					row.set(field, tracking[row.material_request_item][field])
					row.use_serial_batch_fields = 1
		doc.save()
		doc.submit()
		return dict(status="Posted", stock_entry=doc.name, docstatus=doc.docstatus)
	return _post("confirm_load", p, handler)


@frappe.whitelist(methods=["POST"])
def unload_stock(data=None, **kwargs):
	p = _payload(data, **kwargs)
	def handler():
		ctx = _context(p, active=True, lock=True)
		target = _source_warehouse(ctx, p.get("target_warehouse"))
		doc = frappe.new_doc("Stock Entry")
		doc.update(dict(company=ctx.company, stock_entry_type="Material Transfer", purpose="Material Transfer",
			custom_is_van_stock_entry=1, custom_van_session=ctx.session.name,
			custom_van_stock_entry_type="Offloading", posting_date=getdate(p.get("posting_date") or ctx.session.session_date)))
		for row in _rows(p.get("items"), "items"):
			fields = _item_row(row)
			fields.pop("rate", None)
			fields.pop("discount_percentage", None)
			fields.pop("discount_amount", None)
			fields.update(s_warehouse=ctx.warehouse, t_warehouse=target)
			doc.append("items", fields)
		doc.save()
		doc.submit()
		return dict(status="Posted", stock_entry=doc.name, docstatus=doc.docstatus)
	return _post("unload_stock", p, handler)


@frappe.whitelist(methods=["GET", "POST"])
def get_expense_data(data=None, **kwargs):
	p = _payload(data, **kwargs)
	ctx = _context(p, active=True)
	types = frappe.get_list("Van Expense Type", filters={"company": ctx.company, "enabled": 1}, fields=["name as expense_type", "proof_required"], limit_page_length=0)
	expenses = frappe.get_list("Van Expense", filters={"van_session": ctx.session.name, "docstatus": ["<", 2]}, fields=["name as expenseid", "expense_type", "amount", "mode_of_payment", "proof_url", "remarks", "docstatus", "accounting_reference"], limit_page_length=0)
	return dict(status="Success", currency=ctx.currency, expense_types=types, expenses=expenses)


@frappe.whitelist(methods=["POST"])
def post_expense(data=None, **kwargs):
	p = _payload(data, **kwargs)
	def handler():
		ctx = _context(p, active=True, lock=True)
		doc = frappe.new_doc("Van Expense")
		doc.update({k: p.get(k) for k in ("expense_type", "amount", "mode_of_payment", "proof_url", "remarks")})
		doc.update(dict(van_session=ctx.session.name, company=ctx.company, posting_date=getdate(p.get("posting_date") or ctx.session.session_date)))
		doc.save()
		doc.submit()
		return dict(status="Posted", expenseid=doc.name, accounting_reference=doc.accounting_reference, docstatus=doc.docstatus)
	return _post("post_expense", p, handler)


# Short-name compatibility for the app's existing requests.
get_sales_invoices = get_sales_invoice_data
get_sales_returns = get_sales_return_data
get_customer_payments = get_customer_payment_data
get_expenses = get_expense_data
