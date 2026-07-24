from __future__ import annotations

from datetime import datetime

import frappe
from frappe.utils import add_days, flt, getdate, now, now_datetime, nowdate, nowtime, today


DEMO_PREFIX = "BUSINESS-DEMO"
DEMO_COMPANY = "CELESTA ERP Demo LLC"
DEMO_ABBR = "BSD"
DEMO_CUSTOMER = "Business Demo Customer"
DEMO_SUPPLIER = "Business Demo Supplier"
DEMO_BRANCH = "Business Demo Branch"
DEMO_POS_PROFILE = "Business Demo POS Profile"
DEMO_POS_COUNTER = f"{DEMO_BRANCH}-COUNTER-1"
DEMO_GROUP = "Business Demo"
DEMO_BRAND = "Business Demo"


def setup_demo(args=None):
	"""Run Retail demo seeding when ERPNext setup wizard demo data is selected."""
	args = args or {}
	if not args.get("setup_demo"):
		return

	frappe.enqueue(seed_full_demo_data, enqueue_after_commit=True, at_front=True)


def _first_existing(doctype, filters=None, fieldname="name", order_by=None):
	return frappe.db.get_value(doctype, filters or {}, fieldname, order_by=order_by)


def _insert_if_missing(doctype, name=None, values=None):
	values = frappe._dict(values or {})
	name = name or values.get("name")
	if name and frappe.db.exists(doctype, name):
		return frappe.get_doc(doctype, name)

	doc = frappe.new_doc(doctype)
	if name:
		doc.name = name
	doc.update(values)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc


def _submit_once(doc):
	if doc.docstatus == 0:
		doc.flags.ignore_permissions = True
		doc.submit()
	return doc


def _get_company():
	company = frappe.defaults.get_user_default("Company") or _first_existing("Company")
	if company:
		return company

	current_year = now_datetime().year
	from erpnext.setup.setup_wizard.setup_wizard import setup_complete

	setup_complete(
		{
			"currency": "AED",
			"full_name": "Demo Administrator",
			"company_name": DEMO_COMPANY,
			"timezone": "Asia/Dubai",
			"company_abbr": DEMO_ABBR,
			"industry": "Distribution",
			"country": "United Arab Emirates",
			"fy_start_date": f"{current_year}-01-01",
			"fy_end_date": f"{current_year}-12-31",
			"language": "english",
			"company_tagline": "Smart Solutions. Stronger Business.",
			"email": "admin@example.com",
			"password": "admin",
			"chart_of_accounts": "Standard",
		}
	)
	frappe.db.commit()
	return DEMO_COMPANY


def _company_abbr(company):
	return frappe.db.get_value("Company", company, "abbr")


def _default_currency(company):
	return frappe.db.get_value("Company", company, "default_currency") or "AED"


def _default_cost_center(company):
	return (
		frappe.db.get_value("Company", company, "cost_center")
		or frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
	)


def _default_warehouse(company):
	abbr = _company_abbr(company)
	return (
		frappe.db.get_value("Warehouse", {"company": company, "warehouse_name": "Stores", "is_group": 0}, "name")
		or frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name", order_by="lft asc")
		or _insert_if_missing(
			"Warehouse",
			f"Stores - {abbr}",
			{"warehouse_name": "Stores", "company": company, "is_group": 0},
		).name
	)


def _second_warehouse(company):
	abbr = _company_abbr(company)
	return (
		frappe.db.get_value("Warehouse", {"company": company, "warehouse_name": "Demo Display", "is_group": 0}, "name")
		or _insert_if_missing(
			"Warehouse",
			f"Demo Display - {abbr}",
			{"warehouse_name": "Demo Display", "company": company, "is_group": 0},
		).name
	)


def _account(company, account_type=None, root_type=None, contains=None):
	filters = {"company": company, "is_group": 0}
	if account_type:
		filters["account_type"] = account_type
	if root_type:
		filters["root_type"] = root_type
	if contains:
		filters["account_name"] = ["like", f"%{contains}%"]
	return frappe.db.get_value("Account", filters, "name", order_by="lft asc")


