"""Descriptive POS business dates, independent of accounting posting dates."""
import frappe
from frappe.utils import getdate

FIELD = "custom_pos_business_date"


def configure():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({doctype: [{
        "fieldname": FIELD, "label": "Business Date", "fieldtype": "Date",
        "read_only": 1, "no_copy": 1,
        "insert_after": "period_start_date" if doctype == "POS Opening Entry" else "posting_date",
        "in_list_view": 1, "in_standard_filter": 1,
    }] for doctype in ("POS Opening Entry", "POS Closing Entry")})


def set_business_date(doc, method=None):
    if doc.get(FIELD):
        return
    value = None
    if doc.doctype == "POS Closing Entry" and doc.get("pos_opening_entry"):
        value = frappe.db.get_value("POS Opening Entry", doc.pos_opening_entry, FIELD)
    if not value and doc.get("pos_cashier_shift"):
        value = frappe.db.get_value("POS Cashier Shift", doc.pos_cashier_shift, "business_date")
    if value:
        doc.set(FIELD, getdate(value))


def execute():
    configure()
    def fill(doctype, name, value):
        if name and value and frappe.db.exists(doctype, name) and not frappe.db.get_value(doctype, name, FIELD):
            frappe.db.set_value(doctype, name, FIELD, getdate(value), update_modified=False)

    # Original successful device receipts are the source of selected dates.
    for log in frappe.get_all("POS Sync Log", filters={
        "sync_type": ["in", ["Shift Opening", "Shift Resume"]],
        "status": ["in", ["Success", "Duplicate"]],
    }, fields=["request_json", "response_json", "erpnext_docname"], order_by="creation asc"):
        try:
            request = frappe.parse_json(log.request_json or "{}")
            payload = request.get("payload", request)
            response = frappe.parse_json(log.response_json or "{}")
            name = response.get("pos_opening_entry") or log.erpnext_docname
            fill("POS Opening Entry", name, payload.get("business_date") or payload.get("posting_date"))
        except (ValueError, TypeError, AttributeError):
            continue
    for session in frappe.get_all("POS Counter Session", fields=["business_date", "pos_opening_entry"]):
        fill("POS Opening Entry", session.pos_opening_entry, session.business_date)
    for doctype in ("POS Opening Entry", "POS Closing Entry"):
        for row in frappe.get_all(doctype, pluck="name"):
            doc = frappe.get_doc(doctype, row)
            set_business_date(doc)
            fill(doctype, row, doc.get(FIELD))
    from retail.pos_list_settings import COLUMNS, configure_columns
    for doctype in ("POS Opening Entry", "POS Closing Entry"):
        configure_columns(doctype, COLUMNS[doctype])
        frappe.clear_cache(doctype=doctype)
