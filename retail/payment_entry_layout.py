"""Keep the native payment reference beside the payment type."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def install():
    doctype = "Payment Entry"
    meta = frappe.get_meta(doctype)
    order = [field.fieldname for field in meta.fields if field.fieldname != "reference_no"]
    order.insert(order.index("payment_type") + 1, "reference_no")
    make_property_setter(
        doctype, None, "field_order", frappe.as_json(order), "Text", for_doctype=True
    )
    make_property_setter(doctype, "reference_no", "depends_on", "", "Data")
    make_property_setter(doctype, "reference_no", "label", "Reference", "Data")
    frappe.clear_cache(doctype=doctype)
