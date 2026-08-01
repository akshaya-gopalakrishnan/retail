from __future__ import annotations

from datetime import datetime, timedelta

import frappe
from frappe.utils import add_days, add_months, flt, getdate, now, now_datetime, nowdate, nowtime, today


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
DEMO_SIX_MONTH_PREFIX = "BUSINESS-DEMO-6M"


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


def _date_range(start_date, end_date):
	current = getdate(start_date)
	end = getdate(end_date)
	while current <= end:
		yield current
		current += timedelta(days=1)


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


def _ensure_demo_fiscal_years(start_date, end_date):
	for year in range(getdate(start_date).year, getdate(end_date).year + 1):
		name = str(year)
		if not frappe.db.exists("Fiscal Year", name):
			doc = frappe.new_doc("Fiscal Year")
			doc.year = name
			doc.year_start_date = f"{year}-01-01"
			doc.year_end_date = f"{year}-12-31"
			doc.insert(ignore_permissions=True)


def _ensure_demo_people(ctx):
	people = (
		("demo.cashier1@example.com", "Amina", "Cashier", "Female", "1111"),
		("demo.cashier2@example.com", "Ravi", "Cashier", "Male", "2222"),
		("demo.manager@example.com", "Maya", "Store Manager", "Female", "3333"),
	)
	employees = []
	for index, (email, first_name, designation, gender, pin) in enumerate(people, start=1):
		if not frappe.db.exists("User", email):
			user = frappe.new_doc("User")
			user.email = email
			user.first_name = first_name
			user.enabled = 1
			user.user_type = "System User"
			user.send_welcome_email = 0
			for role in ("Sales User", "Stock User", "Accounts User"):
				if frappe.db.exists("Role", role):
					user.append("roles", {"role": role})
			user.insert(ignore_permissions=True)

		employee_name = f"{DEMO_SIX_MONTH_PREFIX}-EMP-{index:03d}"
		existing_employee = (
			frappe.db.get_value("Employee", {"user_id": email}, "name")
			or (employee_name if frappe.db.exists("Employee", employee_name) else None)
		)
		if not existing_employee:
			employee = frappe.new_doc("Employee")
			employee.name = employee_name
			employee.first_name = first_name
			employee.employee_name = first_name
			employee.company = ctx.company
			employee.status = "Active"
			employee.gender = gender
			employee.date_of_birth = "1990-01-01"
			employee.date_of_joining = add_days(today(), -365)
			employee.branch = ctx.branch
			employee.user_id = email
			if employee.meta.has_field("pos_login_enabled"):
				employee.pos_login_enabled = 1
			if employee.meta.has_field("employee_number"):
				employee.employee_number = f"DEMO-CASHIER-{index:03d}"
			if employee.meta.has_field("pos_quick_pin_hash"):
				from retail.pos_login import make_quick_pin_hash

				pin_hash, salt = make_quick_pin_hash(pin)
				employee.pos_quick_pin_hash = pin_hash
				employee.pos_quick_pin_salt = salt
			employee.flags.ignore_mandatory = True
			employee.insert(ignore_permissions=True)
		else:
			employee = frappe.get_doc("Employee", existing_employee)

		if frappe.db.has_column("User", "pos_cashier_employee"):
			frappe.db.set_value("User", email, "pos_cashier_employee", employee.name, update_modified=False)
		employees.append(employee.name)
	return employees


def _delete_prefixed_documents(doctypes, prefix):
	for doctype in doctypes:
		if not frappe.db.table_exists(doctype):
			continue
		names = frappe.get_all(doctype, filters={"name": ["like", f"{prefix}%"]}, pluck="name", limit_page_length=0)
		if not names:
			continue
		for field in frappe.get_meta(doctype).fields:
			if field.fieldtype == "Table" and field.options and frappe.db.table_exists(field.options):
				frappe.db.delete(field.options, {"parent": ["in", names], "parenttype": doctype})
		frappe.db.delete(doctype, {"name": ["in", names]})


