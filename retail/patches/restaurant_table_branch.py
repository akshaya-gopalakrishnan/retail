"""Add table branch selection without guessing existing multi-branch assignments."""
import frappe
from retail.restaurant.defaults import single_branch


def execute():
    frappe.reload_doc("restaurant", "doctype", "restaurant_table")
    branch = single_branch()
    if branch:
        for name in frappe.get_all("Restaurant Table", filters={"branch": ["is", "not set"]}, pluck="name"):
            frappe.db.set_value("Restaurant Table", name, "branch", branch)
    frappe.clear_cache()
