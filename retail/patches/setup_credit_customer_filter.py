"""Install a shared preset using the existing customer credit-limit child table."""

import frappe


def execute():
    key = {"reference_doctype": "Customer", "filter_name": "Credit Customers", "for_user": ""}
    if not frappe.db.exists("List Filter", key):
        frappe.get_doc({
            "doctype": "List Filter",
            **key,
            "filters": frappe.as_json([["Customer Credit Limit", "credit_limit", ">", 0]]),
        }).insert(ignore_permissions=True)
