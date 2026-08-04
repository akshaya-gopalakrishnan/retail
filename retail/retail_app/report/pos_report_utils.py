from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate


POS_REPORTS = (
	"POS Sales Summary",
	"POS Transaction Log",
	"POS Item-wise Sales",
	"POS Category Item Group Sales",
	"POS Hourly Sales",
	"POS Return Report",
	"Cashier Wise Sales",
	"Counter Wise Sales",
	"Shift Closing Variance",
	"POS Payment Mode Summary",
	"POS Discount Report",
	"POS Price Override Report",
	"POS Daily Closing Summary",
	"POS Cash Movement Report",
)

REPORT_ROLES = (
	{"role": "Sales User"},
	{"role": "Sales Manager"},
	{"role": "Accounts User"},
	{"role": "Accounts Manager"},
	{"role": "System Manager"},
)


def execute_report(report_name, filters=None):
	filters = get_filters(filters)
	return REPORT_EXECUTORS[report_name](filters)


def get_filters(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", getdate())
	filters.setdefault("to_date", getdate())
	return filters


def ensure_pos_reports():
	if not frappe.db.table_exists("Report"):
		return

	ensure_pos_dashboard_charts()

	for report_name in POS_REPORTS:
		if frappe.db.exists("Report", report_name):
			continue

		doc = frappe.new_doc("Report")
		doc.update(
			{
				"report_name": report_name,
				"module": "Retail-app",
				"ref_doctype": get_ref_doctype(report_name),
				"report_type": "Script Report",
				"is_standard": "Yes",
				"prepared_report": 0,
				"add_total_row": 1 if report_name not in ("POS Transaction Log", "POS Return Report") else 0,
			}
		)
		doc.roles = []
		for role in REPORT_ROLES:
			doc.append("roles", role)
		doc.flags.ignore_validate = True
		doc.save(ignore_permissions=True)

	from retail.patches.v1_2.setup_pos_workspace import execute as setup_pos_workspace

	setup_pos_workspace()


def ensure_pos_dashboard_charts():
	if not frappe.db.table_exists("Dashboard Chart Source") or not frappe.db.table_exists("Dashboard Chart"):
		return

	sources = {
		"POS Sales Trend 7 Days": "retail.retail_app.retail_dashboard.get_pos_sales_trend_7_days",
		"POS Sales by Counter": "retail.retail_app.retail_dashboard.get_pos_sales_by_counter",
		"POS Top Selling Products": "retail.retail_app.retail_dashboard.get_pos_top_selling_products",
	}
	chart_types = {
		"POS Sales Trend 7 Days": "Line",
		"POS Sales by Counter": "Bar",
		"POS Top Selling Products": "Bar",
	}

	for source_name in sources:
		if not frappe.db.exists("Dashboard Chart Source", source_name):
			source = frappe.new_doc("Dashboard Chart Source")
			source.update(
				{
					"source_name": source_name,
					"module": "Retail-app",
					"timeseries": 0,
				}
			)
			source.save(ignore_permissions=True)

		if frappe.db.exists("Dashboard Chart", source_name):
			continue

		chart = frappe.new_doc("Dashboard Chart")
		chart.update(
			{
				"chart_name": source_name,
				"module": "Retail-app",
				"chart_type": "Custom",
				"document_type": "POS Invoice",
				"source": source_name,
				"type": chart_types[source_name],
				"is_public": 1,
				"is_standard": 1,
				"filters_json": "[]",
				"dynamic_filters_json": "[]",
				"timeseries": 0,
				"number_of_groups": 0,
			}
		)
		chart.flags.ignore_validate = True
		chart.save(ignore_permissions=True)


def get_ref_doctype(report_name):
	if report_name in ("Shift Closing Variance",):
		return "POS Cashier Shift"
	if report_name == "POS Cash Movement Report":
		return "POS Cash Movement"
	if report_name == "POS Transaction Log":
		return "POS Invoice"
	return "POS Invoice"


def pos_invoice_conditions(filters, alias="pi", include_cancelled=False):
	conditions = [f"{alias}.docstatus in (1, 2)" if include_cancelled else f"{alias}.docstatus = 1"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.get("from_date"):
		conditions.append(f"{alias}.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append(f"{alias}.posting_date <= %(to_date)s")
	if filters.get("company"):
		conditions.append(f"{alias}.company = %(company)s")
		values["company"] = filters.company
	if filters.get("branch"):
		conditions.append(f"{alias}.pos_branch = %(branch)s")
		values["branch"] = filters.branch
	if filters.get("counter"):
		conditions.append(f"{alias}.pos_counter = %(counter)s")
		values["counter"] = filters.counter
	if filters.get("cashier_employee"):
		conditions.append(f"{alias}.pos_cashier_employee = %(cashier_employee)s")
		values["cashier_employee"] = filters.cashier_employee
	if filters.get("cashier"):
		conditions.append(f"{alias}.pos_cashier = %(cashier)s")
		values["cashier"] = filters.cashier
	if filters.get("customer"):
		conditions.append(f"{alias}.customer = %(customer)s")
		values["customer"] = filters.customer
	if filters.get("pos_profile"):
		conditions.append(f"{alias}.pos_profile = %(pos_profile)s")
		values["pos_profile"] = filters.pos_profile
	if filters.get("shift"):
		conditions.append(f"{alias}.pos_cashier_shift = %(shift)s")
		values["shift"] = filters.shift
	if filters.get("status"):
		if filters.status == "Cancelled":
			conditions.append(f"{alias}.docstatus = 2")
		elif filters.status == "Return":
			conditions.append(f"{alias}.docstatus = 1 and {alias}.is_return = 1")
		else:
			conditions.append(f"{alias}.docstatus = 1 and {alias}.status = %(status)s")
			values["status"] = filters.status

	return " and ".join(conditions), values


def item_conditions(filters, invoice_alias="pi", item_alias="pii"):
	conditions, values = pos_invoice_conditions(filters, invoice_alias)
	if filters.get("item_code"):
		conditions += f" and {item_alias}.item_code = %(item_code)s"
		values["item_code"] = filters.item_code
	if filters.get("item_group"):
		conditions += f" and {item_alias}.item_group = %(item_group)s"
		values["item_group"] = filters.item_group
	if filters.get("warehouse"):
		conditions += f" and {item_alias}.warehouse = %(warehouse)s"
		values["warehouse"] = filters.warehouse
	return conditions, values


def signed_amount_expr(field, alias="pi"):
	return f"case when {alias}.is_return = 1 then -abs(coalesce({alias}.{field}, 0)) else abs(coalesce({alias}.{field}, 0)) end"


def signed_item_amount_expr(field="base_net_amount", invoice_alias="pi", item_alias="pii"):
	return (
		f"case when {invoice_alias}.is_return = 1 then -abs(coalesce({item_alias}.{field}, 0)) "
		f"else abs(coalesce({item_alias}.{field}, 0)) end"
	)


def signed_qty_expr(invoice_alias="pi", item_alias="pii"):
	return (
		f"case when {invoice_alias}.is_return = 1 then -abs(coalesce({item_alias}.stock_qty, {item_alias}.qty, 0)) "
		f"else abs(coalesce({item_alias}.stock_qty, {item_alias}.qty, 0)) end"
	)


def get_payment_modes(invoice_names):
	if not invoice_names:
		return {}
	rows = frappe.db.sql(
		"""
		select parent, mode_of_payment
		from `tabSales Invoice Payment`
		where parent in %(invoice_names)s
			and ifnull(mode_of_payment, '') != ''
		order by parent, idx
		""",
		{"invoice_names": tuple(invoice_names)},
		as_dict=True,
	)
	modes = defaultdict(list)
	for row in rows:
		if row.mode_of_payment not in modes[row.parent]:
			modes[row.parent].append(row.mode_of_payment)
	return {invoice: ", ".join(values) for invoice, values in modes.items()}


def pos_sales_summary(filters):
	conditions, values = pos_invoice_conditions(filters)
	rows = frappe.db.sql(
		f"""
		select
			pi.posting_date,
			pi.pos_branch as branch,
			pi.pos_counter as counter,
			count(case when ifnull(pi.is_return, 0) = 0 then 1 end) as invoice_count,
			count(case when ifnull(pi.is_return, 0) = 1 then 1 end) as return_count,
			sum(case when ifnull(pi.is_return, 0) = 0 then abs(coalesce(pi.base_grand_total, pi.grand_total, 0)) else 0 end) as gross_sales,
			sum(case when ifnull(pi.is_return, 0) = 1 then abs(coalesce(pi.base_grand_total, pi.grand_total, 0)) else 0 end) as return_amount,
			sum({signed_amount_expr("base_grand_total")}) as net_sales,
			sum({signed_amount_expr("base_paid_amount")}) as paid_amount,
			sum({signed_amount_expr("outstanding_amount")}) as outstanding_amount
		from `tabPOS Invoice` pi
		where {conditions}
		group by pi.posting_date, pi.pos_branch, pi.pos_counter
		order by pi.posting_date desc, pi.pos_branch, pi.pos_counter
		""",
		values,
		as_dict=True,
	)
	return pos_sales_summary_columns(), rows


def pos_transaction_log(filters):
	conditions, values = pos_invoice_conditions(filters, include_cancelled=True)
	rows = frappe.db.sql(
		f"""
		select
			pi.name as invoice_no,
			pi.posting_date,
			pi.posting_time,
			pi.pos_branch as branch,
			pi.pos_counter as counter,
			pi.pos_terminal_id as terminal_id,
			pi.pos_cashier_employee as cashier_employee,
			pi.pos_cashier as cashier,
			pi.customer,
			pi.customer_name,
			pi.docstatus,
			pi.status,
			pi.is_return,
			{signed_amount_expr("base_grand_total")} as grand_total,
			{signed_amount_expr("base_paid_amount")} as paid_amount,
			{signed_amount_expr("outstanding_amount")} as outstanding_amount,
			pi.external_pos_reference,
			pi.pos_bill_no,
			pi.remarks
		from `tabPOS Invoice` pi
		where {conditions}
		order by pi.posting_date desc, pi.posting_time desc, pi.creation desc
		""",
		values,
		as_dict=True,
	)
	payment_modes = get_payment_modes([row.invoice_no for row in rows])
	for row in rows:
		row.transaction_type = _("Return") if row.is_return else _("Sale")
		row.display_status = _("Cancelled") if row.docstatus == 2 else (_("Return") if row.is_return else row.status)
		row.payment_mode = payment_modes.get(row.invoice_no, "")
	return pos_transaction_columns(), rows


def pos_item_wise_sales(filters):
	conditions, values = item_conditions(filters)
	rows = frappe.db.sql(
		f"""
		select
			pii.item_code,
			pii.item_name,
			pii.item_group,
			pii.warehouse,
			sum(case when pi.is_return = 1 then 0 else abs(coalesce(pii.stock_qty, pii.qty, 0)) end) as sold_qty,
			sum(case when pi.is_return = 1 then abs(coalesce(pii.stock_qty, pii.qty, 0)) else 0 end) as return_qty,
			sum({signed_qty_expr()}) as net_qty,
			sum({signed_item_amount_expr()}) as net_amount,
			sum(-coalesce(sle.stock_value_difference, 0)) as cost_amount,
			count(distinct pi.name) as invoice_count
		from `tabPOS Invoice Item` pii
		inner join `tabPOS Invoice` pi on pi.name = pii.parent
		left join (
			select voucher_detail_no, sum(stock_value_difference) as stock_value_difference
			from `tabStock Ledger Entry`
			where voucher_type = 'POS Invoice' and is_cancelled = 0
			group by voucher_detail_no
		) sle on sle.voucher_detail_no = pii.name
		where {conditions}
		group by pii.item_code, pii.item_name, pii.item_group, pii.warehouse
		order by net_amount desc, net_qty desc
		""",
		values,
		as_dict=True,
	)
	add_margin(rows)
	return item_sales_columns(), rows


def pos_category_sales(filters):
	conditions, values = item_conditions(filters)
	rows = frappe.db.sql(
		f"""
		select
			coalesce(pii.item_group, 'No Item Group') as item_group,
			count(distinct pi.name) as invoice_count,
			count(distinct pii.item_code) as item_count,
			sum(case when pi.is_return = 1 then 0 else abs(coalesce(pii.stock_qty, pii.qty, 0)) end) as sold_qty,
			sum(case when pi.is_return = 1 then abs(coalesce(pii.stock_qty, pii.qty, 0)) else 0 end) as return_qty,
			sum({signed_qty_expr()}) as net_qty,
			sum({signed_item_amount_expr()}) as net_amount,
			sum(-coalesce(sle.stock_value_difference, 0)) as cost_amount
		from `tabPOS Invoice Item` pii
		inner join `tabPOS Invoice` pi on pi.name = pii.parent
		left join (
			select voucher_detail_no, sum(stock_value_difference) as stock_value_difference
			from `tabStock Ledger Entry`
			where voucher_type = 'POS Invoice' and is_cancelled = 0
			group by voucher_detail_no
		) sle on sle.voucher_detail_no = pii.name
		where {conditions}
		group by coalesce(pii.item_group, 'No Item Group')
		order by net_amount desc
		""",
		values,
		as_dict=True,
	)
	add_margin(rows)
	return category_sales_columns(), rows


def pos_hourly_sales(filters):
	conditions, values = pos_invoice_conditions(filters)
	rows = frappe.db.sql(
		f"""
		select
			pi.posting_date,
			hour(coalesce(pi.posting_time, '00:00:00')) as hour_of_day,
			pi.pos_branch as branch,
			pi.pos_counter as counter,
			count(case when ifnull(pi.is_return, 0) = 0 then 1 end) as invoice_count,
			count(case when ifnull(pi.is_return, 0) = 1 then 1 end) as return_count,
			sum(case when ifnull(pi.is_return, 0) = 0 then abs(coalesce(pi.base_grand_total, pi.grand_total, 0)) else 0 end) as gross_sales,
			sum(case when ifnull(pi.is_return, 0) = 1 then abs(coalesce(pi.base_grand_total, pi.grand_total, 0)) else 0 end) as return_amount,
			sum({signed_amount_expr("base_grand_total")}) as net_sales
		from `tabPOS Invoice` pi
		where {conditions}
		group by pi.posting_date, hour(coalesce(pi.posting_time, '00:00:00')), pi.pos_branch, pi.pos_counter
		order by pi.posting_date desc, hour_of_day, pi.pos_branch, pi.pos_counter
		""",
		values,
		as_dict=True,
	)
	for row in rows:
		row.hour_label = f"{cint(row.hour_of_day):02d}:00 - {cint(row.hour_of_day):02d}:59"
	return hourly_sales_columns(), rows


def pos_return_report(filters):
	conditions, values = pos_invoice_conditions(filters)
	conditions += " and pi.is_return = 1"
	rows = frappe.db.sql(
		f"""
		select
			pi.name as return_invoice,
			pi.return_against,
			pi.posting_date,
			pi.posting_time,
			pi.pos_branch as branch,
			pi.pos_counter as counter,
			pi.pos_cashier_employee as cashier_employee,
			pi.pos_cashier as cashier,
			pi.customer,
			pi.customer_name,
			abs(coalesce(pi.base_grand_total, pi.grand_total, 0)) as return_amount,
			pi.external_pos_reference,
			pi.pos_original_reference,
			pi.remarks
		from `tabPOS Invoice` pi
		where {conditions}
		order by pi.posting_date desc, pi.posting_time desc, pi.creation desc
		""",
		values,
		as_dict=True,
	)
	return return_report_columns(), rows


def cashier_wise_sales(filters):
	conditions, values = pos_invoice_conditions(filters)
	rows = frappe.db.sql(
		f"""
		select
			pi.pos_cashier_employee as cashier_employee,
			pi.pos_cashier as cashier,
			pi.pos_branch as branch,
			count(case when ifnull(pi.is_return, 0) = 0 then 1 end) as invoice_count,
			count(case when ifnull(pi.is_return, 0) = 1 then 1 end) as return_count,
			sum(case when ifnull(pi.is_return, 0) = 0 then abs(coalesce(pi.base_grand_total, pi.grand_total, 0)) else 0 end) as gross_sales,
			sum(case when ifnull(pi.is_return, 0) = 1 then abs(coalesce(pi.base_grand_total, pi.grand_total, 0)) else 0 end) as return_amount,
			sum({signed_amount_expr("base_grand_total")}) as net_sales
		from `tabPOS Invoice` pi
		where {conditions}
		group by pi.pos_cashier_employee, pi.pos_cashier, pi.pos_branch
		order by net_sales desc
		""",
		values,
		as_dict=True,
	)
	return cashier_sales_columns(), rows


def counter_wise_sales(filters):
	conditions, values = pos_invoice_conditions(filters)
	rows = frappe.db.sql(
		f"""
		select
			pi.pos_branch as branch,
			pi.pos_counter as counter,
			pi.pos_terminal_id as terminal_id,
			count(case when ifnull(pi.is_return, 0) = 0 then 1 end) as invoice_count,
			count(case when ifnull(pi.is_return, 0) = 1 then 1 end) as return_count,
			sum(case when ifnull(pi.is_return, 0) = 0 then abs(coalesce(pi.base_grand_total, pi.grand_total, 0)) else 0 end) as gross_sales,
			sum(case when ifnull(pi.is_return, 0) = 1 then abs(coalesce(pi.base_grand_total, pi.grand_total, 0)) else 0 end) as return_amount,
			sum({signed_amount_expr("base_grand_total")}) as net_sales
		from `tabPOS Invoice` pi
		where {conditions}
		group by pi.pos_branch, pi.pos_counter, pi.pos_terminal_id
		order by net_sales desc
		""",
		values,
		as_dict=True,
	)
	return counter_sales_columns(), rows


def shift_closing_variance(filters):
	conditions = ["shift.opening_time >= %(from_date)s", "shift.opening_time <= date_add(%(to_date)s, interval 1 day)"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}
	if filters.get("branch"):
		conditions.append("shift.branch = %(branch)s")
		values["branch"] = filters.branch
	if filters.get("counter"):
		conditions.append("shift.current_counter = %(counter)s")
		values["counter"] = filters.counter
	if filters.get("cashier_employee"):
		conditions.append("shift.cashier_employee = %(cashier_employee)s")
		values["cashier_employee"] = filters.cashier_employee
	rows = frappe.db.sql(
		f"""
		select
			shift.name as cashier_shift,
			shift.branch,
			shift.current_counter as counter,
			shift.cashier_employee,
			shift.cashier_name,
			shift.status,
			shift.opening_time,
			shift.closing_time,
			shift.opening_amount,
			shift.cash_in_amount,
			shift.cash_out_amount,
			shift.expected_cash,
			shift.closing_amount,
			shift.variance,
			count(pi.name) as invoice_count,
			sum({signed_amount_expr("base_grand_total")}) as net_sales
		from `tabPOS Cashier Shift` shift
		left join `tabPOS Invoice` pi on pi.pos_cashier_shift = shift.name and pi.docstatus = 1
		where {" and ".join(conditions)}
		group by shift.name
		order by shift.opening_time desc
		""",
		values,
		as_dict=True,
	)
	return shift_variance_columns(), rows


def payment_mode_summary(filters):
	conditions, values = pos_invoice_conditions(filters)
	if filters.get("payment_mode"):
		conditions += " and pay.mode_of_payment = %(payment_mode)s"
		values["payment_mode"] = filters.payment_mode
	rows = frappe.db.sql(
		f"""
		select
			pi.posting_date,
			pi.pos_branch as branch,
			pi.pos_counter as counter,
			pi.pos_cashier_employee as cashier_employee,
			pi.pos_cashier as cashier,
			pay.mode_of_payment,
			mop.type as payment_type,
			count(distinct pi.name) as invoice_count,
			sum(case when pi.is_return = 1 then -abs(coalesce(pay.amount, 0)) else abs(coalesce(pay.amount, 0)) end) as paid_amount
		from `tabSales Invoice Payment` pay
		inner join `tabPOS Invoice` pi on pi.name = pay.parent
		left join `tabMode of Payment` mop on mop.name = pay.mode_of_payment
		where {conditions}
		group by pi.posting_date, pi.pos_branch, pi.pos_counter, pi.pos_cashier_employee, pi.pos_cashier, pay.mode_of_payment
		order by pi.posting_date desc, pi.pos_branch, pi.pos_counter, pay.mode_of_payment
		""",
		values,
		as_dict=True,
	)
	return payment_summary_columns(), rows


def pos_discount_report(filters):
	conditions, values = item_conditions(filters)
	rows = frappe.db.sql(
		f"""
		select
			pi.name as invoice_no,
			pi.posting_date,
			pi.pos_branch as branch,
			pi.pos_counter as counter,
			pi.pos_cashier_employee as cashier_employee,
			pi.pos_cashier as cashier,
			pii.item_code,
			pii.item_name,
			pii.qty,
			pii.price_list_rate,
			pii.rate,
			pii.discount_percentage,
			pii.discount_amount,
			pii.distributed_discount_amount,
			pi.discount_amount as invoice_discount_amount,
			pi.additional_discount_percentage,
			coalesce(pii.base_net_amount, pii.net_amount, 0) as net_amount
		from `tabPOS Invoice Item` pii
		inner join `tabPOS Invoice` pi on pi.name = pii.parent
		where {conditions}
			and (
				abs(coalesce(pii.discount_amount, 0)) > 0
				or abs(coalesce(pii.discount_percentage, 0)) > 0
				or abs(coalesce(pii.distributed_discount_amount, 0)) > 0
				or abs(coalesce(pi.discount_amount, 0)) > 0
			)
		order by pi.posting_date desc, pi.posting_time desc, pi.creation desc
		""",
		values,
		as_dict=True,
	)
	return discount_columns(), rows


def pos_price_override_report(filters):
	conditions, values = item_conditions(filters)
	rows = frappe.db.sql(
		f"""
		select
			pi.name as invoice_no,
			pi.posting_date,
			pi.pos_branch as branch,
			pi.pos_counter as counter,
			pi.pos_cashier_employee as cashier_employee,
			pi.pos_cashier as cashier,
			pii.item_code,
			pii.item_name,
			pii.qty,
			pii.price_list_rate,
			pii.rate,
			pii.base_price_list_rate,
			pii.base_rate,
			(coalesce(pii.base_rate, 0) - coalesce(pii.base_price_list_rate, 0)) as rate_difference,
			((coalesce(pii.base_rate, 0) - coalesce(pii.base_price_list_rate, 0)) * abs(coalesce(pii.qty, 0))) as amount_difference,
			pii.discount_percentage,
			pii.discount_amount
		from `tabPOS Invoice Item` pii
		inner join `tabPOS Invoice` pi on pi.name = pii.parent
		where {conditions}
			and coalesce(pii.base_price_list_rate, 0) > 0
			and abs(coalesce(pii.base_rate, 0) - coalesce(pii.base_price_list_rate, 0)) > 0.0001
		order by pi.posting_date desc, pi.posting_time desc, pi.creation desc
		""",
		values,
		as_dict=True,
	)
	return price_override_columns(), rows


def pos_daily_closing_summary(filters):
	columns, rows = pos_sales_summary(filters)
	payments = get_daily_payment_totals(filters)
	variances = get_daily_shift_variances(filters)
	for row in rows:
		key = (row.posting_date, row.branch, row.counter)
		payment = payments.get(key, frappe._dict())
		variance = variances.get(key, frappe._dict())
		row.cash_amount = flt(payment.get("cash_amount"))
		row.non_cash_amount = flt(payment.get("non_cash_amount"))
		row.expected_cash = flt(variance.get("expected_cash"))
		row.closing_amount = flt(variance.get("closing_amount"))
		row.variance = flt(variance.get("variance"))
	return daily_closing_columns(), rows


def get_daily_payment_totals(filters):
	conditions, values = pos_invoice_conditions(filters)
	rows = frappe.db.sql(
		f"""
		select
			pi.posting_date,
			pi.pos_branch as branch,
			pi.pos_counter as counter,
			sum(case when mop.type = 'Cash' then case when pi.is_return = 1 then -abs(coalesce(pay.amount, 0)) else abs(coalesce(pay.amount, 0)) end else 0 end) as cash_amount,
			sum(case when ifnull(mop.type, '') != 'Cash' then case when pi.is_return = 1 then -abs(coalesce(pay.amount, 0)) else abs(coalesce(pay.amount, 0)) end else 0 end) as non_cash_amount
		from `tabSales Invoice Payment` pay
		inner join `tabPOS Invoice` pi on pi.name = pay.parent
		left join `tabMode of Payment` mop on mop.name = pay.mode_of_payment
		where {conditions}
		group by pi.posting_date, pi.pos_branch, pi.pos_counter
		""",
		values,
		as_dict=True,
	)
	return {(row.posting_date, row.branch, row.counter): row for row in rows}


def get_daily_shift_variances(filters):
	conditions = ["date(shift.opening_time) between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}
	if filters.get("branch"):
		conditions.append("shift.branch = %(branch)s")
		values["branch"] = filters.branch
	if filters.get("counter"):
		conditions.append("shift.current_counter = %(counter)s")
		values["counter"] = filters.counter
	rows = frappe.db.sql(
		f"""
		select
			date(shift.opening_time) as posting_date,
			shift.branch,
			shift.current_counter as counter,
			sum(shift.expected_cash) as expected_cash,
			sum(shift.closing_amount) as closing_amount,
			sum(shift.variance) as variance
		from `tabPOS Cashier Shift` shift
		where {" and ".join(conditions)}
		group by date(shift.opening_time), shift.branch, shift.current_counter
		""",
		values,
		as_dict=True,
	)
	return {(row.posting_date, row.branch, row.counter): row for row in rows}


def pos_cash_movement_report(filters):
	conditions = ["date(movement.posting_datetime) between %(from_date)s and %(to_date)s"]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}
	if filters.get("branch"):
		conditions.append("movement.branch = %(branch)s")
		values["branch"] = filters.branch
	if filters.get("counter"):
		conditions.append("movement.counter = %(counter)s")
		values["counter"] = filters.counter
	if filters.get("cashier_employee"):
		conditions.append("movement.cashier_employee = %(cashier_employee)s")
		values["cashier_employee"] = filters.cashier_employee
	if filters.get("movement_type"):
		conditions.append("movement.movement_type = %(movement_type)s")
		values["movement_type"] = filters.movement_type
	rows = frappe.db.sql(
		f"""
		select
			movement.name,
			movement.posting_datetime,
			movement.branch,
			movement.counter,
			movement.counter_code,
			movement.terminal_id,
			movement.cashier_employee,
			movement.cashier_name,
			movement.cashier_shift,
			movement.counter_session,
			movement.movement_type,
			case when movement.movement_type = 'Cash Out' then -abs(movement.amount) else abs(movement.amount) end as signed_amount,
			movement.amount,
			movement.description,
			movement.journal_entry
		from `tabPOS Cash Movement` movement
		where {" and ".join(conditions)}
		order by movement.posting_datetime desc
		""",
		values,
		as_dict=True,
	)
	return cash_movement_columns(), rows


def add_margin(rows):
	for row in rows:
		row.cost_amount = flt(row.cost_amount)
		row.gross_profit = flt(row.net_amount) - row.cost_amount
		row.margin_percent = (row.gross_profit / flt(row.net_amount) * 100) if row.net_amount else 0


def base_filters():
	return [
		{"label": _("From Date"), "fieldname": "from_date", "fieldtype": "Date", "default": "Today", "reqd": 1},
		{"label": _("To Date"), "fieldname": "to_date", "fieldtype": "Date", "default": "Today", "reqd": 1},
	]


def pos_sales_summary_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 140},
		{"label": _("Counter"), "fieldname": "counter", "fieldtype": "Link", "options": "POS Branch Counter", "width": 150},
		{"label": _("Invoice Count"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 110},
		{"label": _("Return Count"), "fieldname": "return_count", "fieldtype": "Int", "width": 110},
		{"label": _("Gross Sales"), "fieldname": "gross_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("Return Amount"), "fieldname": "return_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("Paid Amount"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120},
	]


def pos_transaction_columns():
	return [
		{"label": _("Invoice"), "fieldname": "invoice_no", "fieldtype": "Link", "options": "POS Invoice", "width": 170},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Time"), "fieldname": "posting_time", "fieldtype": "Time", "width": 90},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("Counter"), "fieldname": "counter", "fieldtype": "Link", "options": "POS Branch Counter", "width": 140},
		{"label": _("Cashier Employee"), "fieldname": "cashier_employee", "fieldtype": "Link", "options": "Employee", "width": 150},
		{"label": _("Cashier"), "fieldname": "cashier", "fieldtype": "Data", "width": 140},
		{"label": _("Customer"), "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
		{"label": _("Status"), "fieldname": "display_status", "fieldtype": "Data", "width": 110},
		{"label": _("Type"), "fieldname": "transaction_type", "fieldtype": "Data", "width": 90},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 120},
		{"label": _("Paid"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Payment Mode"), "fieldname": "payment_mode", "fieldtype": "Data", "width": 140},
		{"label": _("POS Bill No"), "fieldname": "pos_bill_no", "fieldtype": "Data", "width": 120},
		{"label": _("External Reference"), "fieldname": "external_pos_reference", "fieldtype": "Data", "width": 170},
	]


def item_sales_columns():
	return [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 130},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 140},
		{"label": _("Sold Qty"), "fieldname": "sold_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Return Qty"), "fieldname": "return_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Net Qty"), "fieldname": "net_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Net Amount"), "fieldname": "net_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Cost Amount"), "fieldname": "cost_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 120},
		{"label": _("Margin %"), "fieldname": "margin_percent", "fieldtype": "Percent", "width": 100},
		{"label": _("Invoice Count"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 110},
	]


def category_sales_columns():
	return [
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 170},
		{"label": _("Item Count"), "fieldname": "item_count", "fieldtype": "Int", "width": 100},
		{"label": _("Invoice Count"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 110},
		{"label": _("Sold Qty"), "fieldname": "sold_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Return Qty"), "fieldname": "return_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Net Qty"), "fieldname": "net_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Net Amount"), "fieldname": "net_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 120},
		{"label": _("Margin %"), "fieldname": "margin_percent", "fieldtype": "Percent", "width": 100},
	]


