"""Give restaurant setup records numeric IDs without changing display names."""
import frappe
from frappe.model.rename_doc import rename_doc

from retail.restaurant.naming import next_numeric_id


def execute():
    for doctype in ("Table Location", "Restaurant Table"):
        frappe.reload_doc("restaurant", "doctype", frappe.scrub(doctype))
        for name in frappe.get_all(doctype, pluck="name", order_by="creation asc, name asc"):
            if name.isascii() and name.isdecimal():
                continue
            rename_doc(doctype, name, next_numeric_id(doctype), force=True,
                       ignore_permissions=True, show_alert=False)
    frappe.clear_cache()
