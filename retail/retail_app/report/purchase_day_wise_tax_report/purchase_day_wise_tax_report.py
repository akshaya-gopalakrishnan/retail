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
		"pi.docstatus = 1",
		"pi.company = %(company)s",
		"pi.posting_date between %(from_date)s and %(to_date)s",
	]

	if filters.get("cost_center"):
		conditions.append(
			"""(
				pi.cost_center = %(cost_center)s
				or exists (
					select 1 from `tabPurchase Invoice Item` pii
					where pii.parent = pi.name and pii.cost_center = %(cost_center)s
				)
				or exists (
					select 1 from `tabPurchase Taxes and Charges` ptc
					where ptc.parent = pi.name and ptc.cost_center = %(cost_center)s
				)
			)"""
		)

	raw_rows = frappe.db.sql(
		f"""
		select
			coalesce(
				pi.cost_center,
				(select max(pii.cost_center) from `tabPurchase Invoice Item` pii where pii.parent = pi.name),
				(select max(ptc2.cost_center) from `tabPurchase Taxes and Charges` ptc2 where ptc2.parent = pi.name)
			) as cost_center,
			pi.posting_date,
			coalesce(ptc.account_head, '') as tax_account,
			coalesce(ptc.rate, 0) as tax_rate,
			sum(
				case when pi.is_return = 1 then -1 else 1 end
				* abs(pi.base_net_total)
			) as purchase_amount,
			sum(
				case when pi.is_return = 1 then -1 else 1 end
				* abs(coalesce(ptc.base_tax_amount_after_discount_amount, ptc.base_tax_amount, ptc.tax_amount, 0))
			) as tax_amount
		from `tabPurchase Invoice` pi
		left join `tabPurchase Taxes and Charges` ptc
			on ptc.parent = pi.name and ptc.account_head in %(tax_accounts)s
		where {" and ".join(conditions)}
		group by cost_center, pi.posting_date, coalesce(ptc.account_head, ''), coalesce(ptc.rate, 0)
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
		row.purchase_amount = flt(row.purchase_amount)
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
	if flt(row.tax_amount) and flt(row.purchase_amount):
		return flt(flt(row.tax_amount) / flt(row.purchase_amount) * 100, 2)
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
	for field in ("purchase_amount", "tax_amount"):
		totals[field] = flt(totals.get(field)) + flt(row.get(field))


def make_total_row(label, totals):
	return frappe._dict(
		{
			"cost_center": label,
			"purchase_amount": totals.get("purchase_amount"),
			"tax_amount": totals.get("tax_amount"),
			"is_group": 1,
		}
	)


def get_columns():
	return [
		{"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 180},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 115},
		{"label": _("Tax Type"), "fieldname": "tax_type", "fieldtype": "Data", "width": 150},
		{"label": _("Tax (%)"), "fieldname": "tax_percent", "fieldtype": "Percent", "width": 100},
		{"label": _("Purchase Amount"), "fieldname": "purchase_amount", "fieldtype": "Currency", "width": 155},
		{"label": _("Tax Amount"), "fieldname": "tax_amount", "fieldtype": "Currency", "width": 135},
		{"label": _("Tax Account"), "fieldname": "tax_account", "fieldtype": "Data", "width": 220},
	]
