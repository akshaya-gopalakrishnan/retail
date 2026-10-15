import frappe


def execute():
    for name in ("pos_accepted_transaction", "pos_settlement_allocation", "pos_settlement_exception"):
        frappe.reload_doc("retail_app", "doctype", name)

    frappe.reload_doc("retail_app", "doctype", "pos_sync_log")
    frappe.reload_doc("retail_app", "report", "pos_settlement_audit")
    from retail.pos_sync_schema import ensure_settlement_fields
    ensure_settlement_fields()

    from frappe.core.doctype.scheduled_job_type.scheduled_job_type import insert_single_event
    insert_single_event("Cron", "retail.pos_settlements.recover", "*/5 * * * *")