def _income_account(company):
	return _account(company, "Income Account") or _account(company, root_type="Income")


def _expense_account(company):
	return _account(company, "Expense Account") or _account(company, root_type="Expense")


def _cash_account(company):
	return _account(company, "Cash") or _account(company, root_type="Asset", contains="Cash")


def _bank_account(company):
	return _account(company, "Bank") or _cash_account(company)


def _receivable_account(company):
	return _account(company, "Receivable") or _account(company, root_type="Asset", contains="Debtors")


def _payable_account(company):
	return _account(company, "Payable") or _account(company, root_type="Liability", contains="Creditors")


def _stock_adjustment_account(company):
	return (
		_account(company, "Stock Adjustment")
		or _account(company, root_type="Expense", contains="Stock Adjustment")
		or _expense_account(company)
	)


def _ensure_mode_of_payment(mode, company, account):
	doc = _insert_if_missing("Mode of Payment", mode, {"mode_of_payment": mode, "type": "Cash" if mode == "Cash" else "Bank"})
	if account and not any(row.company == company for row in doc.accounts):
		doc.append("accounts", {"company": company, "default_account": account})
		doc.save(ignore_permissions=True)
	return doc.name


def _default_item_tax_template(company):
	abbr = _company_abbr(company)
	return (
		frappe.db.exists("Item Tax Template", f"UAE VAT 5% - {abbr}")
		or frappe.db.get_value("Item Tax Template", {"title": "UAE VAT 5%", "company": company}, "name")
		or frappe.db.get_value("Item Tax Template", {"company": company}, "name", order_by="modified desc")
	)


def _ensure_masters(company):
	currency = _default_currency(company)
	warehouse = _default_warehouse(company)
	display_warehouse = _second_warehouse(company)
	cost_center = _default_cost_center(company)
	item_tax_template = _default_item_tax_template(company)

	for doctype, name, values in (
		("Item Group", DEMO_GROUP, {"item_group_name": DEMO_GROUP, "parent_item_group": "All Item Groups", "is_group": 0}),
		("Brand", DEMO_BRAND, {"brand": DEMO_BRAND}),
		("Customer Group", DEMO_GROUP, {"customer_group_name": DEMO_GROUP, "parent_customer_group": "All Customer Groups", "is_group": 0}),
		("Supplier Group", DEMO_GROUP, {"supplier_group_name": DEMO_GROUP, "parent_supplier_group": "All Supplier Groups", "is_group": 0}),
		("Territory", DEMO_GROUP, {"territory_name": DEMO_GROUP, "parent_territory": "All Territories", "is_group": 0}),
	):
		_insert_if_missing(doctype, name, values)

	customer = _insert_if_missing(
		"Customer",
		DEMO_CUSTOMER,
		{
			"customer_name": DEMO_CUSTOMER,
			"customer_type": "Individual",
			"customer_group": DEMO_GROUP,
			"territory": DEMO_GROUP,
			"default_currency": currency,
		},
	).name
	supplier = _insert_if_missing(
		"Supplier",
		DEMO_SUPPLIER,
		{
			"supplier_name": DEMO_SUPPLIER,
			"supplier_group": DEMO_GROUP,
			"supplier_type": "Company",
			"country": frappe.db.get_value("Company", company, "country") or "United Arab Emirates",
			"default_currency": currency,
		},
	).name
	branch = _insert_if_missing("Branch", DEMO_BRANCH, {"branch": DEMO_BRANCH}).name
	counter = _insert_if_missing("Counter", "Counter 1", {"counter_name": "Counter 1"}).name

	_cash = _ensure_mode_of_payment("Cash", company, _cash_account(company))
	_card = _ensure_mode_of_payment("Card", company, _bank_account(company))

	return frappe._dict(
		{
			"company": company,
			"currency": currency,
			"warehouse": warehouse,
			"display_warehouse": display_warehouse,
			"cost_center": cost_center,
			"customer": customer,
			"supplier": supplier,
			"branch": branch,
			"counter": counter,
			"cash_mode": _cash,
			"card_mode": _card,
			"item_tax_template": item_tax_template,
		}
	)


