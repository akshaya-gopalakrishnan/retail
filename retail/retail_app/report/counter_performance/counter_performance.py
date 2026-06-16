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

	data = []
	counter_totals = {}
	grand_total = 0
	current_counter = None

	for row in rows:
		counter = row.custom_counter or _("No Counter")
		if current_counter and current_counter != counter:
			data.append(get_total_row(current_counter, counter_totals[current_counter], _("Counter Total")))

		current_counter = counter
		row.invoice_no = row.name
		row.counter = counter
		row.cashier = row.owner
		row.net_sales = -abs(flt(row.base_grand_total)) if row.is_return else abs(flt(row.base_grand_total))
		row.is_return_display = _("Yes") if row.is_return else _("No")
		row.payment_mode = payment_modes.get(row.name) or ""

		counter_totals.setdefault(counter, 0)
		counter_totals[counter] += row.net_sales
		grand_total += row.net_sales
		data.append(row)

	if current_counter:
		data.append(get_total_row(current_counter, counter_totals[current_counter], _("Counter Total")))

	if data:
		data.append(get_total_row(_("Grand Total"), grand_total, _("Grand Total")))

	return data


def get_total_row(counter, net_sales, status):
	return frappe._dict(
		{
			"invoice_no": "",
			"posting_date": None,
			"posting_time": None,
			"counter": counter,
			"cashier": "",
			"customer_name": "",
			"net_sales": net_sales,
			"is_return_display": "",
			"payment_mode": "",
			"status": status,
			"indent": 0,
		}
	)


def get_invoice_rows(filters):
	return frappe.db.sql(
		"""
		select
			name,
			posting_date,
			posting_time,
			coalesce(custom_counter, '') as custom_counter,
			owner,
			customer,
			customer_name,
			base_grand_total,
			is_return,
			status
		from `tabSales Invoice`
		where docstatus = 1
			and posting_date between %(from_date)s and %(to_date)s
			and (%(company)s is null or company = %(company)s)
			and (%(counter)s is null or custom_counter = %(counter)s)
			and (%(cashier)s is null or owner = %(cashier)s)
		order by coalesce(custom_counter, ''), posting_date desc, posting_time desc, creation desc
		""",
		{
			"from_date": filters.from_date,
			"to_date": filters.to_date,
			"company": filters.get("company"),
			"counter": filters.get("counter"),
			"cashier": filters.get("cashier"),
		},
		as_dict=True,
	)


def get_payment_modes(invoice_names):
	if not invoice_names:
		return {}

	payments = frappe.db.sql(
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

	payment_modes = {}
	for payment in payments:
		payment_modes.setdefault(payment.parent, []).append(payment.mode_of_payment)

	for invoice, modes in get_payment_entry_modes(invoice_names).items():
		payment_modes.setdefault(invoice, []).extend(modes)

	for invoice, modes in payment_modes.items():
		payment_modes[invoice] = list(dict.fromkeys(modes))

	return {invoice: ", ".join(modes) for invoice, modes in payment_modes.items()}


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


def get_columns():
	return [
		{
			"label": _("Invoice No"),
			"fieldname": "invoice_no",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 170,
		},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Time"), "fieldname": "posting_time", "fieldtype": "Time", "width": 90},
		{
			"label": _("Counter"),
			"fieldname": "counter",
			"fieldtype": "Data",
			"width": 150,
		},
		{"label": _("Cashier"), "fieldname": "cashier", "fieldtype": "Link", "options": "User", "width": 160},
		{"label": _("Customer"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("Is Return"), "fieldname": "is_return_display", "fieldtype": "Data", "width": 90},
		{"label": _("Payment Mode"), "fieldname": "payment_mode", "fieldtype": "Data", "width": 150},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
	]
