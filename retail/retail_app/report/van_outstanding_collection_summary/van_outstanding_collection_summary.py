from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from retail.retail_app.report.van_sales_report_utils import add_total_row, common_filters_sql, filter_values, get_van_sales_invoices, normalize_filters


def execute(filters=None):
	filters = normalize_filters(filters)
	return get_columns(), get_data(filters), None, None, None, 1


def get_data(filters):
	rows = defaultdict(new_row)
	for invoice in get_van_sales_invoices(filters):
		key = (invoice.customer, invoice.van, invoice.driver)
		row = rows[key]
		set_identity(row, invoice)
		if invoice.is_return:
			row.credit_sales -= abs(flt(invoice.base_grand_total))
			row.outstanding_amount -= abs(flt(invoice.outstanding_amount))
		else:
			row.invoice_count += 1
			row.credit_sales += flt(invoice.base_grand_total)
			row.outstanding_amount += flt(invoice.outstanding_amount)

	for payment in get_van_payments(filters):
		key = (payment.party, payment.van, payment.driver)
		row = rows[key]
		row.customer = payment.party
		row.customer_name = payment.party_name or payment.party
		row.van_session = payment.van_session
		row.van = payment.van
		row.driver = payment.driver
		row.driver_name = payment.driver_name
		row.collection_amount += flt(payment.paid_amount)
		row.payment_count += 1

	data = sorted(rows.values(), key=lambda row: (row.customer_name or "", row.van or ""))
	return add_total_row(data, "customer_name")


def get_van_payments(filters):
	return frappe.db.sql(
		f"""
		select
			pe.name,
			pe.posting_date,
			pe.party,
			pe.party_name,
			pe.custom_van_session as van_session,
			pe.custom_van as van,
			pe.custom_driver as driver,
			pe.custom_driver_name as driver_name,
			pe.paid_amount
		from `tabPayment Entry` pe
		where pe.docstatus = 1
			and pe.custom_is_van_payment = 1
			and pe.payment_type = 'Receive'
			and pe.posting_date between %(from_date)s and %(to_date)s
			{common_filters_sql("pe")}
		""",
		filter_values(filters),
		as_dict=True,
	)


def new_row():
	return frappe._dict({
		"customer": None,
		"customer_name": None,
		"van_session": None,
		"van": None,
		"driver": None,
		"driver_name": None,
		"invoice_count": 0,
		"payment_count": 0,
		"credit_sales": 0,
		"collection_amount": 0,
		"outstanding_amount": 0,
	})


def set_identity(row, source):
	row.customer = source.customer
	row.customer_name = source.customer_name
	row.van_session = source.van_session
	row.van = source.van
	row.driver = source.driver
	row.driver_name = source.driver_name


def get_columns():
	return [
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
		{"label": _("Van Session"), "fieldname": "van_session", "fieldtype": "Link", "options": "Van Session", "width": 160},
		{"label": _("Van"), "fieldname": "van", "fieldtype": "Link", "options": "Van Fleet", "width": 120},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Driver", "width": 150},
		{"label": _("Driver Name"), "fieldname": "driver_name", "fieldtype": "Data", "width": 140},
		{"label": _("Invoices"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 90},
		{"label": _("Payments"), "fieldname": "payment_count", "fieldtype": "Int", "width": 90},
		{"label": _("Credit Sales"), "fieldname": "credit_sales", "fieldtype": "Currency", "width": 130},
		{"label": _("Collections"), "fieldname": "collection_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 130},
	]
