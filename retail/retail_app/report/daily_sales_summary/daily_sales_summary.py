from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", getdate())
	filters.setdefault("to_date", getdate())
	filters.sales_channel = filters.get("sales_channel") or None

	return get_columns(), get_data(filters), None, None, None, 1


def get_data(filters):
	summary = defaultdict(new_summary_row)

	for invoice in get_sales_invoice_rows(filters):
		add_invoice(summary, invoice)

	for item in get_sales_invoice_item_rows(filters):
		add_item(summary, item)

	data = []
	for key in sorted(summary, reverse=True):
		row = summary[key]
		set_calculated_values(row)
		data.append(row)

	if data:
		data.append(get_total_row(data))

	return data


def new_summary_row():
	return frappe._dict(
		{
			"posting_date": None,
			"counter": None,
			"invoice_count": 0,
			"return_count": 0,
			"gross_sales": 0,
			"return_amount": 0,
			"net_sales": 0,
			"paid_amount": 0,
			"outstanding_amount": 0,
			"average_bill_value": 0,
			"items_sold": 0,
			"net_item_sales": 0,
			"gross_profit": 0,
			"profit_percent": 0,
		}
	)


def set_calculated_values(row):
	row.net_sales = flt(row.gross_sales) - flt(row.return_amount)
	row.average_bill_value = flt(row.net_sales / row.invoice_count) if row.invoice_count else 0
	row.profit_percent = flt(row.gross_profit / row.net_item_sales * 100) if row.net_item_sales else 0


def get_total_row(data):
	total_row = new_summary_row()
	total_row.counter = _("Total")

	for row in data:
		total_row.invoice_count += flt(row.invoice_count)
		total_row.return_count += flt(row.return_count)
		total_row.gross_sales += flt(row.gross_sales)
		total_row.return_amount += flt(row.return_amount)
		total_row.paid_amount += flt(row.paid_amount)
		total_row.outstanding_amount += flt(row.outstanding_amount)
		total_row.items_sold += flt(row.items_sold)
		total_row.net_item_sales += flt(row.net_item_sales)
		total_row.gross_profit += flt(row.gross_profit)

	set_calculated_values(total_row)
	total_row.is_total_row = 1

	return total_row


def add_invoice(summary, invoice):
	counter = invoice.counter_name or _("No Counter")
	key = (invoice.posting_date, counter)
	row = summary[key]
	row.posting_date = invoice.posting_date
	row.counter = counter

	grand_total = abs(flt(invoice.base_grand_total))
	paid_amount = abs(flt(invoice.base_paid_amount))
	outstanding_amount = abs(flt(invoice.outstanding_amount))

	if invoice.is_return:
		row.return_count += 1
		row.return_amount += grand_total
		row.paid_amount -= paid_amount
		row.outstanding_amount -= outstanding_amount
	else:
		row.invoice_count += 1
		row.gross_sales += grand_total
		row.paid_amount += paid_amount
		row.outstanding_amount += outstanding_amount


def add_item(summary, item):
	counter = item.counter_name or _("No Counter")
	key = (item.posting_date, counter)
	row = summary[key]
	row.posting_date = item.posting_date
	row.counter = counter

	sign = -1 if item.is_return else 1
	qty = abs(flt(item.stock_qty) or flt(item.qty))
	net_amount = abs(flt(item.base_net_amount))
	cost_amount = abs(qty * flt(item.incoming_rate))

	row.items_sold += sign * qty
	row.net_item_sales += sign * net_amount
	row.gross_profit += sign * (net_amount - cost_amount)


def get_sales_invoice_rows(filters):
	return frappe.db.sql(
		"""
		select
			name,
			posting_date,
			coalesce(custom_counter, '') as custom_counter,
			coalesce(custom_counter_name, custom_counter, '') as counter_name,
			is_return,
			base_grand_total,
			base_paid_amount,
			outstanding_amount
		from `tabSales Invoice`
		where docstatus = 1
			and posting_date between %(from_date)s and %(to_date)s
			and (%(company)s is null or company = %(company)s)
			and (%(counter)s is null or custom_counter = %(counter)s)
			and (%(sales_channel)s is null or sales_channel = %(sales_channel)s)
		""",
		{
			"from_date": filters.from_date,
			"to_date": filters.to_date,
			"company": filters.get("company"),
			"counter": filters.get("counter"),
			"sales_channel": filters.get("sales_channel"),
		},
		as_dict=True,
	)


def get_sales_invoice_item_rows(filters):
	return frappe.db.sql(
		"""
		select
			si.posting_date,
			coalesce(si.custom_counter, '') as custom_counter,
			coalesce(si.custom_counter_name, si.custom_counter, '') as counter_name,
			si.is_return,
			sii.qty,
			sii.stock_qty,
			sii.base_net_amount,
			sii.incoming_rate
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		where si.docstatus = 1
			and si.posting_date between %(from_date)s and %(to_date)s
			and (%(company)s is null or si.company = %(company)s)
			and (%(counter)s is null or si.custom_counter = %(counter)s)
			and (%(sales_channel)s is null or si.sales_channel = %(sales_channel)s)
		""",
		{
			"from_date": filters.from_date,
			"to_date": filters.to_date,
			"company": filters.get("company"),
			"counter": filters.get("counter"),
			"sales_channel": filters.get("sales_channel"),
		},
		as_dict=True,
	)


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Counter"),
			"fieldname": "counter",
			"fieldtype": "Data",
			"width": 160,
		},
		{"label": _("Invoice Count"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 110},
		{"label": _("Return Count"), "fieldname": "return_count", "fieldtype": "Int", "width": 110},
		{"label": _("Gross Sales"), "fieldname": "gross_sales", "fieldtype": "Currency", "width": 130},
		{"label": _("Return Amount"), "fieldname": "return_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 130},
		{"label": _("Items Sold"), "fieldname": "items_sold", "fieldtype": "Float", "width": 110},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 130},
		{"label": _("Profit %"), "fieldname": "profit_percent", "fieldtype": "Percent", "width": 100},
		{"label": _("Paid Amount"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 130},
		{
			"label": _("Outstanding Amount"),
			"fieldname": "outstanding_amount",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("Average Bill Value"),
			"fieldname": "average_bill_value",
			"fieldtype": "Currency",
			"width": 150,
		},
	]