def _ensure_item(code, item_name, barcode, rate, ctx):
	if frappe.db.exists("Item", code):
		return code
	doc = frappe.new_doc("Item")
	doc.item_code = code
	doc.item_name = item_name
	doc.item_group = DEMO_GROUP
	doc.brand = DEMO_BRAND
	doc.stock_uom = "Nos"
	doc.is_stock_item = 1
	doc.is_sales_item = 1
	doc.is_purchase_item = 1
	doc.valuation_rate = rate * 0.62
	doc.standard_rate = rate
	doc.last_purchase_rate = rate * 0.62
	if doc.meta.has_field("custom_barcode"):
		doc.custom_barcode = barcode
	if ctx.item_tax_template:
		for fieldname in ("custom_purchase_tax_template", "custom_tax"):
			if doc.meta.has_field(fieldname):
				doc.set(fieldname, ctx.item_tax_template)
	doc.append(
		"item_defaults",
		{
			"company": ctx.company,
			"default_warehouse": ctx.warehouse,
			"income_account": _income_account(ctx.company),
			"expense_account": _expense_account(ctx.company),
			"buying_cost_center": ctx.cost_center,
			"selling_cost_center": ctx.cost_center,
		},
	)
	doc.insert(ignore_permissions=True)
	doc.append("barcodes", {"barcode": barcode, "uom": "Nos"})
	doc.save(ignore_permissions=True)
	return doc.name


def _ensure_item_price(item_code, price_list, rate):
	filters = {"item_code": item_code, "price_list": price_list}
	if frappe.db.exists("Item Price", filters):
		return
	doc = frappe.new_doc("Item Price")
	doc.item_code = item_code
	doc.price_list = price_list
	doc.price_list_rate = rate
	doc.insert(ignore_permissions=True)


def _ensure_items(ctx):
	items = [
		("RD-WATER-500ML", "Demo Water 500ml", "6297000000011", 2.5),
		("RD-RICE-5KG", "Demo Rice 5kg", "6297000000028", 28.0),
		("RD-SNACK-MIX", "Demo Snack Mix", "6297000000035", 6.0),
	]
	for code, name, barcode, rate in items:
		_ensure_item(code, name, barcode, rate, ctx)
		_ensure_item_price(code, "Standard Selling", rate)
		_ensure_item_price(code, "Standard Buying", rate * 0.62)
	return [row[0] for row in items]


def _ensure_pos(ctx):
	if frappe.db.exists("POS Profile", DEMO_POS_PROFILE):
		pos_profile = frappe.get_doc("POS Profile", DEMO_POS_PROFILE)
	else:
		pos_profile = frappe.new_doc("POS Profile")
		pos_profile.name = DEMO_POS_PROFILE
		pos_profile.company = ctx.company
		pos_profile.customer = ctx.customer
		pos_profile.country = frappe.db.get_value("Company", ctx.company, "country")
		pos_profile.currency = ctx.currency
		pos_profile.warehouse = ctx.warehouse
		pos_profile.cost_center = ctx.cost_center
		pos_profile.selling_price_list = "Standard Selling"
		pos_profile.write_off_account = _stock_adjustment_account(ctx.company)
		pos_profile.write_off_cost_center = ctx.cost_center
		pos_profile.account_for_change_amount = _cash_account(ctx.company)
		pos_profile.append("payments", {"mode_of_payment": ctx.cash_mode, "default": 1})
		pos_profile.append("payments", {"mode_of_payment": ctx.card_mode})
		pos_profile.insert(ignore_permissions=True)

	if not frappe.db.exists("POS Branch Counter", DEMO_POS_COUNTER):
		counter = frappe.new_doc("POS Branch Counter")
		counter.company = ctx.company
		counter.branch = ctx.branch
		counter.warehouse = ctx.warehouse
		counter.cost_center = ctx.cost_center
		counter.counter_code = "COUNTER-1"
		counter.counter_name = "Counter 1"
		counter.terminal_id = "DEMO-POS-01"
		counter.pos_profile = pos_profile.name
		counter.default_customer = ctx.customer
		counter.cash_account = _cash_account(ctx.company)
		counter.card_account = _bank_account(ctx.company)
		counter.is_active = 1
		counter.allow_offline_sync = 1
		counter.insert(ignore_permissions=True)
	return pos_profile.name


