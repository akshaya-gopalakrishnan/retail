"""Extend native list column selection without changing Frappe source."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def install():
    field = frappe.get_meta("List View Settings").get_field("total_fields")
    options = (field.options or "").split("\n")
    extended = options + [str(count) for count in range(11, 51) if str(count) not in options]
    if extended == options:
        return
    make_property_setter(
        "List View Settings", "total_fields", "options", "\n".join(extended), "Text"
    )
    frappe.clear_cache(doctype="List View Settings")
