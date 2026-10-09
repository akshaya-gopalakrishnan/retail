"""POS list configuration. Edit FILTERS and COLUMNS, then run execute()."""
import frappe
from frappe.utils import flt, getdate

# Standard filter bar fields per DocType. Other fields remain in the Filter dialog.
FILTERS = {
    "POS Sync Log": ["posting_date", "branch", "pos_counter", "custom_pos_transaction_type", "status"],
    "POS Profile": ["company", "disabled"],
    "POS Branch Counter": ["branch", "is_active"],
    "POS Opening Entry": ["posting_date", "pos_profile", "pos_branch_counter", "status"],
    "POS Closing Entry": ["posting_date", "pos_profile", "pos_branch_counter", "status"],
}
COLUMNS = {
    "POS Profile": ["company", "warehouse", "status_field"],
    "POS Branch Counter": ["counter_code", "counter_name", "branch", "pos_profile", "status_field"],
    "POS Opening Entry": ["pos_profile", "period_start_date", "period_end_date", "custom_opening_cash", "status_field"],
    "POS Closing Entry": ["pos_profile", "period_end_date", "custom_closing_amount", "status_field"],
}


def set_log_metadata(doc):
    request = frappe.parse_json(doc.get("request_json") or "{}")
    if not isinstance(request, dict):
        request = {}
    payload = request.get("payload", request)
    if not isinstance(payload, dict):
        payload = {}
    from retail.pos_transaction_display import payload_transaction_type
    doc.custom_pos_transaction_type = payload_transaction_type(doc.sync_type,
        {**payload, "external_pos_reference": payload.get("external_pos_reference") or doc.get("external_reference")})
    doc.posting_date = getdate(payload.get("business_date") or payload.get("posting_date")
        or doc.get("created_at") or doc.get("creation"))
    code = payload.get("counter_code") or doc.get("counter")
    branch = payload.get("branch") or doc.get("branch")
    filters = {"counter_code": code}
    if branch:
        filters["branch"] = branch
    matches = frappe.get_all("POS Branch Counter", filters=filters, pluck="name") if code else []
    doc.pos_counter = matches[0] if len(matches) == 1 else None


def set_opening_summary(doc, method=None):
    cash_modes = set(frappe.get_all("Mode of Payment", filters={"type": "Cash"}, pluck="name"))
    doc.custom_opening_cash = sum(flt(row.opening_amount) for row in doc.balance_details
        if row.mode_of_payment in cash_modes)


def set_closing_summary(doc, method=None):
    doc.custom_closing_amount = sum(flt(row.closing_amount) for row in doc.payment_reconciliation)


def update_opening_end_date(doc, method=None):
    if not doc.pos_opening_entry:
        return
    end_date = frappe.db.get_value("POS Closing Entry",
        {"pos_opening_entry": doc.pos_opening_entry, "docstatus": 1, "status": "Submitted"},
        "period_end_date", order_by="creation desc")
    frappe.db.set_value("POS Opening Entry", doc.pos_opening_entry, "period_end_date",
        getdate(end_date) if end_date else None, update_modified=False)


def configure():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    create_custom_fields({
        "POS Sync Log": [
            {"fieldname": "posting_date", "label": "Posting Date", "fieldtype": "Date",
             "read_only": 1, "insert_after": "status", "in_standard_filter": 1},
            {"fieldname": "pos_counter", "label": "Counter", "fieldtype": "Link",
             "options": "POS Branch Counter", "read_only": 1, "insert_after": "counter",
             "in_standard_filter": 1},
        ],
        "POS Opening Entry": [{"fieldname": "custom_opening_cash", "label": "Opening Cash",
            "fieldtype": "Currency", "read_only": 1, "in_list_view": 1, "insert_after": "balance_details"}],
        "POS Closing Entry": [{"fieldname": "custom_closing_amount", "label": "Closing Amount",
            "fieldtype": "Currency", "read_only": 1, "in_list_view": 1, "insert_after": "payment_reconciliation"}],
    })
    make_property_setter("POS Sync Log", "counter", "label", "Counter Code", "Data")
    for doctype, fields in FILTERS.items():
        for df in frappe.get_meta(doctype).fields:
            enabled = int(df.fieldname in fields)
            if bool(df.in_standard_filter) != bool(enabled):
                make_property_setter(doctype, df.fieldname, "in_standard_filter", str(enabled), "Check")
    for doctype, fields in COLUMNS.items():
        for field in fields:
            if field != "status_field":
                make_property_setter(doctype, field, "in_list_view", "1", "Check")
        settings = (frappe.get_doc("List View Settings", doctype)
            if frappe.db.exists("List View Settings", doctype) else frappe.new_doc("List View Settings"))
        settings.name = doctype
        settings.fields = frappe.as_json([{"fieldname": field} for field in fields])
        settings.total_fields = str(len(fields) + 1)
        settings.save(ignore_permissions=True)
    frappe.clear_cache()


def execute():
    configure()
    for name in frappe.get_all("POS Sync Log", pluck="name"):
        doc = frappe.get_doc("POS Sync Log", name)
        set_log_metadata(doc)
        frappe.db.set_value(doc.doctype, name,
            {"posting_date": doc.posting_date, "pos_counter": doc.pos_counter}, update_modified=False)
    for doctype, setter, field in [
        ("POS Opening Entry", set_opening_summary, "custom_opening_cash"),
        ("POS Closing Entry", set_closing_summary, "custom_closing_amount"),
    ]:
        for name in frappe.get_all(doctype, pluck="name"):
            doc = frappe.get_doc(doctype, name)
            setter(doc)
            frappe.db.set_value(doctype, name, field, doc.get(field), update_modified=False)
            if doctype == "POS Closing Entry":
                update_opening_end_date(doc)
    frappe.clear_cache()
