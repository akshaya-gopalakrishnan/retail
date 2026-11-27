"""Optional receipt snapshots and separately accounted POS delivery charges."""
import frappe
from frappe.utils import flt


SNAPSHOTS = {
    "cashier_name": ("POS Cashier Name", "Data"),
    "sales_man": ("POS Sales Man", "Data"),
    "sales_man_name": ("POS Sales Man Name", "Data"),
    "customer_name": ("POS Customer Name", "Data"),
    "delivery_person": ("Delivery Person", "Data"),
    "delivery_person_name": ("Delivery Person Name", "Data"),
    "customer_address": ("POS Customer Address", "Small Text"),
    "delivery_charge": ("Delivery Charge", "Currency"),
}


def set_snapshots(doc, payload):
    for key in SNAPSHOTS:
        if key in payload:
            doc.set("custom_pos_" + key, flt(payload[key]) if key == "delivery_charge" else payload[key])


def append_charge(doc, payload):
    amount = flt(payload.get("delivery_charge"))
    if not amount:
        return
    # Server-owned account routing; the terminal supplies only the amount.
    account = frappe.get_cached_value("Company", doc.company, "default_income_account")
    if not account:
        account = next((row.income_account for row in doc.items if row.get("income_account")), None)
    if not account or frappe.get_cached_value("Account", account, "company") != doc.company:
        frappe.throw("Configure a company default income account for POS delivery charges.")
    doc.append("taxes", {
        "charge_type": "Actual", "account_head": account,
        "description": "POS Delivery Charge", "rate": 0,
        "tax_amount": -abs(amount) if doc.is_return else amount,
        "cost_center": doc.cost_center,
    })


def install():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    fields = []
    previous = "customer"
    for key, (label, fieldtype) in SNAPSHOTS.items():
        fieldname = "custom_pos_" + key
        fields.append(dict(fieldname=fieldname, label=label, fieldtype=fieldtype,
            read_only=1, no_copy=1, insert_after=previous))
        previous = fieldname
    create_custom_fields({"POS Invoice": fields}, update=True)