def _submit_stock_entry(name, ctx, purpose, rows, stock_entry_type=None):
	if frappe.db.exists("Stock Entry", name) or frappe.db.exists(
		"Stock Entry",
		{
			"company": ctx.company,
			"purpose": purpose,
			"stock_entry_type": stock_entry_type or purpose,
			"remarks": "Retail full demo data",
			"docstatus": 1,
		},
	):
		return name
	if stock_entry_type and not frappe.db.exists("Stock Entry Type", stock_entry_type):
		_insert_if_missing("Stock Entry Type", stock_entry_type, {"purpose": purpose, "is_standard": 0})

	doc = frappe.new_doc("Stock Entry")
	doc.name = name
	doc.company = ctx.company
	doc.stock_entry_type = stock_entry_type or purpose
	doc.purpose = purpose
	doc.posting_date = today()
	doc.posting_time = nowtime()
	doc.set_posting_time = 1
	doc.expense_account = _stock_adjustment_account(ctx.company)
	doc.cost_center = ctx.cost_center
	doc.remarks = "Retail full demo data"
	for row in rows:
		doc.append("items", row)
	doc.insert(ignore_permissions=True)
	_submit_once(doc)
	return doc.name


def _ensure_stock(ctx, items):
	_submit_stock_entry(
		f"{DEMO_PREFIX}-OPENING-STOCK",
		ctx,
		"Material Receipt",
		[
			{"item_code": items[0], "t_warehouse": ctx.warehouse, "qty": 120, "basic_rate": 1.55, "cost_center": ctx.cost_center},
			{"item_code": items[1], "t_warehouse": ctx.warehouse, "qty": 35, "basic_rate": 17.36, "cost_center": ctx.cost_center},
			{"item_code": items[2], "t_warehouse": ctx.warehouse, "qty": 80, "basic_rate": 3.72, "cost_center": ctx.cost_center},
		],
	)
	_submit_stock_entry(
		f"{DEMO_PREFIX}-TRANSFER-STOCK",
		ctx,
		"Material Transfer",
		[
			{
				"item_code": items[2],
				"s_warehouse": ctx.warehouse,
				"t_warehouse": ctx.display_warehouse,
				"qty": 10,
				"basic_rate": 3.72,
				"cost_center": ctx.cost_center,
			}
		],
	)
	_submit_stock_entry(
		f"{DEMO_PREFIX}-DAMAGE-STOCK",
		ctx,
		"Material Issue",
		[
			{"item_code": items[0], "s_warehouse": ctx.warehouse, "qty": 2, "basic_rate": 1.55, "cost_center": ctx.cost_center}
		],
		stock_entry_type="Damage",
	)
	_seed_reorder_rows(items[0], ctx.warehouse, ctx.display_warehouse)


def _append_sales_item(doc, item_code, qty, rate, warehouse, cost_center):
	doc.append(
		"items",
		{"item_code": item_code, "qty": qty, "rate": rate, "warehouse": warehouse, "cost_center": cost_center},
	)


def _append_purchase_item(doc, item_code, qty, rate, warehouse, cost_center):
	doc.append(
		"items",
		{"item_code": item_code, "qty": qty, "rate": rate, "warehouse": warehouse, "cost_center": cost_center},
	)


