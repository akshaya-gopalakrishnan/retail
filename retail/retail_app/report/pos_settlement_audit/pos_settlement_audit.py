import frappe


def execute(filters=None):
    from retail.module_access import require
    require("POS")
    filters = frappe._dict(filters or {})
    query = {}
    for field in ("company", "branch", "customer", "status"):
        if filters.get(field):
            query[field] = filters[field]
    if filters.get("from_date") and filters.get("to_date"):
        query["business_date"] = ["between", [filters.from_date, filters.to_date]]
    rows = frappe.get_list("POS Settlement Allocation", filters=query, fields=["*"], limit_page_length=0)
    columns = [dict(fieldname=field, label=label, fieldtype=kind, width=160) for field, label, kind in (
        ("business_date", "Business Date", "Date"), ("external_pos_reference", "POS Reference", "Data"),
        ("customer", "Customer", "Data"), ("settlement_type", "Settlement Type", "Data"),
        ("source_external_reference", "Source POS Reference", "Data"),
        ("requested_amount", "Requested", "Currency"), ("applied_amount", "Applied", "Currency"),
        ("unresolved_amount", "Unresolved", "Currency"), ("status", "Status", "Data"),
        ("source_erp_document", "Source Sales Invoice", "Data"),
        ("destination_erp_document", "Destination Sales Invoice", "Data"),
        ("reconciliation_reference", "Reconciliation Journals", "Data"),
        ("exception_reason", "Exception", "Data"))]
    return columns, rows
