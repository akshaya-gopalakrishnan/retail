"""Explicit app classification on editable Role Profiles; grants no access."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields({"Role Profile": [{
        "fieldname": "custom_app_module", "label": "App Module", "fieldtype": "Select",
        "options": "\nsales_order\nvan_sales\npurchase", "insert_after": "role_profile",
        "description": "Module used by the unified app login and login logs. Does not grant permissions.",
    }]}, update=True)
    defaults = {"Sales User": "sales_order", "Van Sales User": "van_sales",
                "Purchase User": "purchase", "Van Sales": "van_sales", "VSDriver": "van_sales"}
    for profile, module in defaults.items():
        if frappe.db.exists("Role Profile", profile) and not frappe.db.get_value("Role Profile", profile, "custom_app_module"):
            frappe.db.set_value("Role Profile", profile, "custom_app_module", module)