def _ensure_sales_flow(ctx, items, pos_profile):
	if not frappe.db.exists("Sales Order", f"{DEMO_PREFIX}-SO-001") and not frappe.db.exists(
		"Sales Order", {"customer": ctx.customer, "company": ctx.company, "transaction_date": today(), "docstatus": 1}
	):
		so = frappe.new_doc("Sales Order")
		so.name = f"{DEMO_PREFIX}-SO-001"
		so.customer = ctx.customer
		so.company = ctx.company
		so.transaction_date = today()
		so.delivery_date = add_days(today(), 2)
		so.selling_price_list = "Standard Selling"
		so.set_warehouse = ctx.warehouse
		so.cost_center = ctx.cost_center
		_append_sales_item(so, items[0], 6, 2.5, ctx.warehouse, ctx.cost_center)
		_append_sales_item(so, items[2], 3, 6.0, ctx.warehouse, ctx.cost_center)
		so.insert(ignore_permissions=True)
		_submit_once(so)

	if not frappe.db.exists("Delivery Note", f"{DEMO_PREFIX}-DN-001") and not frappe.db.exists(
		"Delivery Note", {"customer": ctx.customer, "company": ctx.company, "posting_date": today(), "docstatus": 1}
	):
		dn = frappe.new_doc("Delivery Note")
		dn.name = f"{DEMO_PREFIX}-DN-001"
		dn.customer = ctx.customer
		dn.company = ctx.company
		dn.posting_date = today()
		dn.set_posting_time = 1
		dn.posting_time = nowtime()
		dn.selling_price_list = "Standard Selling"
		dn.set_warehouse = ctx.warehouse
		dn.cost_center = ctx.cost_center
		_append_sales_item(dn, items[2], 2, 6.0, ctx.warehouse, ctx.cost_center)
		dn.insert(ignore_permissions=True)
		_submit_once(dn)

	sales_invoice_name = frappe.db.get_value(
		"Sales Invoice",
		{
			"customer": ctx.customer,
			"company": ctx.company,
			"posting_date": today(),
			"is_return": 0,
			"base_grand_total": 81,
			"docstatus": 1,
		},
		"name",
	)
	if not frappe.db.exists("Sales Invoice", f"{DEMO_PREFIX}-SI-FULL-001") and not sales_invoice_name:
		si = frappe.new_doc("Sales Invoice")
		si.name = f"{DEMO_PREFIX}-SI-FULL-001"
		si.customer = ctx.customer
		si.company = ctx.company
		si.posting_date = today()
		si.due_date = today()
		si.set_posting_time = 1
		si.posting_time = nowtime()
		si.is_pos = 1
		si.pos_profile = pos_profile
		si.selling_price_list = "Standard Selling"
		si.set_warehouse = ctx.warehouse
		si.cost_center = ctx.cost_center
		if si.meta.has_field("custom_counter"):
			si.custom_counter = ctx.counter
		_append_sales_item(si, items[0], 10, 2.5, ctx.warehouse, ctx.cost_center)
		_append_sales_item(si, items[1], 2, 28.0, ctx.warehouse, ctx.cost_center)
		si.append("payments", {"mode_of_payment": ctx.cash_mode, "amount": 81})
		si.insert(ignore_permissions=True)
		_submit_once(si)
		sales_invoice_name = si.name

	if (
		not frappe.db.exists("Sales Invoice", f"{DEMO_PREFIX}-SI-RETURN-001")
		and sales_invoice_name
		and not frappe.db.exists(
			"Sales Invoice",
			{
				"customer": ctx.customer,
				"company": ctx.company,
				"posting_date": today(),
				"is_return": 1,
				"return_against": sales_invoice_name,
				"docstatus": 1,
			},
		)
	):
		from erpnext.controllers.sales_and_purchase_return import make_return_doc

		ret = make_return_doc("Sales Invoice", sales_invoice_name)
		ret.name = f"{DEMO_PREFIX}-SI-RETURN-001"
		ret.posting_date = today()
		ret.posting_time = nowtime()
		ret.set_posting_time = 1
		if ret.meta.has_field("custom_counter"):
			ret.custom_counter = ctx.counter
		ret.set("payments", [])
		ret.paid_amount = 0
		ret.base_paid_amount = 0
		if ret.items:
			if len(ret.items) > 1:
				ret.set("items", [ret.items[0]])
			ret.items[0].qty = -1
			ret.items[0].stock_qty = -abs(ret.items[0].conversion_factor or 1)
		ret.insert(ignore_permissions=True)
		_submit_once(ret)


