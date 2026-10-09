from __future__ import annotations

from datetime import timedelta
from retail.module_access import requires

import frappe
from frappe import _
from frappe.utils import flt, getdate, today
from frappe.utils.dashboard import cache_source

from retail.retail_app.report.cashier_wise_damage.cashier_wise_damage import execute as get_damage_report


def get_today():
	return getdate(today())


def _get_company_filter(company=None):
	user_default_company = frappe.defaults.get_user_default("Company")
	company = company or user_default_company or frappe.defaults.get_user_default("company")

	if not company:
		return None

	if not frappe.has_permission("Company", doc=company, ptype="read"):
		return None

	return company


@frappe.whitelist()
def get_today_sales(company=None, from_date=None, to_date=None, branch=None, counter=None):
    return get_profit_summary(company=_get_company_filter(company or frappe.form_dict.get("company")),
        from_date=from_date or frappe.form_dict.get("from_date"),
        to_date=to_date or frappe.form_dict.get("to_date"),
        branch=branch or frappe.form_dict.get("branch"), counter=counter or frappe.form_dict.get("counter")).net_sales


@frappe.whitelist()
def get_today_profit(company=None, from_date=None, to_date=None, branch=None, counter=None):
    return get_profit_summary(company=_get_company_filter(company or frappe.form_dict.get("company")),
        from_date=from_date or frappe.form_dict.get("from_date"),
        to_date=to_date or frappe.form_dict.get("to_date"),
        branch=branch or frappe.form_dict.get("branch"), counter=counter or frappe.form_dict.get("counter")).gross_profit


@frappe.whitelist()
def get_invoice_count_today():
	return get_sales_summary(company=frappe.form_dict.get("company")).invoice_count


@frappe.whitelist()
def get_return_amount_today():
	return get_sales_summary(company=frappe.form_dict.get("company")).return_amount


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


def get_sales_summary(company=None, posting_date=None, from_date=None, to_date=None, branch=None, counter=None):
    return get_profit_summary(posting_date, _get_company_filter(company), from_date, to_date, branch, counter)

def _get_today_gross_profit_from_report(posting_date=None, company=None):
	return get_profit_summary(posting_date or get_today(), _get_company_filter(company)).gross_profit


def get_invoice_summary(posting_date, company=None):
    return get_profit_summary(posting_date, company)


def get_profit_summary(posting_date=None, company=None, from_date=None, to_date=None, branch=None, counter=None, sales_source="Sales Invoice", van=False, van_session=None, driver=None):
    from retail.retail_app.report.profitability import profitability_rows, profitability_total
    filters = dict(company=company, from_date=from_date or posting_date or get_today(),
        to_date=to_date or posting_date or get_today(), branch=branch, counter=counter, van_session=van_session, driver=driver)
    if sales_source not in ("Sales Invoice", "POS Invoice"):
        frappe.throw("Unsupported profitability sales source")
    rows = profitability_rows(filters, sales_source, van=van)
    total = profitability_total(rows, "label")
    total.invoice_count = len({r.invoice_no for r in rows if not r.is_return})
    total.return_amount = total.get("sales_returns", 0)
    total.source_status = "; ".join(sorted({r.source_status for r in rows if r.source_status != "Recorded / Posted"})) or "Recorded / Posted"
    return total

def get_latest_sales_posting_date(from_date=None, to_date=None):
	conditions = ["docstatus = 1"]
	values = {}

	if from_date:
		conditions.append("posting_date >= %(from_date)s")
		values["from_date"] = from_date

	if to_date:
		conditions.append("posting_date <= %(to_date)s")
		values["to_date"] = to_date

	latest_date = frappe.db.sql(
		f"""
		select max(posting_date)
		from `tabSales Invoice`
		where {" and ".join(conditions)}
		""",
		values,
	)
	latest_date = latest_date[0][0] if latest_date else None

	return getdate(latest_date) if latest_date else None


def get_latest_pos_sales_posting_date(from_date=None, to_date=None):
	conditions = ["docstatus = 1"]
	values = {}

	if from_date:
		conditions.append("posting_date >= %(from_date)s")
		values["from_date"] = from_date

	if to_date:
		conditions.append("posting_date <= %(to_date)s")
		values["to_date"] = to_date

	latest_date = frappe.db.sql(
		f"""
		select max(posting_date)
		from `tabPOS Invoice`
		where {" and ".join(conditions)}
		""",
		values,
	)
	latest_date = latest_date[0][0] if latest_date else None

	return getdate(latest_date) if latest_date else None


def get_chart_period(days=7):
	end_date = get_today()
	start_date = end_date - timedelta(days=days - 1)

	if get_latest_sales_posting_date(start_date, end_date):
		return start_date, end_date

	latest_sales_date = get_latest_sales_posting_date()
	if latest_sales_date:
		return latest_sales_date - timedelta(days=days - 1), latest_sales_date

	return start_date, end_date


