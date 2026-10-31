"""Expose the original POS business date without changing accounting dates."""
import frappe
from frappe.utils import getdate


def configure():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter

    create_custom_fields({"POS Invoice": [{
        "fieldname": "custom_pos_business_date", "label": "Business Date",
        "fieldtype": "Date", "read_only": 1, "no_copy": 1,
        "insert_after": "cost_center", "in_list_view": 1, "in_standard_filter": 1,
    }]})
    for prop, value, kind in [("label", "Posting Date", "Data"),
                              ("in_list_view", "1", "Check"),
                              ("in_standard_filter", "1", "Check")]:
        make_property_setter("POS Invoice", "posting_date", prop, value, kind)


def set_business_date(doc, method=None):
    payload = frappe.parse_json(doc.get("custom_pos_completed_payload") or "{}")
    if isinstance(payload, dict) and payload.get("business_date"):
        doc.custom_pos_business_date = getdate(payload["business_date"])


def execute():
    configure()
    # Update only the new descriptive field, preserving posted dates and timestamps.
    for row in frappe.get_all("POS Invoice", fields=["name", "custom_pos_completed_payload",
                                                     "custom_pos_business_date"]):
        set_business_date(row)
        if row.custom_pos_business_date:
            frappe.db.set_value("POS Invoice", row.name, "custom_pos_business_date",
                                row.custom_pos_business_date, update_modified=False)
    for row in frappe.get_all("POS Accepted Transaction", filters={"pos_invoice": ["is", "set"]},
                             fields=["pos_invoice", "business_date"]):
        if row.business_date and not frappe.db.get_value("POS Invoice", row.pos_invoice,
                                                        "custom_pos_business_date"):
            frappe.db.set_value("POS Invoice", row.pos_invoice, "custom_pos_business_date",
                                row.business_date, update_modified=False)
    settings = (frappe.get_doc("List View Settings", "POS Invoice")
                if frappe.db.exists("List View Settings", "POS Invoice")
                else frappe.new_doc("List View Settings"))
    settings.name = "POS Invoice"
    fields = frappe.parse_json(settings.fields or "[]")
    if not fields:
        fields = [{"fieldname": "title"}, {"fieldname": "status_field"},
                  {"fieldname": "grand_total"}]
    added = 0
    for fieldname in ("custom_pos_business_date", "posting_date"):
        if not any(field.get("fieldname") == fieldname for field in fields):
            fields.insert(1 + added, {"fieldname": fieldname})
            added += 1
    settings.fields = frappe.as_json(fields)
    settings.total_fields = str(max(int(settings.total_fields or 6) + added, len(fields) + 1))
    settings.save(ignore_permissions=True)
    frappe.clear_cache(doctype="POS Invoice")
