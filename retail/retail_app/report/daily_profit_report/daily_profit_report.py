"""Profitability grouped from the shared posted invoice source."""
import frappe
from retail.retail_app.report.profitability import profitability_rows, report_result


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.company:
        frappe.throw("Please select a Company.")
    field = {"Invoice": "invoice_no", "Item Code": "item_code", "Item Group": "item_group",
             "Brand": "brand", "Warehouse": "warehouse", "Customer": "customer", "Monthly": "month"}.get(filters.get("group_by") or "Invoice")
    if not field:
        frappe.throw("Unsupported grouping")
    rows = profitability_rows(filters)
    for row in rows:
        row.sales_group = str(row.posting_date)[:7] if field == "month" else row.get(field)
    return report_result(rows, [dict(fieldname="sales_group", label=filters.get("group_by") or "Invoice", fieldtype="Data", width=200)], ["sales_group"])