def get_pos_chart_period(days=7):
	end_date = get_today()
	start_date = end_date - timedelta(days=days - 1)

	if get_latest_pos_sales_posting_date(start_date, end_date):
		return start_date, end_date

	latest_sales_date = get_latest_pos_sales_posting_date()
	if latest_sales_date:
		return latest_sales_date - timedelta(days=days - 1), latest_sales_date

	return start_date, end_date


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
	start_date, end_date = get_chart_period()
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
		{"from_date": start_date, "to_date": end_date},
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
	posting_date = get_latest_sales_posting_date(get_today(), get_today()) or get_latest_sales_posting_date() or get_today()
	rows = frappe.db.sql(
		"""
		select
			case
				when ifnull(si.custom_counter, '') = '' then %(no_counter)s
				else coalesce(nullif(counter.counter_name, ''), si.custom_counter)
			end as counter,
			sum(case when si.is_return = 1 then -abs(si.base_net_total) else abs(si.base_net_total) end) as net_sales
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
		{"posting_date": posting_date, "no_counter": _("No Counter")},
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
	start_date, end_date = get_chart_period()
	rows = frappe.db.sql(
		"""
		select
			posting_date,
			sum(case when is_return = 1 then -abs(base_net_total) else abs(base_net_total) end) as net_sales
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


@frappe.whitelist()
@requires("POS")
@cache_source
def get_pos_top_selling_products(
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
	start_date, end_date = get_pos_chart_period()
	rows = frappe.db.sql(
		"""
		select
			pii.item_name,
			sum(case when pi.is_return = 1 then -abs(coalesce(pii.stock_qty, pii.qty, 0)) else abs(coalesce(pii.stock_qty, pii.qty, 0)) end) as net_qty
		from `tabPOS Invoice Item` pii
		inner join `tabPOS Invoice` pi on pi.name = pii.parent
		inner join `tabItem` item on item.name = pii.item_code
		where pi.docstatus = 1
			and pi.posting_date between %(from_date)s and %(to_date)s
			and item.is_stock_item = 1
		group by pii.item_code
		having net_qty > 0
		order by net_qty desc, pii.item_name asc
		limit 10
		""",
		{"from_date": start_date, "to_date": end_date},
		as_dict=True,
	)
	return build_bar_chart(rows, "item_name", "net_qty", _("Qty Sold"))


@frappe.whitelist()
@requires("POS")
@cache_source
def get_pos_sales_by_counter(
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
	posting_date = get_latest_pos_sales_posting_date(get_today(), get_today()) or get_latest_pos_sales_posting_date() or get_today()
	rows = frappe.db.sql(
		"""
		select
			coalesce(nullif(pi.pos_counter, ''), %(no_counter)s) as counter,
			sum(case when pi.is_return = 1 then -abs(pi.base_net_total) else abs(pi.base_net_total) end) as net_sales
		from `tabPOS Invoice` pi
		where pi.docstatus = 1
			and pi.posting_date = %(posting_date)s
		group by coalesce(nullif(pi.pos_counter, ''), %(no_counter)s)
		having net_sales != 0
		order by net_sales desc
		""",
		{"posting_date": posting_date, "no_counter": _("No Counter")},
		as_dict=True,
	)
	return build_bar_chart(rows, "counter", "net_sales", _("Net Sales"))


@frappe.whitelist()
@requires("POS")
@cache_source
def get_pos_sales_trend_7_days(
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
	start_date, end_date = get_pos_chart_period()
	rows = frappe.db.sql(
		"""
		select
			posting_date,
			sum(case when is_return = 1 then -abs(base_net_total) else abs(base_net_total) end) as net_sales
		from `tabPOS Invoice`
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


def get_latest_van_sales_posting_date(from_date=None, to_date=None):
	conditions = ["docstatus = 1", "custom_is_van_sale = 1"]
	values = {}

	if from_date:
		conditions.append("posting_date >= %(from_date)s")
		values["from_date"] = from_date

	if to_date:
		conditions.append("posting_date <= %(to_date)s")
		values["to_date"] = to_date

	latest_date = frappe.db.sql(
		f"""
		select max(posting_date)
		from `tabSales Invoice`
		where {" and ".join(conditions)}
		""",
		values,
	)
	latest_date = latest_date[0][0] if latest_date else None

	return getdate(latest_date) if latest_date else None



def get_van_chart_period(days=7):
	end_date = get_today()
	start_date = end_date - timedelta(days=days - 1)

	if get_latest_van_sales_posting_date(start_date, end_date):
		return start_date, end_date

	latest_sales_date = get_latest_van_sales_posting_date()
	if latest_sales_date:
		return latest_sales_date - timedelta(days=days - 1), latest_sales_date

	return start_date, end_date



@frappe.whitelist()
def get_van_top_selling_products(
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
	from retail.van_assignment import chart_condition
	condition = chart_condition().replace("`tabSales Invoice`.", "si.")
	start_date, end_date = get_van_chart_period()
	rows = frappe.db.sql(
		f"""
		select
			sii.item_name,
			sum(case when si.is_return = 1 then -abs(coalesce(sii.stock_qty, sii.qty, 0)) else abs(coalesce(sii.stock_qty, sii.qty, 0)) end) as net_qty
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		inner join `tabItem` item on item.name = sii.item_code
		where si.docstatus = 1
			and {condition}
			and si.custom_is_van_sale = 1
			and si.posting_date between %(from_date)s and %(to_date)s
			and item.is_stock_item = 1
		group by sii.item_code
		having net_qty > 0
		order by net_qty desc, sii.item_name asc
		limit 10
		""",
		{"from_date": start_date, "to_date": end_date},
		as_dict=True,
	)
	return build_bar_chart(rows, "item_name", "net_qty", _("Qty Sold"))



@frappe.whitelist()
def get_van_sales_by_van(
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
	from retail.van_assignment import chart_condition
	condition = chart_condition()
	posting_date = get_latest_van_sales_posting_date(get_today(), get_today()) or get_latest_van_sales_posting_date() or get_today()
	rows = frappe.db.sql(
		f"""
		select
			coalesce(nullif(custom_van, ''), %(no_van)s) as van,
			sum(case when is_return = 1 then -abs(base_net_total) else abs(base_net_total) end) as net_sales
		from `tabSales Invoice`
		where docstatus = 1
			and {condition}
			and custom_is_van_sale = 1
			and posting_date = %(posting_date)s
		group by coalesce(nullif(custom_van, ''), %(no_van)s)
		having net_sales != 0
		order by net_sales desc
		""",
		{"posting_date": posting_date, "no_van": _("No Van")},
		as_dict=True,
	)
	return build_bar_chart(rows, "van", "net_sales", _("Net Sales"))



@frappe.whitelist()
def get_van_sales_trend_7_days(
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
	from retail.van_assignment import chart_condition
	condition = chart_condition()
	start_date, end_date = get_van_chart_period()
	rows = frappe.db.sql(
		f"""
		select
			posting_date,
			sum(case when is_return = 1 then -abs(base_net_total) else abs(base_net_total) end) as net_sales
		from `tabSales Invoice`
		where docstatus = 1
			and {condition}
			and custom_is_van_sale = 1
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


@frappe.whitelist()
def get_profit_number_card(company=None, from_date=None, to_date=None, branch=None, counter=None):
    """Number Card adapter: null must not become zero or crash Frappe's custom widget."""
    company = _get_company_filter(company or frappe.form_dict.get("company"))
    summary = get_profit_summary(company=company,
        from_date=from_date or frappe.form_dict.get("from_date"),
        to_date=to_date or frappe.form_dict.get("to_date"),
        branch=branch or frappe.form_dict.get("branch"),
        counter=counter or frappe.form_dict.get("counter"))
    return _format_profit_number_card(summary, company)


def _format_profit_number_card(summary, company):
    from html import escape
    if summary.gross_profit is None:
        label = _("N/A")
    else:
        currency = frappe.get_cached_value("Company", company, "default_currency") if company else None
        label = frappe.format_value(summary.gross_profit, {"fieldtype": "Currency", "options": currency})
    if summary.source_status != "Recorded / Posted":
        return '<span title="{}">{}</span>'.format(
            escape(summary.source_status, quote=True), escape(str(label)), _(""))
    return label


@frappe.whitelist()
def get_business_home_profit_cards(contexts):
    """Request-scoped sharing, keyed after the legacy effective filters resolve.

    Exceptions abort the whole response. No partial values or cached accounting
    data are returned, and the original invoice permission path is unchanged.
    """
    contexts = frappe.parse_json(contexts)
    if not isinstance(contexts, list) or len(contexts) > 32:
        frappe.throw("Invalid Business Home card contexts")
    summaries = {}
    results = []
    for context in contexts:
        company = _get_company_filter(context.get("company"))
        today_only = context.get("today_only")
        from_date = (not today_only and context.get("from_date")) or get_today()
        to_date = (not today_only and context.get("to_date")) or get_today()
        branch = (not today_only and context.get("branch")) or None
        counter = (not today_only and context.get("counter")) or None
        key = (company, str(from_date), str(to_date), branch, counter)
        if key not in summaries:
            summary = get_profit_summary(company=company, from_date=from_date,
                to_date=to_date, branch=branch, counter=counter)
            summaries[key] = {
                "sales": summary.net_sales,
                "profit": _format_profit_number_card(summary, company),
                "count": summary.invoice_count,
                "returns": summary.return_amount,
            }
        results.append(summaries[key])
    return results