def hourly_sales_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Hour"), "fieldname": "hour_label", "fieldtype": "Data", "width": 120},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("Counter"), "fieldname": "counter", "fieldtype": "Link", "options": "POS Branch Counter", "width": 140},
		{"label": _("Invoice Count"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 110},
		{"label": _("Return Count"), "fieldname": "return_count", "fieldtype": "Int", "width": 110},
		{"label": _("Gross Sales"), "fieldname": "gross_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("Return Amount"), "fieldname": "return_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 120},
	]


def return_report_columns():
	return [
		{"label": _("Return Invoice"), "fieldname": "return_invoice", "fieldtype": "Link", "options": "POS Invoice", "width": 170},
		{"label": _("Original Invoice"), "fieldname": "return_against", "fieldtype": "Link", "options": "POS Invoice", "width": 170},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Counter"), "fieldname": "counter", "fieldtype": "Link", "options": "POS Branch Counter", "width": 140},
		{"label": _("Cashier Employee"), "fieldname": "cashier_employee", "fieldtype": "Link", "options": "Employee", "width": 150},
		{"label": _("Cashier"), "fieldname": "cashier", "fieldtype": "Data", "width": 140},
		{"label": _("Customer"), "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
		{"label": _("Return Amount"), "fieldname": "return_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Original Reference"), "fieldname": "pos_original_reference", "fieldtype": "Data", "width": 160},
		{"label": _("Remarks / Reason"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
	]


def cashier_sales_columns():
	return [
		{"label": _("Cashier Employee"), "fieldname": "cashier_employee", "fieldtype": "Link", "options": "Employee", "width": 160},
		{"label": _("Cashier"), "fieldname": "cashier", "fieldtype": "Data", "width": 150},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 140},
		{"label": _("Invoice Count"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 110},
		{"label": _("Return Count"), "fieldname": "return_count", "fieldtype": "Int", "width": 110},
		{"label": _("Gross Sales"), "fieldname": "gross_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("Return Amount"), "fieldname": "return_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 120},
	]


def counter_sales_columns():
	return [
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 140},
		{"label": _("Counter"), "fieldname": "counter", "fieldtype": "Link", "options": "POS Branch Counter", "width": 160},
		{"label": _("Terminal ID"), "fieldname": "terminal_id", "fieldtype": "Data", "width": 120},
		{"label": _("Invoice Count"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 110},
		{"label": _("Return Count"), "fieldname": "return_count", "fieldtype": "Int", "width": 110},
		{"label": _("Gross Sales"), "fieldname": "gross_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("Return Amount"), "fieldname": "return_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 120},
	]


def shift_variance_columns():
	return [
		{"label": _("Shift"), "fieldname": "cashier_shift", "fieldtype": "Link", "options": "POS Cashier Shift", "width": 170},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("Counter"), "fieldname": "counter", "fieldtype": "Link", "options": "POS Branch Counter", "width": 140},
		{"label": _("Cashier Employee"), "fieldname": "cashier_employee", "fieldtype": "Link", "options": "Employee", "width": 150},
		{"label": _("Cashier Name"), "fieldname": "cashier_name", "fieldtype": "Data", "width": 150},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Opening Time"), "fieldname": "opening_time", "fieldtype": "Datetime", "width": 160},
		{"label": _("Closing Time"), "fieldname": "closing_time", "fieldtype": "Datetime", "width": 160},
		{"label": _("Opening Amount"), "fieldname": "opening_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Cash In"), "fieldname": "cash_in_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Cash Out"), "fieldname": "cash_out_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Expected Cash"), "fieldname": "expected_cash", "fieldtype": "Currency", "width": 130},
		{"label": _("Closing Amount"), "fieldname": "closing_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Variance"), "fieldname": "variance", "fieldtype": "Currency", "width": 120},
		{"label": _("Invoice Count"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 110},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 120},
	]


