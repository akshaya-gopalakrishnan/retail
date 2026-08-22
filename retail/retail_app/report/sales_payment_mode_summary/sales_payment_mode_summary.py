from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters=None):
	filters = get_filters(filters)
	conditions, values = get_conditions(filters)
	rows = frappe.db.sql(
		f"""
		select
			posting_date,
			company,
			mode_of_payment,
			payment_type,
			count(distinct invoice_no) as invoice_count,
			sum(paid_amount) as paid_amount
		from (
			select
				si.name as invoice_no,
				si.posting_date,
				si.company,
				pay.mode_of_payment,
				mop.type as payment_type,
				case when si.is_return = 1 then -abs(coalesce(pay.amount, 0)) else abs(coalesce(pay.amount, 0)) end as paid_amount
			from `tabSales Invoice Payment` pay
			inner join `tabSales Invoice` si on si.name = pay.parent
			left join `tabMode of Payment` mop on mop.name = pay.mode_of_payment
			where {conditions}
			union all
			select
				si.name as invoice_no,
				si.posting_date,
				si.company,
				pe.mode_of_payment,
				mop.type as payment_type,
				case when pe.payment_type = 'Pay' then -abs(coalesce(per.allocated_amount, 0)) else abs(coalesce(per.allocated_amount, 0)) end as paid_amount
			from `tabPayment Entry Reference` per
			inner join `tabPayment Entry` pe on pe.name = per.parent
			inner join `tabSales Invoice` si on si.name = per.reference_name
			left join `tabMode of Payment` mop on mop.name = pe.mode_of_payment
			where {conditions.replace("pay.", "pe.").replace("si.docstatus = 1", "si.docstatus = 1 and pe.docstatus = 1").replace("ifnull(pe.mode_of_payment, '') != ''", "ifnull(pe.mode_of_payment, '') != '' and per.reference_doctype = 'Sales Invoice'")}
		) payments
		group by posting_date, company, mode_of_payment
		order by posting_date desc, mode_of_payment
		""",
		values,
		as_dict=True,
	)
	return get_columns(), rows


def get_filters(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", getdate())
	filters.setdefault("to_date", getdate())
	return filters


def get_conditions(filters):
	conditions = ["si.docstatus = 1", "ifnull(pay.mode_of_payment, '') != ''"]
	values = {}

	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.get("company"):
		conditions.append("si.company = %(company)s")
		values["company"] = filters.company
	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")
		values["customer"] = filters.customer
	if filters.get("payment_mode"):
		conditions.append("pay.mode_of_payment = %(payment_mode)s")
		values["payment_mode"] = filters.payment_mode
	if not filters.get("include_pos_invoices"):
		conditions.append("ifnull(si.is_pos, 0) = 0")

	return " and ".join(conditions), values


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
		{"label": _("Mode of Payment"), "fieldname": "mode_of_payment", "fieldtype": "Link", "options": "Mode of Payment", "width": 160},
		{"label": _("Payment Type"), "fieldname": "payment_type", "fieldtype": "Data", "width": 120},
		{"label": _("Invoice Count"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 120},
		{"label": _("Paid Amount"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 130},
	]