def _delete_six_month_demo_data():
	_delete_prefixed_documents(
		(
			"POS Cash Movement",
			"POS Branch Day Closing",
			"POS Counter Session",
			"POS Cashier Shift",
			"POS Closing Entry",
			"POS Opening Entry",
			"POS Invoice",
			"Sales Invoice",
			"Purchase Invoice",
			"Delivery Note",
			"Purchase Receipt",
			"Sales Order",
			"Purchase Order",
			"Stock Entry",
		),
		DEMO_SIX_MONTH_PREFIX,
	)
	if frappe.db.table_exists("Stock Ledger Entry"):
		frappe.db.delete("Stock Ledger Entry", {"name": ["like", f"{DEMO_SIX_MONTH_PREFIX}%"]})


def _clone_parent(doctype, template_name, new_name, updates):
	template = frappe.get_doc(doctype, template_name)
	data = _valid_row_data(doctype, template)
	data.update(updates)
	data["doctype"] = doctype
	data["name"] = new_name
	doc = frappe.get_doc(data)
	doc.db_insert()
	return doc


def _insert_direct_doc(doctype, name, values):
	data = {"doctype": doctype, "name": name}
	for column in frappe.get_meta(doctype).get_valid_columns():
		if column in values:
			data[column] = values[column]
	doc = frappe.get_doc(data)
	doc.db_insert()
	return doc


def _clone_child(doctype, template_row, name, parent, parenttype, parentfield, updates):
	data = _valid_row_data(doctype, template_row)
	data.update(updates)
	data.update({"doctype": doctype, "name": name, "parent": parent, "parenttype": parenttype, "parentfield": parentfield})
	frappe.get_doc(data).db_insert()


def _amount_fields(amount):
	return {
		"total": amount,
		"base_total": amount,
		"net_total": amount,
		"base_net_total": amount,
		"grand_total": amount,
		"base_grand_total": amount,
		"rounded_total": amount,
		"base_rounded_total": amount,
		"outstanding_amount": 0,
	}


def _invoice_item_values(item_code, qty, rate, idx, amount=None):
	amount = flt(amount if amount is not None else qty * rate, 2)
	item = frappe.get_doc("Item", item_code)
	values = {
		"idx": idx,
		"docstatus": 1,
		"item_code": item_code,
		"item_name": item.item_name,
		"description": item.description or item.item_name,
		"item_group": item.item_group,
		"qty": qty,
		"stock_qty": qty,
		"rate": abs(rate),
		"base_rate": abs(rate),
		"net_rate": abs(rate),
		"base_net_rate": abs(rate),
		"amount": amount,
		"base_amount": amount,
		"net_amount": amount,
		"base_net_amount": amount,
		"incoming_rate": abs(rate) * 0.62,
	}
	return values


def _clone_payment_rows(template_parent, target_parent, parenttype, payments):
	template_payment_name = frappe.db.get_value("Sales Invoice Payment", {"parent": template_parent, "parenttype": parenttype}, "name")
	if not template_payment_name:
		return
	template_payment = frappe.get_doc("Sales Invoice Payment", template_payment_name)
	for idx, (mode, amount) in enumerate(payments, start=1):
		_clone_child(
			"Sales Invoice Payment",
			template_payment,
			f"{target_parent}-PAY-{idx}",
			target_parent,
			parenttype,
			"payments",
			{
				"idx": idx,
				"docstatus": 1,
				"mode_of_payment": mode,
				"amount": amount,
				"base_amount": amount,
			},
		)


