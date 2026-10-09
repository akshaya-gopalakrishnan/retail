"""Install portable Retail loyalty fields and place the existing totals together."""
import json
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from retail.domains.sales.invoice_totals import _place_after


def install():
    create_custom_fields({"Sales Invoice": [{
        "fieldname": "custom_available_loyalty_points", "label": "Available Loyalty Points",
        "fieldtype": "Int", "read_only": 1, "no_copy": 1,
        "insert_after": "column_break_77", "default": "0",
        "description": "Unexpired ledger points available for redemption. Refreshed when the customer or program changes.",
    }]}, update=True)
    order = [field.fieldname for field in frappe.get_meta("Sales Invoice").fields]
    order = _place_after(order, "column_break_77", ["custom_available_loyalty_points"])
    order = _place_after(order, "grand_total", ["loyalty_amount", "outstanding_amount"])
    make_property_setter("Sales Invoice", None, "field_order", json.dumps(order), "JSON", for_doctype=True)
    for field, prop, value, kind in [
        ("loyalty_points_redemption", "collapsible", 0, "Check"),
        ("loyalty_amount", "label", "Loyalty Redemption Amount", "Data"),
        ("loyalty_amount", "hidden", 0, "Check"),
        ("outstanding_amount", "hidden", 0, "Check"),
    ]:
        make_property_setter("Sales Invoice", field, prop, value, kind)
    frappe.clear_cache(doctype="Sales Invoice")
