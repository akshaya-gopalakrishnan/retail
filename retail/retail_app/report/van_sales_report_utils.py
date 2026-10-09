from retail.retail_app.report.profitability import sales_cost_join, sales_cost_sql, set_profit, profitability_total
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate


VAN_REPORT_ROLES = ("Van Sales User", "Van Sales Manager", "System Manager", "Accounts Manager")


def normalize_filters(filters=None):
	from retail.module_access import require
	require("Van Sales")
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", getdate())
	filters.setdefault("to_date", getdate())
	return filters


def report_roles():
	return [{"role": role} for role in VAN_REPORT_ROLES]


def common_filters_sql(alias):
	from retail.van_assignment import is_operator
	assignment = ""
	if is_operator():
		assignment = f"and {alias}.custom_van_session in (select name from `tabVan Session` where custom_salesperson = {frappe.db.escape(frappe.session.user)})"
	return f"""
		{assignment}
		and (%(company)s is null or {alias}.company = %(company)s)
		and (%(van_session)s is null or {alias}.custom_van_session = %(van_session)s)
		and (%(van)s is null or {alias}.custom_van = %(van)s)
		and (%(driver)s is null or {alias}.custom_driver = %(driver)s)
	"""


def filter_values(filters):
	return {
		"from_date": filters.from_date,
		"to_date": filters.to_date,
		"company": filters.get("company"),
		"van_session": filters.get("van_session"),
		"van": filters.get("van"),
		"driver": filters.get("driver"),
	}


def add_total_row(data, label_field, label=None):
	label = label or _("Total")
	if not data:
		return data

	total = frappe._dict({label_field: label, "is_total_row": 1})
	for row in data:
		for key, value in row.items():
			if key == label_field or key == "is_total_row":
				continue
			if isinstance(value, (int, float)):
				total[key] = flt(total.get(key)) + flt(value)

	if any("gross_profit" in row for row in data):
		values = profitability_total(data, label_field)
		for field in ("gross_sales", "discount", "sales_returns", "net_sales", "vat", "cost_amount", "gross_profit", "profit_percent", "source_status"):
			total[field] = values[field]
		set_profit(total)
	if "average_bill_value" in total:
		total.average_bill_value = total.net_sales / total.invoice_count if total.invoice_count else 0
	data.append(total)
	return data


def get_van_sales_invoices(filters):
	return frappe.db.sql(
		f"""
		select
			si.name,
			si.posting_date,
			si.customer,
			si.customer_name,
			si.custom_van_session as van_session,
			si.custom_van as van,
			si.custom_van_warehouse as van_warehouse,
			si.custom_driver as driver,
			si.custom_driver_name as driver_name,
			si.is_return,
			si.base_grand_total,
			si.base_net_total,
			si.base_total_taxes_and_charges,
			si.base_discount_amount,
			si.base_paid_amount,
			si.outstanding_amount,
			si.status
		from `tabSales Invoice` si
		where si.docstatus = 1
			and si.custom_is_van_sale = 1
			and si.posting_date between %(from_date)s and %(to_date)s
			{common_filters_sql("si")}
		order by si.posting_date desc, si.modified desc
		""",
		filter_values(filters),
		as_dict=True,
	)


def get_van_sales_items(filters):
	return frappe.db.sql(
		f"""
		select
			si.name as sales_invoice,
			si.posting_date,
			si.customer,
			si.customer_name,
			si.custom_van_session as van_session,
			si.custom_van as van,
			si.custom_van_warehouse as van_warehouse,
			si.custom_driver as driver,
			si.custom_driver_name as driver_name,
			si.is_return,
			sii.item_code,
			sii.item_name,
			sii.item_group,
			sii.warehouse,
			sii.qty,
			sii.stock_qty,
			sii.uom,
			sii.stock_uom,
			sii.base_net_rate,
			sii.base_net_amount,
			{sales_cost_sql()} as cost_amount
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		{sales_cost_join()}
		where si.docstatus = 1
			and si.custom_is_van_sale = 1
			and si.posting_date between %(from_date)s and %(to_date)s
			{common_filters_sql("si")}
		order by si.posting_date desc, si.name desc, sii.idx
		""",
		filter_values(filters),
		as_dict=True,
	)


def get_van_stock_items(filters, stock_type=None):
	values = filter_values(filters)
	values["stock_type"] = stock_type
	return frappe.db.sql(
		f"""
		select
			se.name as stock_entry,
			se.posting_date,
			se.stock_entry_type,
			se.custom_van_stock_entry_type as van_stock_entry_type,
			se.custom_van_session as van_session,
			se.custom_van as van,
			se.custom_van_warehouse as van_warehouse,
			se.custom_driver as driver,
			se.custom_driver_name_ as driver_name,
			sed.item_code,
			sed.item_name,
			sed.s_warehouse,
			sed.t_warehouse,
			sed.qty,
			sed.transfer_qty,
			sed.uom,
			sed.stock_uom,
			sed.basic_rate,
			sed.basic_amount,
			sed.amount
		from `tabStock Entry Detail` sed
		inner join `tabStock Entry` se on se.name = sed.parent
		where se.docstatus = 1
			and se.custom_is_van_stock_entry = 1
			and se.posting_date between %(from_date)s and %(to_date)s
			and (%(stock_type)s is null or se.custom_van_stock_entry_type = %(stock_type)s)
			{common_filters_sql("se")}
		order by se.posting_date desc, se.name desc, sed.idx
		""",
		values,
		as_dict=True,
	)


def signed_qty(item):
	return -abs(flt(item.stock_qty or item.qty)) if item.is_return else flt(item.stock_qty or item.qty)


def signed_amount(item):
	return -abs(flt(item.base_net_amount)) if item.is_return else flt(item.base_net_amount)


def cost_amount(item):
	return item.cost_amount


def group_key(row, fields):
	return tuple(row.get(field) for field in fields)


def default_dict(factory):
	return defaultdict(factory)
