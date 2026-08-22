import frappe
from frappe import _
from frappe.utils import cint, flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	rows = get_purchase_rows(filters)
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


def get_purchase_rows(filters):
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

	rows = frappe.db.sql(
		f"""
		select
			pi.name as voucher_no,
			coalesce(nullif(pi.bill_no, ''), pi.name) as invoice_no,
			pi.posting_date as invoice_date,
			pi.supplier,
			coalesce(pi.supplier_name, pi.supplier) as supplier_name,
			pi.tax_id as supplier_tax_id,
			coalesce(
				pi.cost_center,
				(select max(pii.cost_center) from `tabPurchase Invoice Item` pii where pii.parent = pi.name),
				(select max(ptc.cost_center) from `tabPurchase Taxes and Charges` ptc where ptc.parent = pi.name)
			) as cost_center,
			pi.is_return,
			abs(pi.base_net_total) as total,
			abs(coalesce(pi.base_discount_amount, 0)) as discount_amount,
			abs(coalesce((
				select sum(coalesce(ptc.base_tax_amount_after_discount_amount, ptc.base_tax_amount, ptc.tax_amount, 0))
				from `tabPurchase Taxes and Charges` ptc
				where ptc.parent = pi.name and ptc.account_head in %(tax_accounts)s
			), 0)) as tax_amount,
			abs(pi.base_grand_total) as net_amount,
			(
				select group_concat(distinct ptc.account_head order by ptc.account_head separator ', ')
				from `tabPurchase Taxes and Charges` ptc
				where ptc.parent = pi.name and ptc.account_head in %(tax_accounts)s
			) as tax_account,
			(
				select count(*)
				from `tabPurchase Invoice Item` pii
				inner join `tabItem` item on item.name = pii.item_code
				where pii.parent = pi.name and item.is_stock_item = 1
			) as stock_item_count
		from `tabPurchase Invoice` pi
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
		row.taxable_amount = sign * flt(row.total) if flt(row.tax_amount) else 0
		row.non_taxable_amount = 0 if flt(row.tax_amount) else sign * flt(row.total)
		row.input_tax = sign * flt(row.tax_amount)
		row.net_amount = sign * flt(row.net_amount)
		row.doctype = "Purchase Invoice"

	return rows


def get_transaction_type(row):
	if row.is_return:
		return _("Purchase Return")
	return _("Purchase Invoice") if flt(row.stock_item_count) else _("Expense")


def apply_filters(rows, filters):
	filtered = []
	for row in rows:
		if filters.get("transaction_type") and row.transaction_type != filters.transaction_type:
			continue
		if filters.get("supplier") and row.supplier != filters.supplier:
			continue
		if filters.get("tax_account") and filters.tax_account not in (row.tax_account or ""):
			continue
		if not cint(filters.get("show_zero_tax_rows", 1)) and not flt(row.input_tax):
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
		"input_tax",
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
			"input_tax": totals.get("input_tax"),
			"net_amount": totals.get("net_amount"),
			"is_group": 1,
		}
	)


def get_columns():
	return [
		{"label": _("Transaction Type"), "fieldname": "transaction_type", "fieldtype": "Data", "width": 150},
		{
			"label": _("Voucher No"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "doctype",
			"width": 180,
		},
		{"label": _("Invoice No"), "fieldname": "invoice_no", "fieldtype": "Data", "width": 140},
		{"label": _("Invoice Date"), "fieldname": "invoice_date", "fieldtype": "Date", "width": 110},
		{"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 220},
		{"label": _("Supplier Tax ID"), "fieldname": "supplier_tax_id", "fieldtype": "Data", "width": 140},
		{"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 170},
		{"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "width": 120},
		{"label": _("Discount"), "fieldname": "discount_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Taxable Amount"), "fieldname": "taxable_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Non Taxable Amount"), "fieldname": "non_taxable_amount", "fieldtype": "Currency", "width": 150},
		{"label": _("Input Tax"), "fieldname": "input_tax", "fieldtype": "Currency", "width": 115},
		{"label": _("Net Amount"), "fieldname": "net_amount", "fieldtype": "Currency", "width": 125},
		{"label": _("Tax Account"), "fieldname": "tax_account", "fieldtype": "Data", "width": 220},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 170},
		{"label": _("Doctype"), "fieldname": "doctype", "fieldtype": "Data", "width": 120, "hidden": 1},
	]
