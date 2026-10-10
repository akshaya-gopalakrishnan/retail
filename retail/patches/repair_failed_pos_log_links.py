"""Remove invoice links incorrectly copied to failed sale attempts."""
import frappe


def execute():
    for name in frappe.get_all("POS Sync Log", filters={
            "status": "Failed",
            "sync_type": ["in", ["POS Sale", "Sales Invoice", "Credit Sales Invoice", "POS Return", "Return"]]},
            pluck="name"):
        frappe.db.set_value("POS Sync Log", name, {
            "linked_invoice_type": None,
            "linked_invoice": None,
            "custom_accounting_invoice": None,
            "erpnext_docname": None,
        }, update_modified=False)
    from retail.patches.repair_recovered_pos_display import execute as refresh
    refresh()