def _ensure_purchase_flow(ctx, items):
	if not frappe.db.exists("Purchase Order", f"{DEMO_PREFIX}-PO-001") and not frappe.db.exists(
		"Purchase Order", {"supplier": ctx.supplier, "company": ctx.company, "transaction_date": today(), "docstatus": 1}
	):
		po = frappe.new_doc("Purchase Order")
		po.name = f"{DEMO_PREFIX}-PO-001"
		po.supplier = ctx.supplier
		po.company = ctx.company
		po.transaction_date = today()
		po.schedule_date = add_days(today(), 3)
		po.buying_price_list = "Standard Buying"
		po.set_warehouse = ctx.warehouse
		po.cost_center = ctx.cost_center
		_append_purchase_item(po, items[0], 24, 1.55, ctx.warehouse, ctx.cost_center)
		_append_purchase_item(po, items[1], 6, 17.36, ctx.warehouse, ctx.cost_center)
		po.insert(ignore_permissions=True)
		_submit_once(po)

	if not frappe.db.exists("Purchase Receipt", f"{DEMO_PREFIX}-PR-001") and not frappe.db.exists(
		"Purchase Receipt", {"supplier": ctx.supplier, "company": ctx.company, "posting_date": today(), "docstatus": 1}
	):
		pr = frappe.new_doc("Purchase Receipt")
		pr.name = f"{DEMO_PREFIX}-PR-001"
		pr.supplier = ctx.supplier
		pr.company = ctx.company
		pr.posting_date = today()
		pr.posting_time = nowtime()
		pr.set_posting_time = 1
		pr.buying_price_list = "Standard Buying"
		pr.set_warehouse = ctx.warehouse
		pr.cost_center = ctx.cost_center
		_append_purchase_item(pr, items[0], 12, 1.55, ctx.warehouse, ctx.cost_center)
		pr.insert(ignore_permissions=True)
		_submit_once(pr)

	if not frappe.db.exists("Purchase Invoice", f"{DEMO_PREFIX}-PI-001") and not frappe.db.exists(
		"Purchase Invoice", {"supplier": ctx.supplier, "company": ctx.company, "posting_date": today(), "docstatus": 1}
	):
		pi = frappe.new_doc("Purchase Invoice")
		pi.name = f"{DEMO_PREFIX}-PI-001"
		pi.supplier = ctx.supplier
		pi.company = ctx.company
		pi.posting_date = today()
		pi.due_date = today()
		pi.buying_price_list = "Standard Buying"
		pi.set_warehouse = ctx.warehouse
		pi.cost_center = ctx.cost_center
		pi.credit_to = _payable_account(ctx.company)
		_append_purchase_item(pi, items[2], 20, 3.72, ctx.warehouse, ctx.cost_center)
		pi.insert(ignore_permissions=True)
		_submit_once(pi)


@frappe.whitelist()
def seed_full_demo_data():
	"""Create a reusable retail demo dataset for fresh or lightly configured sites."""
	company = _get_company()
	ctx = _ensure_masters(company)
	items = _ensure_items(ctx)
	pos_profile = _ensure_pos(ctx)
	_ensure_stock(ctx, items)
	_ensure_purchase_flow(ctx, items)
	_ensure_sales_flow(ctx, items, pos_profile)
	frappe.clear_cache()
	frappe.db.commit()
	return {
		"company": ctx.company,
		"customer": ctx.customer,
		"supplier": ctx.supplier,
		"items": items,
		"warehouse": ctx.warehouse,
		"pos_profile": pos_profile,
		"pos_counter": DEMO_POS_COUNTER,
	}


def _valid_row_data(doctype, source_doc):
	data = {}
	for column in frappe.get_meta(doctype).get_valid_columns():
		data[column] = source_doc.get(column)
	return data


