import frappe


def execute():
    for name in ("pos_accepted_transaction", "pos_settlement_allocation", "pos_settlement_exception"):
        frappe.reload_doc("retail_app", "doctype", name)

    frappe.reload_doc("retail_app", "doctype", "pos_sync_log")
    frappe.reload_doc("retail_app", "report", "pos_settlement_audit")
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({"POS Branch Day Closing": [{
        "fieldname": "pos_settlement_totals", "label": "POS Settlement Totals",
        "fieldtype": "Long Text", "read_only": 1, "allow_on_submit": 1,
        "insert_after": "payment_totals",
    }]})

    fields = [("credit_sales", "Credit Sales"), ("credit_notes_issued", "Credit Note Issued"),
        ("credit_notes_redeemed", "Credit Note Redeemed"), ("credit_notes_applied", "Credit Note Applied"),
        ("credit_notes_unresolved", "Credit Note Unresolved")]
    create_custom_fields({doctype: [{"fieldname": "pos_" + field, "label": label,
        "fieldtype": "Currency", "read_only": 1, "allow_on_submit": 1}
        for field, label in fields] for doctype in ("POS Branch Day Closing", "POS Cashier Shift", "POS Closing Entry")})

    from frappe.core.doctype.scheduled_job_type.scheduled_job_type import insert_single_event
    insert_single_event("Cron", "retail.pos_settlements.recover", "*/5 * * * *")
