import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	rows = get_rows(filters)
	rows = apply_filters(rows, filters)
	rows.sort(key=lambda row: (row.cost_center or "", getdate(row.posting_date), flt(row.tax_rate), row.tax_type))

	if cint(filters.get("show_summary_rows", 1)):
		rows = add_summary_rows(rows)

	return get_columns(), rows


def validate_filters(filters):
	if not filters.get("company"):
		frappe.throw(_("Company is required"))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required"))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date"))


def get_tax_accounts(company):
	accounts = frappe.get_all("UAE VAT Account", filters={"parent": company}, pluck="account")
	if accounts:
		return accounts

	return frappe.get_all(
		"Account",
		filters={"company": company, "account_type": "Tax", "is_group": 0},
		pluck="name",
	)


def get_rows(filters):
	tax_accounts = get_tax_accounts(filters.company)
	if not tax_accounts:
		tax_accounts = ["__no_tax_account__"]

	conditions = [
		"si.docstatus = 1",
		"si.company = %(company)s",
		"si.posting_date between %(from_date)s and %(to_date)s",
	]

	if filters.get("cost_center"):
		conditions.append(
			"""(
				si.cost_center = %(cost_center)s
				or exists (
					select 1 from `tabSales Invoice Item` sii
					where sii.parent = si.name and sii.cost_center = %(cost_center)s
				)
				or exists (
					select 1 from `tabSales Taxes and Charges` stc
					where stc.parent = si.name and stc.cost_center = %(cost_center)s
				)
			)"""
		)

	raw_rows = frappe.db.sql(
		f"""
		select
			coalesce(
				si.cost_center,
				(select max(sii.cost_center) from `tabSales Invoice Item` sii where sii.parent = si.name),
				(select max(stc2.cost_center) from `tabSales Taxes and Charges` stc2 where stc2.parent = si.name)
			) as cost_center,
			si.posting_date,
			coalesce(stc.account_head, '') as tax_account,
			coalesce(stc.rate, 0) as tax_rate,
			sum(
				case when si.is_return = 1 then -1 else 1 end
				* abs(si.base_net_total)
			) as sales_amount,
			sum(
				case when si.is_return = 1 then -1 else 1 end
				* abs(coalesce(stc.base_tax_amount_after_discount_amount, stc.base_tax_amount, stc.tax_amount, 0))
			) as tax_amount
		from `tabSales Invoice` si
		left join `tabSales Taxes and Charges` stc
			on stc.parent = si.name and stc.account_head in %(tax_accounts)s
		where {" and ".join(conditions)}
		group by cost_center, si.posting_date, coalesce(stc.account_head, ''), coalesce(stc.rate, 0)
		""",
		{
			"company": filters.company,
			"from_date": filters.from_date,
			"to_date": filters.to_date,
			"cost_center": filters.get("cost_center"),
			"tax_accounts": tuple(tax_accounts),
		},
		as_dict=True,
	)

	for row in raw_rows:
		row.sales_amount = flt(row.sales_amount)
		row.tax_amount = flt(row.tax_amount)
		row.tax_rate = get_tax_rate(row)
		row.tax_type = get_tax_type(row)
		row.tax_percent = flt(row.tax_rate)

	return raw_rows


def get_tax_rate(row):
	if flt(row.tax_rate):
		return flt(row.tax_rate)
	account_rate = get_rate_from_tax_account(row.tax_account)
	if account_rate is not None:
		return account_rate
	if flt(row.tax_amount) and flt(row.sales_amount):
		return flt(flt(row.tax_amount) / flt(row.sales_amount) * 100, 2)
	return 0


def get_rate_from_tax_account(tax_account):
	if not tax_account:
		return None

	match = re.search(r"(\d+(?:\.\d+)?)\s*%", tax_account)
	if match:
		return flt(match.group(1))

	return None


def get_tax_type(row):
	if not flt(row.tax_rate) and not flt(row.tax_amount):
		return _("Zero Rate")
	return _("Standard Rate")


def apply_filters(rows, filters):
	filtered = []
	for row in rows:
		if filters.get("tax_account") and row.tax_account != filters.tax_account:
			continue
		if not cint(filters.get("show_zero_tax_rows", 1)) and not flt(row.tax_amount):
			continue
		filtered.append(row)
	return filtered


def add_summary_rows(rows):
	grouped_rows = []
	current_cost_center = None
	cost_center_totals = frappe._dict()
	grand_totals = frappe._dict()

	for row in rows:
		if current_cost_center and row.cost_center != current_cost_center:
			grouped_rows.append(make_total_row(_("{0} Total").format(current_cost_center), cost_center_totals))
			cost_center_totals = frappe._dict()

		current_cost_center = row.cost_center
		grouped_rows.append(row)
		add_to_totals(cost_center_totals, row)
		add_to_totals(grand_totals, row)

	if current_cost_center:
		grouped_rows.append(make_total_row(_("{0} Total").format(current_cost_center), cost_center_totals))
		grouped_rows.append(make_total_row(_("Grand Total"), grand_totals))

	return grouped_rows


def add_to_totals(totals, row):
	for field in ("sales_amount", "tax_amount"):
		totals[field] = flt(totals.get(field)) + flt(row.get(field))


def make_total_row(label, totals):
	return frappe._dict(
		{
			"cost_center": label,
			"sales_amount": totals.get("sales_amount"),
			"tax_amount": totals.get("tax_amount"),
			"is_group": 1,
		}
	)


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 200},
		{"label": _("Tax Type"), "fieldname": "tax_type", "fieldtype": "Data", "width": 200},
		{"label": _("Tax (%)"), "fieldname": "tax_percent", "fieldtype": "Percent", "width": 150},
		{"label": _("Sales Amount"), "fieldname": "sales_amount", "fieldtype": "Currency", "width": 200},
		{"label": _("Tax Amount"), "fieldname": "tax_amount", "fieldtype": "Currency", "width": 200},
		{"label": _("Tax Account"), "fieldname": "tax_account", "fieldtype": "Data", "width": 220},
		{"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 200},

	]
