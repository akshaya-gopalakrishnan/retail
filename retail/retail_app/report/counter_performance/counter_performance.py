import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    from retail.retail_app.report.profitability import profitability_columns
    return profitability_columns(get_columns()), get_data(frappe._dict(filters or {})), None, None, None, True

def get_data(filters):
    from retail.retail_app.report.profitability import profitability_rows, aggregate_profitability, profitability_total
    rows = aggregate_profitability(profitability_rows(filters),
        ["invoice_no", "posting_date", "posting_time", "counter", "cashier", "customer_name", "status", "is_return"])
    modes = get_payment_modes([r.invoice_no for r in rows])
    data = []
    from itertools import groupby
    for counter, members in groupby(sorted(rows, key=lambda r: r.counter or ""), key=lambda r:r.counter):
        members = list(members)
        for row in members:
            row.payment_mode = modes.get(row.invoice_no, "")
            row.is_return_display = "Yes" if row.is_return else "No"
        data.extend(members)
        total = profitability_total(members, "invoice_no")
        total.counter = counter
        total.status = "Counter Total"
        data.append(total)
    if rows:
        data.append(profitability_total(rows, "invoice_no"))
    return data

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
