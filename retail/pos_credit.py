"""Accounting references for collections against credit POS invoices."""

import frappe
from frappe import _
from frappe.utils import flt


def ensure_payment_invoice_field():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields({"Payment Entry": [{
        "fieldname": "pos_credit_invoice", "label": "Credit POS Invoice",
        "fieldtype": "Link", "options": "POS Invoice", "insert_after": "party",
        "read_only": 1, "no_copy": 1,
    }]})


def remaining_amount(invoice):
    """Rebuild the POS balance from submitted collections and unpaid returns."""
    if invoice.get("consolidated_invoice"):
        # Native accounting already includes credit-note and payment allocations.
        # Subtracting linked returns again would consume reusable credit twice.
        return max(0, flt(frappe.db.get_value("Sales Invoice", invoice.consolidated_invoice, "outstanding_amount"),
                          invoice.precision("outstanding_amount")))
    collected = frappe.db.sql("""
        select coalesce(sum(r.allocated_amount), 0)
        from `tabPayment Entry` p
        inner join `tabPayment Entry Reference` r on r.parent = p.name
            and r.parenttype = 'Payment Entry'
        where p.docstatus = 1 and p.pos_credit_invoice = %s
            and r.reference_doctype = 'Sales Invoice'
            and r.reference_name = %s
    """, (invoice.name, invoice.consolidated_invoice))[0][0]
    returns = frappe.get_all("POS Invoice", filters={
        "return_against": invoice.name, "is_return": 1, "docstatus": 1,
    }, fields=["grand_total", "rounded_total", "paid_amount", "write_off_amount"])
    credit = sum(flt(r.rounded_total or r.grand_total) - flt(r.paid_amount)
                 - flt(r.write_off_amount) for r in returns)
    return max(0, flt(flt(invoice.rounded_total or invoice.grand_total)
        - flt(invoice.paid_amount) - flt(invoice.write_off_amount) - flt(collected) + credit,
        invoice.precision("outstanding_amount")))


def refresh_payment_balance(doc, method=None):
    name = doc.get("pos_credit_invoice")
    names = {name} if name else set()
    accounting_names = [row.reference_name for row in doc.get("references") or []
                        if row.reference_doctype == "Sales Invoice"]
    if accounting_names and doc.get("pos_sync_source") == "Offline POS":
        names.update(frappe.get_all("POS Invoice", filters={
            "consolidated_invoice": ["in", accounting_names], "docstatus": 1,
            "is_return": 0,
        }, pluck="name"))
    for invoice_name in sorted(names):
        invoice = frappe.get_doc("POS Invoice", invoice_name, for_update=True)
        invoice.db_set("outstanding_amount", remaining_amount(invoice))
        invoice.set_status(update=True)


def accounting_invoice(invoice):
    """Return the individually posted accounting invoice for collection."""
    from retail.pos_realtime import post_invoice

    name = post_invoice(invoice)
    return frappe.get_doc("Sales Invoice", name, for_update=True)
