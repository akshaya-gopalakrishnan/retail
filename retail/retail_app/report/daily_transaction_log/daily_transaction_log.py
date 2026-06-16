import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", getdate())
	filters.setdefault("to_date", getdate())

	return get_columns(), get_data(filters)


def get_data(filters):
	rows = get_invoice_rows(filters)
	payment_modes = get_payment_modes([row.name for row in rows])
	item_counts = get_item_counts([row.name for row in rows])
	filtered_rows = []

	for row in rows:
		row.invoice_no = row.name
		row.counter = row.custom_counter or _("No Counter")
		row.cashier = row.owner
		row.transaction_type = _("Return") if row.is_return else _("Sale")
		row.display_status = get_display_status(row)
		row.grand_total = -abs(flt(row.base_grand_total)) if row.is_return else abs(flt(row.base_grand_total))
		row.paid_amount = -abs(flt(row.base_paid_amount)) if row.is_return else abs(flt(row.base_paid_amount))
		row.outstanding_amount = (
			-abs(flt(row.outstanding_amount)) if row.is_return else abs(flt(row.outstanding_amount))
		)
		row.payment_mode = payment_modes.get(row.name) or ""
		row.item_count = item_counts.get(row.name, 0)
		row.cancelled_by = row.modified_by if row.docstatus == 2 else ""
		row.cancelled_on = row.modified if row.docstatus == 2 else None

		if filters.get("payment_mode") and filters.payment_mode not in row.payment_mode.split(", "):
			continue

		filtered_rows.append(row)

	return filtered_rows


def get_display_status(row):
	if row.docstatus == 2:
		return _("Cancelled")
	if row.is_return:
		return _("Return")
	return row.status or _("Submitted")


def get_invoice_rows(filters):
	return frappe.db.sql(
		"""
		select
			name,
			posting_date,
			posting_time,
			coalesce(custom_counter, '') as custom_counter,
			customer,
			customer_name,
			docstatus,
			status,
			is_return,
			base_grand_total,
			base_paid_amount,
			outstanding_amount,
			owner,
			modified_by,
			modified,
			remarks
		from `tabSales Invoice`
		where docstatus in (1, 2)
			and posting_date between %(from_date)s and %(to_date)s
			and (%(company)s is null or company = %(company)s)
			and (%(counter)s is null or custom_counter = %(counter)s)
			and (%(cashier)s is null or owner = %(cashier)s)
			and (%(customer)s is null or customer = %(customer)s)
			and (
				%(status)s is null
				or (%(status)s = 'Cancelled' and docstatus = 2)
				or (%(status)s = 'Return' and docstatus = 1 and is_return = 1)
				or (%(status)s not in ('Cancelled', 'Return') and docstatus = 1 and status = %(status)s)
			)
		order by posting_date desc, posting_time desc, creation desc
		""",
		{
			"from_date": filters.from_date,
			"to_date": filters.to_date,
			"company": filters.get("company"),
			"counter": filters.get("counter"),
			"cashier": filters.get("cashier"),
			"customer": filters.get("customer"),
			"status": filters.get("status"),
		},
		as_dict=True,
	)


def get_payment_modes(invoice_names):
	if not invoice_names:
		return {}

	payment_modes = {}
	for payment in get_sales_invoice_payment_modes(invoice_names):
		payment_modes.setdefault(payment.parent, []).append(payment.mode_of_payment)

	for invoice, modes in get_payment_entry_modes(invoice_names).items():
		payment_modes.setdefault(invoice, []).extend(modes)

	for invoice, modes in payment_modes.items():
		payment_modes[invoice] = list(dict.fromkeys(modes))

	return {invoice: ", ".join(modes) for invoice, modes in payment_modes.items()}


def get_sales_invoice_payment_modes(invoice_names):
	return frappe.db.sql(
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


def get_payment_entry_modes(invoice_names):
	payments = frappe.db.sql(
		"""
		select
			per.reference_name as invoice,
			pe.mode_of_payment
		from `tabPayment Entry Reference` per
		inner join `tabPayment Entry` pe on pe.name = per.parent
		where pe.docstatus = 1
			and per.reference_doctype = 'Sales Invoice'
			and per.reference_name in %(invoice_names)s
			and ifnull(pe.mode_of_payment, '') != ''
		order by per.reference_name, pe.posting_date, pe.creation
		""",
		{"invoice_names": tuple(invoice_names)},
		as_dict=True,
	)

	payment_modes = {}
	for payment in payments:
		payment_modes.setdefault(payment.invoice, []).append(payment.mode_of_payment)

	return payment_modes


def get_item_counts(invoice_names):
	if not invoice_names:
		return {}

	rows = frappe.db.sql(
		"""
		select parent, sum(abs(stock_qty)) as item_count
		from `tabSales Invoice Item`
		where parent in %(invoice_names)s
		group by parent
		""",
		{"invoice_names": tuple(invoice_names)},
		as_dict=True,
	)

	return {row.parent: flt(row.item_count) for row in rows}


def get_columns():
	return [
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
		{"label": _("Posting Time"), "fieldname": "posting_time", "fieldtype": "Time", "width": 100},
		{
			"label": _("Invoice No"),
			"fieldname": "invoice_no",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 170,
		},
		{"label": _("Counter"), "fieldname": "counter", "fieldtype": "Data", "width": 140},
		{"label": _("Customer"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
		{"label": _("Status"), "fieldname": "display_status", "fieldtype": "Data", "width": 110},
		{"label": _("Transaction Type"), "fieldname": "transaction_type", "fieldtype": "Data", "width": 130},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 120},
		{"label": _("Paid Amount"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Outstanding Amount"),
			"fieldname": "outstanding_amount",
			"fieldtype": "Currency",
			"width": 150,
		},
		{"label": _("Payment Mode"), "fieldname": "payment_mode", "fieldtype": "Data", "width": 140},
		{"label": _("Item Count"), "fieldname": "item_count", "fieldtype": "Float", "width": 100},
		{"label": _("Created By"), "fieldname": "cashier", "fieldtype": "Link", "options": "User", "width": 160},
		{"label": _("Cancelled By"), "fieldname": "cancelled_by", "fieldtype": "Link", "options": "User", "width": 160},
		{"label": _("Cancelled On"), "fieldname": "cancelled_on", "fieldtype": "Datetime", "width": 160},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
	]