def payment_summary_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("Counter"), "fieldname": "counter", "fieldtype": "Link", "options": "POS Branch Counter", "width": 140},
		{"label": _("Cashier Employee"), "fieldname": "cashier_employee", "fieldtype": "Link", "options": "Employee", "width": 150},
		{"label": _("Cashier"), "fieldname": "cashier", "fieldtype": "Data", "width": 140},
		{"label": _("Mode of Payment"), "fieldname": "mode_of_payment", "fieldtype": "Link", "options": "Mode of Payment", "width": 150},
		{"label": _("Payment Type"), "fieldname": "payment_type", "fieldtype": "Data", "width": 110},
		{"label": _("Invoice Count"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 110},
		{"label": _("Paid Amount"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 120},
	]


def discount_columns():
	return [
		{"label": _("Invoice"), "fieldname": "invoice_no", "fieldtype": "Link", "options": "POS Invoice", "width": 170},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Counter"), "fieldname": "counter", "fieldtype": "Link", "options": "POS Branch Counter", "width": 140},
		{"label": _("Cashier Employee"), "fieldname": "cashier_employee", "fieldtype": "Link", "options": "Employee", "width": 150},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 170},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("Price List Rate"), "fieldname": "price_list_rate", "fieldtype": "Currency", "width": 120},
		{"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Discount %"), "fieldname": "discount_percentage", "fieldtype": "Percent", "width": 100},
		{"label": _("Discount Amount"), "fieldname": "discount_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Distributed Discount"), "fieldname": "distributed_discount_amount", "fieldtype": "Currency", "width": 140},
		{"label": _("Invoice Discount"), "fieldname": "invoice_discount_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Net Amount"), "fieldname": "net_amount", "fieldtype": "Currency", "width": 120},
	]


