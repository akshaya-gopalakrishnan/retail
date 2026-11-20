"""Expose selected business date alongside actual shift timestamps."""
import frappe


def execute():
    from retail.pos_list_settings import COLUMNS, configure_columns
    frappe.reload_doc("retail_app", "doctype", "pos_cashier_shift")
    configure_columns("POS Cashier Shift", COLUMNS["POS Cashier Shift"])
    frappe.clear_cache(doctype="POS Cashier Shift")
