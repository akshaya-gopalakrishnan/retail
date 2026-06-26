from __future__ import annotations

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate, today
from frappe.utils.dashboard import cache_source

from retail.retail_app.report.cashier_wise_damage.cashier_wise_damage import execute as get_damage_report


def get_today():
	return getdate(today())


@frappe.whitelist()
def get_today_sales():
	return get_sales_summary().net_sales


@frappe.whitelist()
def get_today_profit():
	return get_sales_summary().gross_profit


@frappe.whitelist()
def get_invoice_count_today():
	return get_sales_summary().invoice_count


@frappe.whitelist()
def get_return_amount_today():
	return get_sales_summary().return_amount


@frappe.whitelist()
def get_cash_in_hand_today():
	return flt(
		frappe.db.sql(
			"""
			select sum(abs(sip.base_amount))
			from `tabSales Invoice Payment` sip
			inner join `tabSales Invoice` si on si.name = sip.parent
			where si.docstatus = 1
				and si.posting_date = %(posting_date)s
				and ifnull(si.is_return, 0) = 0
				and lower(ifnull(sip.mode_of_payment, '')) like '%%cash%%'
			""",
			{"posting_date": get_today()},
		)[0][0]
	)


@frappe.whitelist()
def get_damage_amount_today():
	filters = {"from_date": get_today(), "to_date": get_today()}
	_, rows = get_damage_report(filters)
	return sum(flt(row.get("damage_value")) for row in rows)


def get_sales_summary(posting_date=None):
	posting_date = posting_date or get_today()
	invoices = get_invoice_summary(posting_date)
	items = get_profit_summary(posting_date)

	return frappe._dict(
		{
			"gross_sales": flt(invoices.gross_sales),
			"return_amount": flt(invoices.return_amount),
			"net_sales": flt(invoices.gross_sales) - flt(invoices.return_amount),
			"invoice_count": flt(invoices.invoice_count),
			"gross_profit": flt(items.gross_profit),
		}
	)


def get_invoice_summary(posting_date):
	return frappe.db.sql(
		"""
		select
			sum(case when ifnull(is_return, 0) = 1 then 0 else abs(base_grand_total) end) as gross_sales,
			sum(case when ifnull(is_return, 0) = 1 then abs(base_grand_total) else 0 end) as return_amount,
			count(distinct case when ifnull(is_return, 0) = 0 then name end) as invoice_count
		from `tabSales Invoice`
		where docstatus = 1
			and posting_date = %(posting_date)s
		""",
		{"posting_date": posting_date},
		as_dict=True,
	)[0]


def get_profit_summary(posting_date):
	return frappe.db.sql(
		"""
		select
			sum(
				case
					when si.is_return = 1 then -1
					else 1
				end
				* (abs(sii.base_net_amount) - abs(coalesce(sii.stock_qty, sii.qty, 0)) * coalesce(sii.incoming_rate, 0))
			) as gross_profit
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		where si.docstatus = 1
			and si.posting_date = %(posting_date)s
		""",
		{"posting_date": posting_date},
		as_dict=True,
	)[0]


@frappe.whitelist()
@cache_source
def get_top_selling_products(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	start_date = get_today() - timedelta(days=6)
	rows = frappe.db.sql(
		"""
		select
			sii.item_name,
			sum(case when si.is_return = 1 then -abs(sii.stock_qty) else abs(sii.stock_qty) end) as net_qty
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		inner join `tabItem` item on item.name = sii.item_code
		where si.docstatus = 1
			and si.posting_date between %(from_date)s and %(to_date)s
			and item.is_stock_item = 1
		group by sii.item_code
		having net_qty > 0
		order by net_qty desc, sii.item_name asc
		limit 10
		""",
		{"from_date": start_date, "to_date": get_today()},
		as_dict=True,
	)
	return build_bar_chart(rows, "item_name", "net_qty", _("Qty Sold"))


@frappe.whitelist()
@cache_source
def get_sales_by_counter(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	rows = frappe.db.sql(
		"""
		select
			case
				when ifnull(si.custom_counter, '') = '' then %(no_counter)s
				else coalesce(nullif(counter.counter_name, ''), si.custom_counter)
			end as counter,
			sum(case when si.is_return = 1 then -abs(si.base_grand_total) else abs(si.base_grand_total) end) as net_sales
		from `tabSales Invoice` si
		left join `tabCounter` counter on counter.name = si.custom_counter
		where si.docstatus = 1
			and si.posting_date = %(posting_date)s
		group by
			case
				when ifnull(si.custom_counter, '') = '' then %(no_counter)s
				else coalesce(nullif(counter.counter_name, ''), si.custom_counter)
			end
		having net_sales != 0
		order by net_sales desc
		""",
		{"posting_date": get_today(), "no_counter": _("No Counter")},
		as_dict=True,
	)
	return build_bar_chart(rows, "counter", "net_sales", _("Net Sales"))


@frappe.whitelist()
@cache_source
def get_sales_trend_7_days(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	end_date = get_today()
	start_date = end_date - timedelta(days=6)
	rows = frappe.db.sql(
		"""
		select
			posting_date,
			sum(case when is_return = 1 then -abs(base_grand_total) else abs(base_grand_total) end) as net_sales
		from `tabSales Invoice`
		where docstatus = 1
			and posting_date between %(from_date)s and %(to_date)s
		group by posting_date
		""",
		{"from_date": start_date, "to_date": end_date},
		as_dict=True,
	)
	values_by_date = {getdate(row.posting_date): flt(row.net_sales) for row in rows}
	labels = []
	values = []

	for offset in range(7):
		date = start_date + timedelta(days=offset)
		labels.append(date.strftime("%d %b"))
		values.append(values_by_date.get(date, 0))

	return {"labels": labels, "datasets": [{"name": _("Net Sales"), "values": values}], "type": "line"}


def build_bar_chart(rows, label_field, value_field, dataset_name):
	if not rows:
		return []

	return {
		"labels": [row.get(label_field) or _("Not Set") for row in rows],
		"datasets": [{"name": dataset_name, "values": [flt(row.get(value_field)) for row in rows]}],
		"type": "bar",
	}