def price_override_columns():
	return [
		{"label": _("Invoice"), "fieldname": "invoice_no", "fieldtype": "Link", "options": "POS Invoice", "width": 170},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Counter"), "fieldname": "counter", "fieldtype": "Link", "options": "POS Branch Counter", "width": 140},
		{"label": _("Cashier Employee"), "fieldname": "cashier_employee", "fieldtype": "Link", "options": "Employee", "width": 150},
		{"label": _("Cashier"), "fieldname": "cashier", "fieldtype": "Data", "width": 140},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 170},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("Price List Rate"), "fieldname": "price_list_rate", "fieldtype": "Currency", "width": 120},
		{"label": _("Actual Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 110},
		{"label": _("Rate Difference"), "fieldname": "rate_difference", "fieldtype": "Currency", "width": 120},
		{"label": _("Amount Difference"), "fieldname": "amount_difference", "fieldtype": "Currency", "width": 140},
		{"label": _("Discount %"), "fieldname": "discount_percentage", "fieldtype": "Percent", "width": 100},
	]


def daily_closing_columns():
	columns = pos_sales_summary_columns()
	columns.extend(
		[
			{"label": _("Cash Amount"), "fieldname": "cash_amount", "fieldtype": "Currency", "width": 120},
			{"label": _("Card/Bank Amount"), "fieldname": "non_cash_amount", "fieldtype": "Currency", "width": 130},
			{"label": _("Expected Cash"), "fieldname": "expected_cash", "fieldtype": "Currency", "width": 130},
			{"label": _("Closing Amount"), "fieldname": "closing_amount", "fieldtype": "Currency", "width": 130},
			{"label": _("Variance"), "fieldname": "variance", "fieldtype": "Currency", "width": 120},
		]
	)
	return columns


def cash_movement_columns():
	return [
		{"label": _("Movement"), "fieldname": "name", "fieldtype": "Link", "options": "POS Cash Movement", "width": 170},
		{"label": _("Posting Datetime"), "fieldname": "posting_datetime", "fieldtype": "Datetime", "width": 160},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("Counter"), "fieldname": "counter", "fieldtype": "Link", "options": "POS Branch Counter", "width": 140},
		{"label": _("Counter Code"), "fieldname": "counter_code", "fieldtype": "Data", "width": 110},
		{"label": _("Terminal ID"), "fieldname": "terminal_id", "fieldtype": "Data", "width": 120},
		{"label": _("Cashier Employee"), "fieldname": "cashier_employee", "fieldtype": "Link", "options": "Employee", "width": 150},
		{"label": _("Cashier Name"), "fieldname": "cashier_name", "fieldtype": "Data", "width": 150},
		{"label": _("Cashier Shift"), "fieldname": "cashier_shift", "fieldtype": "Link", "options": "POS Cashier Shift", "width": 160},
		{"label": _("Counter Session"), "fieldname": "counter_session", "fieldtype": "Link", "options": "POS Counter Session", "width": 160},
		{"label": _("Movement Type"), "fieldname": "movement_type", "fieldtype": "Data", "width": 120},
		{"label": _("Signed Amount"), "fieldname": "signed_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 220},
		{"label": _("Journal Entry"), "fieldname": "journal_entry", "fieldtype": "Link", "options": "Journal Entry", "width": 160},
	]


REPORT_EXECUTORS = {
	"POS Sales Summary": pos_sales_summary,
	"POS Transaction Log": pos_transaction_log,
	"POS Item-wise Sales": pos_item_wise_sales,
	"POS Category Item Group Sales": pos_category_sales,
	"POS Hourly Sales": pos_hourly_sales,
	"POS Return Report": pos_return_report,
	"Cashier Wise Sales": cashier_wise_sales,
	"Counter Wise Sales": counter_wise_sales,
	"Shift Closing Variance": shift_closing_variance,
	"POS Payment Mode Summary": payment_mode_summary,
	"POS Discount Report": pos_discount_report,
	"POS Price Override Report": pos_price_override_report,
	"POS Daily Closing Summary": pos_daily_closing_summary,
	"POS Cash Movement Report": pos_cash_movement_report,
}