def _clone_row(doctype, template_name, new_name, updates):
	if frappe.db.exists(doctype, new_name):
		frappe.delete_doc(doctype, new_name, force=True, ignore_permissions=True)

	template = frappe.get_doc(doctype, template_name)
	data = _valid_row_data(doctype, template)
	data.update(updates)
	data["doctype"] = doctype
	data["name"] = new_name
	doc = frappe.get_doc(data)
	doc.db_insert()
	return doc.name


def _set_if_column(data, doctype, fieldname, value):
	if fieldname in frappe.get_meta(doctype).get_valid_columns():
		data[fieldname] = value


def _invoice_updates(name, template, amount, is_return=False, counter="Counter 1"):
	posting_date = today()
	grand_total = -abs(amount) if is_return else abs(amount)
	updates = {
		"name": name,
		"docstatus": 1,
		"posting_date": posting_date,
		"due_date": posting_date,
		"set_posting_time": 1,
		"posting_time": nowtime(),
		"is_return": 1 if is_return else 0,
		"custom_counter": counter,
		"base_grand_total": grand_total,
		"grand_total": grand_total,
		"rounded_total": grand_total,
		"base_rounded_total": grand_total,
		"outstanding_amount": 0,
		"paid_amount": abs(amount) if not is_return else 0,
		"base_paid_amount": abs(amount) if not is_return else 0,
		"remarks": "Retail dashboard demo data",
		"owner": "Administrator",
		"modified_by": "Administrator",
		"creation": now(),
		"modified": now(),
	}
	for field in ("net_total", "base_net_total", "total", "base_total"):
		_set_if_column(updates, "Sales Invoice", field, grand_total)
	return updates


def _item_updates(name, parent, template, amount, qty, is_return=False):
	signed_qty = -abs(qty) if is_return else abs(qty)
	signed_amount = -abs(amount) if is_return else abs(amount)
	updates = {
		"name": name,
		"parent": parent,
		"parenttype": "Sales Invoice",
		"parentfield": "items",
		"idx": 1,
		"docstatus": 1,
		"qty": signed_qty,
		"stock_qty": signed_qty,
		"amount": signed_amount,
		"base_amount": signed_amount,
		"net_amount": signed_amount,
		"base_net_amount": signed_amount,
		"rate": abs(amount) / abs(qty),
		"base_rate": abs(amount) / abs(qty),
		"net_rate": abs(amount) / abs(qty),
		"base_net_rate": abs(amount) / abs(qty),
		"incoming_rate": template.incoming_rate or 0,
		"owner": "Administrator",
		"modified_by": "Administrator",
		"creation": now(),
		"modified": now(),
	}
	return updates


def _payment_updates(name, parent, template, amount):
	return {
		"name": name,
		"parent": parent,
		"parenttype": "Sales Invoice",
		"parentfield": "payments",
		"idx": 1,
		"docstatus": 1,
		"mode_of_payment": template.mode_of_payment or "Cash",
		"amount": abs(amount),
		"base_amount": abs(amount),
		"account": template.account,
		"type": template.type,
		"default": template.default,
		"owner": "Administrator",
		"modified_by": "Administrator",
		"creation": now(),
		"modified": now(),
	}


def _seed_reorder_rows(item_code, low_stock_warehouse, out_stock_warehouse):
	for row_name in (f"{DEMO_PREFIX}-REORDER-LOW", f"{DEMO_PREFIX}-REORDER-OUT"):
		if frappe.db.exists("Item Reorder", row_name):
			frappe.db.delete("Item Reorder", {"name": row_name})

	rows = [
		{
			"doctype": "Item Reorder",
			"name": f"{DEMO_PREFIX}-REORDER-LOW",
			"parent": item_code,
			"parenttype": "Item",
			"parentfield": "reorder_levels",
			"idx": 98,
			"warehouse": low_stock_warehouse,
			"warehouse_reorder_level": 600,
			"warehouse_reorder_qty": 50,
		},
		{
			"doctype": "Item Reorder",
			"name": f"{DEMO_PREFIX}-REORDER-OUT",
			"parent": item_code,
			"parenttype": "Item",
			"parentfield": "reorder_levels",
			"idx": 99,
			"warehouse": out_stock_warehouse,
			"warehouse_reorder_level": 5,
			"warehouse_reorder_qty": 5,
		},
	]
	for row in rows:
		frappe.get_doc(row).db_insert()


