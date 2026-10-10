"""Repair display metadata only; accepted payloads and posting receipts stay intact."""
import frappe
from retail.pos_transaction_display import correct_consolidated_title, refresh_accepted_invoice_links


def execute():
    for row in frappe.get_all("POS Accepted Transaction", filters={"pos_invoice": ["is", "set"]},
            fields=["pos_invoice", "external_pos_reference"]):
        refresh_accepted_invoice_links(row)
    for row in frappe.get_all("Sales Invoice", filters={"is_consolidated": 1},
            fields=["name", "title", "naming_series", "customer_name", "customer", "is_consolidated"]):
        previous = row.title
        correct_consolidated_title(row)
        if row.title != previous:
            frappe.db.set_value("Sales Invoice", row.name, "title", row.title, update_modified=False)