def _clone_stock_ledger(template_sle, name, posting_date, posting_time, voucher_type, voucher_no, item_code, qty, rate, warehouse, detail_no=None):
	amount = flt(qty * rate * 0.62, 2)
	_clone_parent(
		"Stock Ledger Entry",
		template_sle.name,
		name,
		{
			"docstatus": 1,
			"is_cancelled": 0,
			"posting_date": posting_date,
			"posting_time": posting_time,
			"posting_datetime": f"{posting_date} {posting_time}",
			"voucher_type": voucher_type,
			"voucher_no": voucher_no,
			"voucher_detail_no": detail_no,
			"item_code": item_code,
			"warehouse": warehouse,
			"actual_qty": qty,
			"qty_after_transaction": 1000 + qty,
			"incoming_rate": abs(rate) * 0.62,
			"valuation_rate": abs(rate) * 0.62,
			"stock_value_difference": amount,
			"company": frappe.db.get_value("Warehouse", warehouse, "company"),
			"creation": f"{posting_date} {posting_time}",
			"modified": f"{posting_date} {posting_time}",
			"owner": "Administrator",
			"modified_by": "Administrator",
		},
	)


def _seed_pos_day(ctx, items, employees, date_value, day_index, templates):
	date_key = date_value.strftime("%Y%m%d")
	cashier = employees[day_index % len(employees)]
	open_time = f"{date_value} 08:00:00"
	close_time = f"{date_value} 22:00:00"
	opening_amount = 350 + (day_index % 5) * 25
	shift_name = f"{DEMO_SIX_MONTH_PREFIX}-SHIFT-{date_key}"
	session_name = f"{DEMO_SIX_MONTH_PREFIX}-SESSION-{date_key}"
	opening_name = f"{DEMO_SIX_MONTH_PREFIX}-OPEN-{date_key}"
	closing_name = f"{DEMO_SIX_MONTH_PREFIX}-CLOSE-{date_key}"

	_clone_parent(
		"POS Cashier Shift",
		templates.shift.name,
		shift_name,
		{
			"branch": ctx.branch,
			"cashier_employee": cashier,
			"cashier_name": frappe.db.get_value("Employee", cashier, "employee_name"),
			"status": "Closed",
			"opening_time": open_time,
			"closing_time": close_time,
			"opening_amount": opening_amount,
			"current_counter": None,
			"current_counter_session": None,
			"device_api_user": "Administrator",
			"external_open_reference": f"{shift_name}-OPEN-REF",
			"external_close_reference": f"{shift_name}-CLOSE-REF",
		},
	)
	_clone_parent(
		"POS Counter Session",
		templates.session.name,
		session_name,
		{
			"cashier_shift": shift_name,
			"branch": ctx.branch,
			"counter": DEMO_POS_COUNTER,
			"counter_code": "COUNTER-1",
			"terminal_id": "DEMO-POS-01",
			"status": "Closed",
			"cashier_employee": cashier,
			"started_at": open_time,
			"ended_at": close_time,
			"pos_opening_entry": opening_name,
			"pos_closing_entry": closing_name,
			"opened_by_api_user": "Administrator",
			"opening_external_reference": f"{session_name}-OPEN-REF",
			"closing_external_reference": f"{session_name}-CLOSE-REF",
		},
	)

	if templates.opening:
		_clone_parent(
			"POS Opening Entry",
			templates.opening.name,
			opening_name,
			{
				"docstatus": 1,
				"status": "Closed",
				"company": ctx.company,
				"pos_profile": DEMO_POS_PROFILE,
				"user": "Administrator",
				"posting_date": date_value,
				"period_start_date": open_time,
				"pos_cashier_shift": shift_name,
				"pos_counter_session": session_name,
				"pos_branch_counter": DEMO_POS_COUNTER,
			},
		)
	if templates.closing:
		_clone_parent(
			"POS Closing Entry",
			templates.closing.name,
			closing_name,
			{
				"docstatus": 1,
				"company": ctx.company,
				"pos_profile": DEMO_POS_PROFILE,
				"user": "Administrator",
				"posting_date": date_value,
				"period_start_date": open_time,
				"period_end_date": close_time,
				"pos_opening_entry": opening_name,
				"pos_cashier_shift": shift_name,
				"pos_counter_session": session_name,
				"pos_branch_counter": DEMO_POS_COUNTER,
			},
		)

	invoice_total = 0
	cash_total = 0
	for invoice_idx in range(1, 5):
		hour = 9 + invoice_idx * 3 + (day_index % 2)
		posting_time = f"{hour:02d}:{(day_index * 7 + invoice_idx * 3) % 60:02d}:00"
		is_return = invoice_idx == 4 and day_index % 5 == 0
		name = f"{DEMO_SIX_MONTH_PREFIX}-POS-{date_key}-{invoice_idx:02d}"
		item_code = items[(day_index + invoice_idx) % len(items)]
		qty = (day_index % 3) + invoice_idx
		rate = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": "Standard Selling"}, "price_list_rate") or 10
		if invoice_idx == 3:
			rate = flt(rate * 0.92, 2)
		if is_return:
			qty = -1
		amount = flt(qty * rate, 2)
		payments = [(ctx.cash_mode, amount)] if invoice_idx % 2 else [(ctx.card_mode, amount)]
		if invoice_idx == 2:
			payments = [(ctx.cash_mode, flt(amount * 0.45, 2)), (ctx.card_mode, flt(amount * 0.55, 2))]

		updates = {
			"docstatus": 1,
			"posting_date": date_value,
			"due_date": date_value,
			"posting_time": posting_time,
			"set_posting_time": 1,
			"is_return": 1 if is_return else 0,
			"return_against": f"{DEMO_SIX_MONTH_PREFIX}-POS-{date_key}-01" if is_return else None,
			"customer": ctx.customer,
			"company": ctx.company,
			"update_stock": 1,
			"set_warehouse": ctx.warehouse,
			"cost_center": ctx.cost_center,
			"pos_profile": DEMO_POS_PROFILE,
			"external_pos_reference": f"{name}-EXT",
			"pos_bill_no": f"BILL-{date_key}-{invoice_idx:03d}",
			"pos_branch": ctx.branch,
			"pos_counter": DEMO_POS_COUNTER,
			"pos_terminal_id": "DEMO-POS-01",
			"pos_shift_no": shift_name,
			"pos_cashier": "Administrator",
			"pos_cashier_employee": cashier,
			"pos_cashier_shift": shift_name,
			"pos_counter_session": session_name,
			"pos_sync_source": "Offline POS",
			"pos_sync_datetime": f"{date_value} {posting_time}",
			"paid_amount": amount,
			"base_paid_amount": amount,
			"creation": f"{date_value} {posting_time}",
			"modified": f"{date_value} {posting_time}",
			"owner": "Administrator",
			"modified_by": "Administrator",
			"remarks": "Six month retail POS demo data",
		}
		updates.update(_amount_fields(amount))
		_clone_parent("POS Invoice", templates.pos_invoice.name, name, updates)
		item_row_name = f"{name}-ITEM-1"
		_clone_child(
			"POS Invoice Item",
			templates.pos_item,
			item_row_name,
			name,
			"POS Invoice",
			"items",
			_invoice_item_values(item_code, qty, rate, 1, amount),
		)
		_clone_payment_rows(templates.pos_invoice.name, name, "POS Invoice", payments)
		_clone_stock_ledger(templates.sle, f"{DEMO_SIX_MONTH_PREFIX}-SLE-POS-{date_key}-{invoice_idx:02d}", date_value, posting_time, "POS Invoice", name, item_code, -qty, rate, ctx.warehouse, item_row_name)
		invoice_total += amount
		cash_total += sum(amount for mode, amount in payments if mode == ctx.cash_mode)

	cash_in = 40 if day_index % 6 == 0 else 0
	cash_out = 25 if day_index % 4 == 0 else 0
	for movement_type, amount in (("Cash In", cash_in), ("Cash Out", cash_out)):
		if not amount:
			continue
		movement_name = f"{DEMO_SIX_MONTH_PREFIX}-CMOV-{date_key}-{movement_type.replace(' ', '').upper()}"
		movement_values = {
			"external_pos_reference": f"{movement_name}-EXT",
			"branch": ctx.branch,
			"counter": DEMO_POS_COUNTER,
			"counter_code": "COUNTER-1",
			"terminal_id": "DEMO-POS-01",
			"cashier_employee": cashier,
			"cashier_name": frappe.db.get_value("Employee", cashier, "employee_name"),
			"cashier_shift": shift_name,
			"counter_session": session_name,
			"movement_type": movement_type,
			"amount": amount,
			"posting_datetime": f"{date_value} 15:30:00",
			"description": "Demo till cash movement",
			"device_api_user": "Administrator",
			"creation": f"{date_value} 15:30:00",
			"modified": f"{date_value} 15:30:00",
			"owner": "Administrator",
			"modified_by": "Administrator",
		}
		if templates.cash_movement:
			_clone_parent("POS Cash Movement", templates.cash_movement.name, movement_name, movement_values)
		else:
			_insert_direct_doc("POS Cash Movement", movement_name, movement_values)

	expected_cash = flt(opening_amount + cash_total + cash_in - cash_out, 2)
	counted_cash = flt(expected_cash + ((day_index % 7) - 3), 2)
	frappe.db.set_value(
		"POS Cashier Shift",
		shift_name,
		{
			"cash_in_amount": cash_in,
			"cash_out_amount": cash_out,
			"expected_cash": expected_cash,
			"closing_amount": counted_cash,
			"variance": flt(counted_cash - expected_cash, 2),
		},
		update_modified=False,
	)
	return invoice_total


