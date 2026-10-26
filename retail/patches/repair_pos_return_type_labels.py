"""Repair return display labels without resaving receipts or accepted facts."""
import frappe

from retail.pos_transaction_display import transaction_type


def execute():
    for row in frappe.get_all("POS Invoice", filters={"is_return": 1},
            fields=["name", "is_return", "external_pos_reference", "custom_pos_transaction_type"]):
        label = transaction_type(row)
        if row.custom_pos_transaction_type != label:
            frappe.db.set_value("POS Invoice", row.name, "custom_pos_transaction_type",
                label, update_modified=False)
        if not row.external_pos_reference:
            continue
        for name in frappe.get_all("POS Sync Log", filters={
                "external_reference": row.external_pos_reference,
                "sync_type": ["in", ["POS Sale", "Sales Invoice", "Credit Sales Invoice", "POS Return", "Return"]]},
                pluck="name"):
            frappe.db.set_value("POS Sync Log", name, "custom_pos_transaction_type",
                label, update_modified=False)
