import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	rows = get_rows(filters)
	rows = apply_filters(rows, filters)
	rows.sort(key=lambda row: (flt(row.tax_rate), row.tax_type))

	if rows:
		rows.append(make_grand_total_row(rows))

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

	grouped = {}
	for row in get_sales_tax_rows(filters, tax_accounts):
		add_tax_row(grouped, row, "sale_tax")

	for row in get_purchase_tax_rows(filters, tax_accounts):
		add_tax_row(grouped, row, "purchase_tax")

	rows = []
	for row in grouped.values():
		row.sale_tax = flt(row.sale_tax)
		row.purchase_tax = flt(row.purchase_tax)
		row.tax_payable = flt(row.sale_tax) - flt(row.purchase_tax)
		row.tax_percent = flt(row.tax_rate)
		rows.append(row)

	return rows


def get_sales_tax_rows(filters, tax_accounts):
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

	return frappe.db.sql(
		f"""
		select
			coalesce(stc.account_head, '') as tax_account,
			coalesce(stc.rate, 0) as tax_rate,
			sum(
				case when si.is_return = 1 then -1 else 1 end
				* abs(coalesce(stc.base_tax_amount_after_discount_amount, stc.base_tax_amount, stc.tax_amount, 0))
			) as tax_amount
		from `tabSales Invoice` si
		left join `tabSales Taxes and Charges` stc
			on stc.parent = si.name and stc.account_head in %(tax_accounts)s
		where {" and ".join(conditions)}
		group by coalesce(stc.account_head, ''), coalesce(stc.rate, 0)
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


def get_purchase_tax_rows(filters, tax_accounts):
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

	return frappe.db.sql(
		f"""
		select
			coalesce(ptc.account_head, '') as tax_account,
			coalesce(ptc.rate, 0) as tax_rate,
			sum(
				case when pi.is_return = 1 then -1 else 1 end
				* abs(coalesce(ptc.base_tax_amount_after_discount_amount, ptc.base_tax_amount, ptc.tax_amount, 0))
			) as tax_amount
		from `tabPurchase Invoice` pi
		left join `tabPurchase Taxes and Charges` ptc
			on ptc.parent = pi.name and ptc.account_head in %(tax_accounts)s
		where {" and ".join(conditions)}
		group by coalesce(ptc.account_head, ''), coalesce(ptc.rate, 0)
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


def add_tax_row(grouped, source_row, amount_field):
	tax_rate = get_tax_rate(source_row)
	tax_type = get_tax_type(tax_rate, source_row.tax_amount)
	key = (tax_type, flt(tax_rate))

	if key not in grouped:
		grouped[key] = frappe._dict(
			{
				"tax_type": tax_type,
				"tax_rate": flt(tax_rate),
				"sale_tax": 0,
				"purchase_tax": 0,
			}
		)

	grouped[key][amount_field] = flt(grouped[key].get(amount_field)) + flt(source_row.tax_amount)


def get_tax_rate(row):
	if flt(row.tax_rate):
		return flt(row.tax_rate)
	account_rate = get_rate_from_tax_account(row.tax_account)
	if account_rate is not None:
		return account_rate
	return 0


def get_rate_from_tax_account(tax_account):
	if not tax_account:
		return None

	match = re.search(r"(\d+(?:\.\d+)?)\s*%", tax_account)
	if match:
		return flt(match.group(1))

	return None


def get_tax_type(tax_rate, tax_amount):
	if not flt(tax_rate) and not flt(tax_amount):
		return _("Zero Rate")
	return _("Standard Rate")


def apply_filters(rows, filters):
	filtered = []
	for row in rows:
		if not cint(filters.get("show_zero_tax_rows", 1)) and not (flt(row.sale_tax) or flt(row.purchase_tax)):
			continue
		filtered.append(row)
	return filtered


def make_grand_total_row(rows):
	sale_tax = sum(flt(row.sale_tax) for row in rows)
	purchase_tax = sum(flt(row.purchase_tax) for row in rows)
	return frappe._dict(
		{
			"tax_type": _("Grand Total"),
			"sale_tax": sale_tax,
			"purchase_tax": purchase_tax,
			"tax_payable": sale_tax - purchase_tax,
			"is_group": 1,
		}
	)


def get_columns():
	return [
		{"label": _("Tax Type"), "fieldname": "tax_type", "fieldtype": "Data", "width": 170},
		{"label": _("Tax (%)"), "fieldname": "tax_percent", "fieldtype": "Percent", "width": 100},
		{"label": _("Sale Tax"), "fieldname": "sale_tax", "fieldtype": "Currency", "width": 130},
		{"label": _("Purchase Tax"), "fieldname": "purchase_tax", "fieldtype": "Currency", "width": 130},
		{"label": _("Tax Payable"), "fieldname": "tax_payable", "fieldtype": "Currency", "width": 135},
	]