def _seed_branch_day_closings(ctx, start_date, end_date):
	for date_value in _date_range(start_date, end_date):
		date_key = date_value.strftime("%Y%m%d")
		closing_name = f"{DEMO_SIX_MONTH_PREFIX}-BDC-{date_key}"
		shift_name = f"{DEMO_SIX_MONTH_PREFIX}-SHIFT-{date_key}"
		shift = frappe.db.get_value(
			"POS Cashier Shift",
			shift_name,
			[
				"name",
				"cashier_employee",
				"cashier_name",
				"status",
				"opening_time",
				"closing_time",
				"opening_amount",
				"cash_in_amount",
				"cash_out_amount",
				"expected_cash",
				"closing_amount",
				"variance",
			],
			as_dict=True,
		)
		if not shift:
			continue
		invoice = frappe.db.sql(
			"""
			select count(*) as invoice_count, coalesce(sum(grand_total), 0) as sales_total
			from `tabPOS Invoice`
			where docstatus = 1 and pos_cashier_shift = %s
			""",
			shift_name,
			as_dict=True,
		)[0]
		_insert_direct_doc(
			"POS Branch Day Closing",
			closing_name,
			{
				"docstatus": 1,
				"branch": ctx.branch,
				"business_date": date_value,
				"manager_user": "Administrator",
				"closed_at": f"{date_value} 23:00:00",
				"total_cashier_shifts": 1,
				"open_shift_count": 0,
				"closed_shift_count": 1,
				"active_counter_session_count": 0,
				"total_invoice_count": invoice.invoice_count,
				"total_sales": invoice.sales_total,
				"total_cash_in": shift.cash_in_amount,
				"total_cash_out": shift.cash_out_amount,
				"total_expected_cash": shift.expected_cash,
				"total_closing_cash": shift.closing_amount,
				"total_variance": shift.variance,
				"notes": "Six month branch day closing demo data",
				"creation": f"{date_value} 23:00:00",
				"modified": f"{date_value} 23:00:00",
				"owner": "Administrator",
				"modified_by": "Administrator",
			},
		)
		frappe.get_doc(
			{
				"doctype": "POS Day Closing Cashier Summary",
				"name": f"{closing_name}-CASHIER-1",
				"parent": closing_name,
				"parenttype": "POS Branch Day Closing",
				"parentfield": "cashier_summaries",
				"idx": 1,
				"cashier_shift": shift.name,
				"cashier_employee": shift.cashier_employee,
				"cashier_name": shift.cashier_name,
				"status": shift.status,
				"opening_time": shift.opening_time,
				"closing_time": shift.closing_time,
				"opening_amount": shift.opening_amount,
				"cash_in_amount": shift.cash_in_amount,
				"cash_out_amount": shift.cash_out_amount,
				"expected_cash": shift.expected_cash,
				"closing_amount": shift.closing_amount,
				"variance": shift.variance,
				"invoice_count": invoice.invoice_count,
				"sales_total": invoice.sales_total,
			}
		).db_insert()
		frappe.get_doc(
			{
				"doctype": "POS Day Closing Counter Summary",
				"name": f"{closing_name}-COUNTER-1",
				"parent": closing_name,
				"parenttype": "POS Branch Day Closing",
				"parentfield": "counter_summaries",
				"idx": 1,
				"counter": DEMO_POS_COUNTER,
				"counter_code": "COUNTER-1",
				"session_count": 1,
				"invoice_count": invoice.invoice_count,
				"sales_total": invoice.sales_total,
				"expected_cash": shift.expected_cash,
				"closing_amount": shift.closing_amount,
				"variance": shift.variance,
			}
		).db_insert()


