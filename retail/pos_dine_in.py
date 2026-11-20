"""Dine-in display metadata for newly synchronized POS invoices."""
import frappe


def from_payload(payload):
    if "is_dine_in" not in payload:
        return 1
    value = payload.get("is_dine_in")
    if value is None or (isinstance(value, str) and not value.strip()):
        return 0
    if isinstance(value, bool) or (type(value) is int and value in (0, 1)):
        return int(value)
    frappe.throw(frappe._("is_dine_in must be true, false, 1, 0, null or empty."))


def install():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({"POS Invoice": [{
        "fieldname": "custom_is_dine_in", "label": "Dine In", "fieldtype": "Check",
        "insert_after": "custom_pos_transaction_type", "default": "0", "read_only": 1,
        "depends_on": "eval:doc.custom_is_dine_in == 1", "no_copy": 1,
    }]}, ignore_validate=True)
    from retail.pos_invoice_layout import execute
    execute()
