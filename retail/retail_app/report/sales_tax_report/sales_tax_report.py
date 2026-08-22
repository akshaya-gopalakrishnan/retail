import frappe
from frappe import _
from frappe.utils import cint, flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	rows = get_sales_rows(filters)
	rows = apply_filters(rows, filters)
	rows.sort(key=lambda row: (row.transaction_type, getdate(row.invoice_date), row.voucher_no or ""))
	add_reference_numbers(rows)

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


def get_sales_rows(filters):
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

	rows = frappe.db.sql(
		f"""
		select
			si.name as voucher_no,
			si.name as invoice_no,
			si.posting_date as invoice_date,
			si.customer,
			coalesce(si.customer_name, si.customer) as customer_name,
			si.tax_id as customer_tax_id,
			coalesce(
				si.cost_center,
				(select max(sii.cost_center) from `tabSales Invoice Item` sii where sii.parent = si.name),
				(select max(stc.cost_center) from `tabSales Taxes and Charges` stc where stc.parent = si.name)
			) as cost_center,
			si.is_pos,
			si.is_return,
			abs(si.base_net_total) as total,
			abs(coalesce(si.base_discount_amount, 0)) as discount_amount,
			abs(coalesce((
				select sum(coalesce(stc.base_tax_amount_after_discount_amount, stc.base_tax_amount, stc.tax_amount, 0))
				from `tabSales Taxes and Charges` stc
				where stc.parent = si.name and stc.account_head in %(tax_accounts)s
			), 0)) as tax_amount,
			abs(si.base_grand_total) as net_amount,
			(
				select group_concat(distinct stc.account_head order by stc.account_head separator ', ')
				from `tabSales Taxes and Charges` stc
				where stc.parent = si.name and stc.account_head in %(tax_accounts)s
			) as tax_account
		from `tabSales Invoice` si
		where {" and ".join(conditions)}
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

	for row in rows:
		sign = -1 if row.is_return else 1
		row.transaction_type = get_transaction_type(row)
		row.total = sign * flt(row.total)
		row.discount_amount = sign * flt(row.discount_amount)
		row.taxable_amount = flt(row.total) if flt(row.tax_amount) else 0
		row.non_taxable_amount = 0 if flt(row.tax_amount) else flt(row.total)
		row.output_tax = sign * flt(row.tax_amount)
		row.net_amount = sign * flt(row.net_amount)
		row.doctype = "Sales Invoice"

	return rows


def get_transaction_type(row):
	if row.is_pos and row.is_return:
		return _("POS Sales Return")
	if row.is_pos:
		return _("POS Sales")
	if row.is_return:
		return _("Sales Return")
	return _("Sales Invoice")


def apply_filters(rows, filters):
	filtered = []
	for row in rows:
		if filters.get("transaction_type") and row.transaction_type != filters.transaction_type:
			continue
		if filters.get("customer") and row.customer != filters.customer:
			continue
		if filters.get("tax_account") and filters.tax_account not in (row.tax_account or ""):
			continue
		if not cint(filters.get("show_zero_tax_rows", 1)) and not flt(row.output_tax):
			continue
		filtered.append(row)
	return filtered


def add_reference_numbers(rows):
	for index, row in enumerate(rows, 1):
		row.ref_no = index


def add_summary_rows(rows):
	grouped_rows = []
	current_type = None
	totals = frappe._dict()
	grand_totals = frappe._dict()

	for row in rows:
		if current_type and row.transaction_type != current_type:
			grouped_rows.append(make_total_row(current_type, totals))
			totals = frappe._dict()

		current_type = row.transaction_type
		grouped_rows.append(row)
		add_to_totals(totals, row)
		add_to_totals(grand_totals, row)

	if current_type:
		grouped_rows.append(make_total_row(current_type, totals))
		grouped_rows.append(make_total_row(_("Grand Total"), grand_totals, is_grand_total=True))

	return grouped_rows


def add_to_totals(totals, row):
	for field in (
		"total",
		"discount_amount",
		"taxable_amount",
		"non_taxable_amount",
		"output_tax",
		"net_amount",
	):
		totals[field] = flt(totals.get(field)) + flt(row.get(field))


def make_total_row(label, totals, is_grand_total=False):
	return frappe._dict(
		{
			"transaction_type": _("{0} Total").format(label) if not is_grand_total else label,
			"total": totals.get("total"),
			"discount_amount": totals.get("discount_amount"),
			"taxable_amount": totals.get("taxable_amount"),
			"non_taxable_amount": totals.get("non_taxable_amount"),
			"output_tax": totals.get("output_tax"),
			"net_amount": totals.get("net_amount"),
			"is_group": 1,
		}
	)


def get_columns():
	return [
		{
			"label": _("Voucher No"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "doctype",
			"width": 180,
		},
		{"label": _("Invoice No"), "fieldname": "invoice_no", "fieldtype": "Data", "width": 120},
		{"label": _("Invoice Date"), "fieldname": "invoice_date", "fieldtype": "Date", "width": 110},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 220},
		{"label": _("Customer TRN"), "fieldname": "customer_tax_id", "fieldtype": "Data", "width": 130},
		{"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 140},
		{"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "width": 120},
		{"label": _("Discount"), "fieldname": "discount_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Taxable Amount"), "fieldname": "taxable_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Non Taxable Amount"), "fieldname": "non_taxable_amount", "fieldtype": "Currency", "width": 150},
		{"label": _("Tax Amount"), "fieldname": "output_tax", "fieldtype": "Currency", "width": 115},
		{"label": _("Net Amount"), "fieldname": "net_amount", "fieldtype": "Currency", "width": 125},
		{"label": _("Transaction Type"), "fieldname": "transaction_type", "fieldtype": "Data", "width": 200},
		{"label": _("Tax Account"), "fieldname": "tax_account", "fieldtype": "Data", "width": 120},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 170},
		{"label": _("Doctype"), "fieldname": "doctype", "fieldtype": "Data", "width": 120, "hidden": 1},
	]