def _seed_normal_invoice(doctype, child_doctype, template_name, template_item, ctx, items, date_value, index, party_field):
	name = f"{DEMO_SIX_MONTH_PREFIX}-{frappe.scrub(doctype).upper().replace('_', '-')}-{date_value.strftime('%Y%m%d')}-{index:02d}"
	item_code = items[index % len(items)]
	rate = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": "Standard Selling"}, "price_list_rate") or 10
	if doctype == "Purchase Invoice":
		rate = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": "Standard Buying"}, "price_list_rate") or flt(rate * 0.62, 2)
	qty = 4 + (index % 5)
	amount = flt(qty * rate, 2)
	updates = {
		"docstatus": 1,
		"posting_date": date_value,
		"due_date": add_days(date_value, 15),
		"set_posting_time": 1,
		"posting_time": "11:10:00",
		"company": ctx.company,
		"set_warehouse": ctx.warehouse,
		"cost_center": ctx.cost_center,
		"is_return": 0,
		"creation": f"{date_value} 11:10:00",
		"modified": f"{date_value} 11:10:00",
		"owner": "Administrator",
		"modified_by": "Administrator",
		"remarks": "Six month retail back-office demo data",
	}
	updates[party_field] = ctx.customer if party_field == "customer" else ctx.supplier
	if doctype == "Sales Invoice":
		updates["is_pos"] = 0
		updates["update_stock"] = 1
		updates["paid_amount"] = amount if index % 3 else 0
		updates["base_paid_amount"] = updates["paid_amount"]
		updates["outstanding_amount"] = 0 if updates["paid_amount"] else amount
	if doctype == "Purchase Invoice":
		updates["credit_to"] = _payable_account(ctx.company)
		updates["outstanding_amount"] = amount if index % 4 else 0
	updates.update(_amount_fields(amount))
	if doctype == "Sales Invoice" and index % 3 == 0:
		updates["outstanding_amount"] = amount
	_clone_parent(doctype, template_name, name, updates)
	item_row_name = f"{name}-ITEM-1"
	_clone_child(child_doctype, template_item, item_row_name, name, doctype, "items", _invoice_item_values(item_code, qty, rate, 1, amount))
	if doctype == "Sales Invoice" and updates.get("paid_amount"):
		_clone_payment_rows(template_name, name, "Sales Invoice", [(ctx.cash_mode, amount)])
	if doctype in ("Sales Invoice", "Purchase Invoice"):
		sle_qty = -qty if doctype == "Sales Invoice" else qty
		_clone_stock_ledger(
			frappe.get_doc("Stock Ledger Entry", frappe.db.get_value("Stock Ledger Entry", {}, "name")),
			f"{DEMO_SIX_MONTH_PREFIX}-SLE-{frappe.scrub(doctype).upper().replace('_', '-')}-{date_value.strftime('%Y%m%d')}-{index:02d}",
			date_value,
			"11:10:00",
			doctype,
			name,
			item_code,
			sle_qty,
			rate,
			ctx.warehouse,
			item_row_name,
		)
	return amount