@frappe.whitelist()
def seed_dashboard_demo_data():
	"""Seed tiny demo records used only to prove dashboard cards/charts render."""
	template_invoice_name = frappe.db.get_value(
		"Sales Invoice", {"docstatus": 1, "is_return": 0}, "name", order_by="posting_date desc, creation desc"
	)
	if not template_invoice_name:
		frappe.throw("Need at least one submitted Sales Invoice to clone demo dashboard rows.")

	template_invoice = frappe.get_doc("Sales Invoice", template_invoice_name)
	template_item = template_invoice.items[0]
	template_payment = template_invoice.payments[0] if template_invoice.payments else frappe._dict({})
	date_key = datetime.now().strftime("%Y%m%d")

	sale_name = f"{DEMO_PREFIX}-SI-{date_key}-001"
	return_name = f"{DEMO_PREFIX}-SI-{date_key}-RET-001"

	for invoice_name in (sale_name, return_name):
		frappe.db.delete("Sales Invoice Payment", {"parent": invoice_name})
		frappe.db.delete("Sales Invoice Item", {"parent": invoice_name})
		frappe.db.delete("Sales Invoice", {"name": invoice_name})

	_clone_row("Sales Invoice", template_invoice_name, sale_name, _invoice_updates(sale_name, template_invoice, 125, False))
	_clone_row(
		"Sales Invoice Item",
		template_item.name,
		f"{sale_name}-ITEM-1",
		_item_updates(f"{sale_name}-ITEM-1", sale_name, template_item, 125, 5, False),
	)
	_clone_row(
		"Sales Invoice Payment",
		template_payment.name,
		f"{sale_name}-PAY-1",
		_payment_updates(f"{sale_name}-PAY-1", sale_name, template_payment, 125),
	)

	_clone_row("Sales Invoice", template_invoice_name, return_name, _invoice_updates(return_name, template_invoice, 25, True))
	_clone_row(
		"Sales Invoice Item",
		template_item.name,
		f"{return_name}-ITEM-1",
		_item_updates(f"{return_name}-ITEM-1", return_name, template_item, 25, 1, True),
	)

	template_sle_name = frappe.db.get_value("Stock Ledger Entry", {"item_code": template_item.item_code}, "name")
	if template_sle_name:
		sle_name = f"{DEMO_PREFIX}-SLE-{date_key}-DAMAGE-001"
		frappe.db.delete("Stock Ledger Entry", {"name": sle_name})
		sle_template = frappe.get_doc("Stock Ledger Entry", template_sle_name)
		_clone_row(
			"Stock Ledger Entry",
			template_sle_name,
			sle_name,
			{
				"name": sle_name,
				"docstatus": 1,
				"is_cancelled": 0,
				"posting_date": today(),
				"posting_time": nowtime(),
				"posting_datetime": now(),
				"voucher_type": "Damage",
				"voucher_no": f"{DEMO_PREFIX}-DAMAGE-{date_key}-001",
				"actual_qty": -1,
				"qty_after_transaction": flt(sle_template.qty_after_transaction) - 1,
				"stock_value_difference": -abs(flt(sle_template.valuation_rate) or 9),
				"valuation_rate": flt(sle_template.valuation_rate) or 9,
				"owner": "Administrator",
				"modified_by": "Administrator",
				"creation": now(),
				"modified": now(),
			},
		)

	warehouses = frappe.get_all("Warehouse", filters={"is_group": 0, "disabled": 0}, pluck="name", order_by="lft asc")
	if warehouses:
		_seed_reorder_rows(template_item.item_code, warehouses[0], warehouses[1] if len(warehouses) > 1 else warehouses[0])

	frappe.clear_cache()
	frappe.db.commit()
	return {
		"sale_invoice": sale_name,
		"return_invoice": return_name,
		"item": template_item.item_code,
		"counter": "Counter 1",
	}
