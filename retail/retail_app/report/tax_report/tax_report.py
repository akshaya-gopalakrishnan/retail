import frappe
from frappe import _
from frappe.utils import cint, flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	rows = []
	rows.extend(get_sales_invoice_rows(filters))
	rows.extend(get_purchase_invoice_rows(filters))
	rows.extend(get_journal_entry_rows(filters))

	rows = apply_common_filters(rows, filters)
	rows.sort(key=lambda row: (row.transaction_type, getdate(row.date), row.voucher_no or ""))
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


def get_uae_vat_accounts(company):
	accounts = frappe.get_all("UAE VAT Account", filters={"parent": company}, pluck="account")
	if accounts:
		return accounts

	return frappe.get_all(
		"Account",
		filters={"company": company, "account_type": "Tax", "is_group": 0},
		pluck="name",
	)


def get_sales_invoice_rows(filters):
	tax_accounts = get_uae_vat_accounts(filters.company)
	if not tax_accounts:
		return []

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
			si.posting_date as date,
			si.customer as party,
			coalesce(si.customer_name, si.customer) as party_name,
			si.tax_id as trn,
			coalesce(
				si.cost_center,
				(select max(sii.cost_center) from `tabSales Invoice Item` sii where sii.parent = si.name),
				(select max(stc.cost_center) from `tabSales Taxes and Charges` stc where stc.parent = si.name)
			) as cost_center,
			si.is_pos,
			si.is_return,
			abs(si.base_net_total) as net_total,
			abs(coalesce(si.base_discount_amount, 0)) as discount_amount,
			abs((
				select sum(coalesce(stc.base_tax_amount_after_discount_amount, stc.base_tax_amount, stc.tax_amount, 0))
				from `tabSales Taxes and Charges` stc
				where stc.parent = si.name and stc.account_head in %(tax_accounts)s
			)) as vat_amount,
			abs(si.base_grand_total) as gross_amount,
			(
				select group_concat(distinct stc.account_head order by stc.account_head separator ', ')
				from `tabSales Taxes and Charges` stc
				where stc.parent = si.name and stc.account_head in %(tax_accounts)s
			) as tax_account
		from `tabSales Invoice` si
		where {" and ".join(conditions)}
			and exists (
				select 1 from `tabSales Taxes and Charges` stc
				where stc.parent = si.name and stc.account_head in %(tax_accounts)s
			)
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

	data = []
	for row in rows:
		is_return = bool(row.is_return)
		row.transaction_type = get_sales_transaction_type(row)
		sign = -1 if is_return else 1
		row.total = sign * flt(row.net_total)
		row.discount_amount = sign * flt(row.discount_amount)
		row.taxable_amount = sign * flt(row.net_total) if flt(row.vat_amount) else 0
		row.non_taxable_amount = 0 if flt(row.vat_amount) else sign * flt(row.net_total)
		row.output_tax = sign * flt(row.vat_amount)
		row.input_tax = 0
		row.net_amount = sign * flt(row.gross_amount)
		row.tax_payable = None
		row.party_type = "Customer"
		row.doctype = "Sales Invoice"
		data.append(row)

	return data


def get_sales_transaction_type(row):
	if row.is_pos and row.is_return:
		return _("POS Sales Return")
	if row.is_pos:
		return _("POS Sales")
	if row.is_return:
		return _("Sales Return")
	return _("Sales Invoice")


def get_purchase_invoice_rows(filters):
	tax_accounts = get_uae_vat_accounts(filters.company)
	if not tax_accounts:
		return []

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
			pi.posting_date as date,
			pi.supplier as party,
			coalesce(pi.supplier_name, pi.supplier) as party_name,
			pi.tax_id as trn,
			coalesce(
				pi.cost_center,
				(select max(pii.cost_center) from `tabPurchase Invoice Item` pii where pii.parent = pi.name),
				(select max(ptc.cost_center) from `tabPurchase Taxes and Charges` ptc where ptc.parent = pi.name)
			) as cost_center,
			pi.is_return,
			abs(pi.base_net_total) as net_total,
			abs(coalesce(pi.base_discount_amount, 0)) as discount_amount,
			abs((
				select sum(coalesce(ptc.base_tax_amount_after_discount_amount, ptc.base_tax_amount, ptc.tax_amount, 0))
				from `tabPurchase Taxes and Charges` ptc
				where ptc.parent = pi.name and ptc.account_head in %(tax_accounts)s
			)) as vat_amount,
			abs(pi.base_grand_total) as gross_amount,
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
			and exists (
				select 1 from `tabPurchase Taxes and Charges` ptc
				where ptc.parent = pi.name and ptc.account_head in %(tax_accounts)s
			)
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

	data = []
	for row in rows:
		is_return = bool(row.is_return)
		row.transaction_type = _("Purchase Return") if is_return else get_purchase_transaction_type(row)
		sign = -1 if is_return else 1
		row.total = sign * flt(row.net_total)
		row.discount_amount = sign * flt(row.discount_amount)
		row.taxable_amount = sign * flt(row.net_total) if flt(row.vat_amount) else 0
		row.non_taxable_amount = 0 if flt(row.vat_amount) else sign * flt(row.net_total)
		row.output_tax = 0
		row.input_tax = sign * flt(row.vat_amount)
		row.net_amount = sign * flt(row.gross_amount)
		row.tax_payable = None
		row.party_type = "Supplier"
		row.doctype = "Purchase Invoice"
		data.append(row)

	return data