def _seed_workflow_doc(doctype, child_doctype, template_name, template_item, ctx, items, date_value, index, party_field):
	name = f"{DEMO_SIX_MONTH_PREFIX}-{frappe.scrub(doctype).upper().replace('_', '-')}-{date_value.strftime('%Y%m%d')}-{index:02d}"
	item_code = items[(index + 1) % len(items)]
	rate = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": "Standard Selling"}, "price_list_rate") or 10
	if doctype in ("Purchase Order", "Purchase Receipt"):
		rate = frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": "Standard Buying"}, "price_list_rate") or flt(rate * 0.62, 2)
	qty = 8 + (index % 4)
	amount = flt(qty * rate, 2)
	updates = {
		"docstatus": 1,
		"company": ctx.company,
		"set_warehouse": ctx.warehouse,
		"cost_center": ctx.cost_center,
		"creation": f"{date_value} 10:00:00",
		"modified": f"{date_value} 10:00:00",
		"owner": "Administrator",
		"modified_by": "Administrator",
	}
	updates[party_field] = ctx.customer if party_field == "customer" else ctx.supplier
	if doctype in ("Sales Order", "Purchase Order"):
		updates["transaction_date"] = date_value
		updates["delivery_date" if doctype == "Sales Order" else "schedule_date"] = add_days(date_value, 3)
	else:
		updates["posting_date"] = date_value
		updates["posting_time"] = "10:00:00"
		updates["set_posting_time"] = 1
	updates.update(_amount_fields(amount))
	_clone_parent(doctype, template_name, name, updates)
	_clone_child(child_doctype, template_item, f"{name}-ITEM-1", name, doctype, "items", _invoice_item_values(item_code, qty, rate, 1, amount))
	return amount


