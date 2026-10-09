import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    for dt in ("POS Branch Day Closing", "POS Operator Privilege", "POS Sync Log"):
        frappe.reload_doc("retail_app", "doctype", frappe.scrub(dt))
    create_custom_fields({
        "Payment Entry": [{"fieldname": "custom_settlement_operation", "fieldtype": "Data", "label": "Settlement Correction Reference", "read_only": 1, "no_copy": 1}],
        "POS Invoice": [{"fieldname": "custom_payment_revision", "fieldtype": "Int", "label": "Payment Correction Revision", "default": "0", "read_only": 1, "no_copy": 1}],
        "Sales Invoice": [{"fieldname": "custom_payment_revision", "fieldtype": "Int", "label": "Payment Correction Revision", "default": "0", "read_only": 1, "no_copy": 1}],
    }, update=True, ignore_validate=True)
    marker = "retail.pos_day_corrections.native_repost.v1"
    if not frappe.db.exists("Patch Log", {"patch": marker}):
        settings = frappe.get_single("Repost Accounting Ledger Settings")
        matches = [row for row in settings.allowed_types if row.document_type == "Sales Invoice"]
        if matches:
            for row in matches:
                row.allowed = 1
        else:
            settings.append("allowed_types", {"document_type": "Sales Invoice", "allowed": 1})
        settings.save(ignore_permissions=True)
        frappe.get_doc({"doctype": "Patch Log", "patch": marker}).insert(ignore_permissions=True)
    # Remove the unused field from the initial, rollback-tested journal prototype.
    old_field = "Journal Entry-custom_pos_payment_correction"
    if frappe.db.exists("Custom Field", old_field):
        if not frappe.db.count("Journal Entry", {"custom_pos_payment_correction": ["is", "set"]}):
            frappe.delete_doc("Custom Field", old_field, ignore_permissions=True)
    frappe.clear_cache()