def get_purchase_transaction_type(row):
	return _("Purchase Invoice") if flt(row.stock_item_count) else _("Expense")


def get_journal_entry_rows(filters):
	tax_accounts = get_uae_vat_accounts(filters.company)
	if not tax_accounts:
		return []

	conditions = [
		"je.docstatus = 1",
		"je.company = %(company)s",
		"je.posting_date between %(from_date)s and %(to_date)s",
		"jea.account in %(tax_accounts)s",
	]

	if filters.get("cost_center"):
		conditions.append("jea.cost_center = %(cost_center)s")

	rows = frappe.db.sql(
		f"""
		select
			je.name as voucher_no,
			coalesce(nullif(je.bill_no, ''), je.name) as invoice_no,
			je.posting_date as date,
			jea.party_type,
			jea.party,
			coalesce(jea.cost_center, '') as cost_center,
			jea.account as tax_account,
			sum(jea.debit) as input_tax,
			sum(jea.credit) as output_tax,
			je.user_remark as remarks
		from `tabJournal Entry` je
		inner join `tabJournal Entry Account` jea on jea.parent = je.name
		where {" and ".join(conditions)}
		group by je.name, jea.account, jea.cost_center, jea.party_type, jea.party
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
		row.transaction_type = _("Tax Adjustment")
		row.party_name = get_party_name(row.party_type, row.party)
		row.trn = get_party_trn(row.party_type, row.party)
		row.total = 0
		row.discount_amount = 0
		row.taxable_amount = 0
		row.non_taxable_amount = 0
		row.net_amount = 0
		row.tax_payable = None
		row.doctype = "Journal Entry"

	return rows


def get_party_name(party_type, party):
	if not party_type or not party:
		return ""
	if party_type == "Customer":
		return frappe.get_cached_value("Customer", party, "customer_name") or party
	if party_type == "Supplier":
		return frappe.get_cached_value("Supplier", party, "supplier_name") or party
	return party


def get_party_trn(party_type, party):
	if not party_type or not party:
		return ""
	if party_type in ("Customer", "Supplier"):
		return frappe.get_cached_value(party_type, party, "tax_id") or ""
	return ""


def apply_common_filters(rows, filters):
	filtered = []
	for row in rows:
		if filters.get("transaction_type") and row.transaction_type != filters.transaction_type:
			continue
		if filters.get("tax_account") and filters.tax_account not in (row.tax_account or ""):
			continue
		if filters.get("party_type") and row.get("party_type") != filters.party_type:
			continue
		if filters.get("party") and row.get("party") != filters.party:
			continue
		if not cint(filters.get("show_zero_vat_rows")) and not (flt(row.output_tax) or flt(row.input_tax)):
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
		grouped_rows.append(make_vat_payable_row(grand_totals))

	return grouped_rows


def add_to_totals(totals, row):
	for field in (
		"total",
		"discount_amount",
		"taxable_amount",
		"non_taxable_amount",
		"output_tax",
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
			"output_tax": totals.get("output_tax"),
			"input_tax": totals.get("input_tax"),
			"net_amount": totals.get("net_amount"),
			"tax_payable": None,
			"is_group": 1,
		}
	)


def make_vat_payable_row(totals):
	return frappe._dict(
		{
			"transaction_type": _("Tax Payable / Recoverable"),
			"tax_payable": flt(totals.get("output_tax")) - flt(totals.get("input_tax")),
			"is_group": 1,
		}
	)


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 105},
		{"label": _("Transaction Type"), "fieldname": "transaction_type", "fieldtype": "Data", "width": 150},
		{
			"label": _("Voucher No"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "doctype",
			"width": 180,
		},
		{"label": _("Invoice No"), "fieldname": "invoice_no", "fieldtype": "Data", "width": 140},
		{"label": _("Party Name"), "fieldname": "party_name", "fieldtype": "Data", "width": 220},
		{"label": _("Party Tax ID"), "fieldname": "trn", "fieldtype": "Data", "width": 140},
		{"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 140},
		{"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "width": 120},
		{"label": _("Discount"), "fieldname": "discount_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Taxable Amount"), "fieldname": "taxable_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Non Taxable Amount"), "fieldname": "non_taxable_amount", "fieldtype": "Currency", "width": 150},
		{"label": _("Output Tax"), "fieldname": "output_tax", "fieldtype": "Currency", "width": 115},
		{"label": _("Input Tax"), "fieldname": "input_tax", "fieldtype": "Currency", "width": 110},
		{"label": _("Net Amount"), "fieldname": "net_amount", "fieldtype": "Currency", "width": 125},
		{"label": _("Tax Payable / Recoverable"), "fieldname": "tax_payable", "fieldtype": "Currency", "width": 170},
		{"label": _("Tax Account"), "fieldname": "tax_account", "fieldtype": "Data", "width": 220},
		{"label": _("Party Type"), "fieldname": "party_type", "fieldtype": "Data", "width": 100},
		{"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 170},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
		{"label": _("Doctype"), "fieldname": "doctype", "fieldtype": "Data", "width": 120, "hidden": 1},
	]