@frappe.whitelist()
def seed_six_month_demo_data():
	"""Seed a broad, repeatable retail demo window around today through the next 6 months."""
	seed_full_demo_data()
	company = _get_company()
	ctx = _ensure_masters(company)
	items = _ensure_items(ctx)
	_ensure_pos(ctx)
	employees = _ensure_demo_people(ctx)

	start_date = add_days(today(), -90)
	end_date = add_months(today(), 6)
	_ensure_demo_fiscal_years(start_date, end_date)
	_delete_six_month_demo_data()

	templates = frappe._dict(
		{
			"pos_invoice": frappe.get_doc("POS Invoice", frappe.db.get_value("POS Invoice", {"docstatus": 1, "is_return": 0}, "name", order_by="posting_date desc, creation desc")),
			"shift": frappe.get_doc("POS Cashier Shift", frappe.db.get_value("POS Cashier Shift", {}, "name", order_by="creation desc")),
			"session": frappe.get_doc("POS Counter Session", frappe.db.get_value("POS Counter Session", {}, "name", order_by="creation desc")),
			"opening": None,
			"closing": None,
			"cash_movement": None,
			"sle": frappe.get_doc("Stock Ledger Entry", frappe.db.get_value("Stock Ledger Entry", {}, "name", order_by="posting_date desc, creation desc")),
		}
	)
	templates.pos_item = templates.pos_invoice.items[0]
	if cash_movement_name := frappe.db.get_value("POS Cash Movement", {}, "name", order_by="creation desc"):
		templates.cash_movement = frappe.get_doc("POS Cash Movement", cash_movement_name)
	if opening_name := frappe.db.get_value("POS Opening Entry", {}, "name", order_by="creation desc"):
		templates.opening = frappe.get_doc("POS Opening Entry", opening_name)
	if closing_name := frappe.db.get_value("POS Closing Entry", {}, "name", order_by="creation desc"):
		templates.closing = frappe.get_doc("POS Closing Entry", closing_name)

	si_name = frappe.db.get_value("Sales Invoice", {"docstatus": 1, "is_return": 0}, "name", order_by="posting_date desc, creation desc")
	pi_name = frappe.db.get_value("Purchase Invoice", {"docstatus": 1}, "name", order_by="posting_date desc, creation desc")
	so_name = frappe.db.get_value("Sales Order", {"docstatus": 1}, "name", order_by="transaction_date desc, creation desc")
	po_name = frappe.db.get_value("Purchase Order", {"docstatus": 1}, "name", order_by="transaction_date desc, creation desc")
	dn_name = frappe.db.get_value("Delivery Note", {"docstatus": 1}, "name", order_by="posting_date desc, creation desc")
	pr_name = frappe.db.get_value("Purchase Receipt", {"docstatus": 1}, "name", order_by="posting_date desc, creation desc")

	counts = frappe._dict(pos_invoices=0, sales_invoices=0, purchase_invoices=0, cash_movements=0, cashier_shifts=0, stock_ledger_entries=0)
	for day_index, date_value in enumerate(_date_range(start_date, end_date)):
		_seed_pos_day(ctx, items, employees, date_value, day_index, templates)
		counts.pos_invoices += 4
		counts.cashier_shifts += 1
		counts.cash_movements += (1 if day_index % 6 == 0 else 0) + (1 if day_index % 4 == 0 else 0)
		counts.stock_ledger_entries += 4

		if day_index % 3 == 0 and si_name:
			si = frappe.get_doc("Sales Invoice", si_name)
			_seed_normal_invoice("Sales Invoice", "Sales Invoice Item", si_name, si.items[0], ctx, items, date_value, day_index, "customer")
			counts.sales_invoices += 1
			counts.stock_ledger_entries += 1
		if day_index % 5 == 0 and pi_name:
			pi = frappe.get_doc("Purchase Invoice", pi_name)
			_seed_normal_invoice("Purchase Invoice", "Purchase Invoice Item", pi_name, pi.items[0], ctx, items, date_value, day_index, "supplier")
			counts.purchase_invoices += 1
			counts.stock_ledger_entries += 1
		if day_index % 14 == 0:
			if so_name:
				so = frappe.get_doc("Sales Order", so_name)
				_seed_workflow_doc("Sales Order", "Sales Order Item", so_name, so.items[0], ctx, items, date_value, day_index, "customer")
			if po_name:
				po = frappe.get_doc("Purchase Order", po_name)
				_seed_workflow_doc("Purchase Order", "Purchase Order Item", po_name, po.items[0], ctx, items, date_value, day_index, "supplier")
			if dn_name:
				dn = frappe.get_doc("Delivery Note", dn_name)
				_seed_workflow_doc("Delivery Note", "Delivery Note Item", dn_name, dn.items[0], ctx, items, date_value, day_index, "customer")
			if pr_name:
				pr = frappe.get_doc("Purchase Receipt", pr_name)
				_seed_workflow_doc("Purchase Receipt", "Purchase Receipt Item", pr_name, pr.items[0], ctx, items, date_value, day_index, "supplier")

	_seed_branch_day_closings(ctx, start_date, end_date)
	counts.branch_day_closings = counts.cashier_shifts

	frappe.clear_cache()
	frappe.db.commit()
	counts.update({"from_date": str(start_date), "to_date": str(end_date), "employees": len(employees), "items": len(items)})
	return counts


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
