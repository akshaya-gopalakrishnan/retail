"""Enable standard Auto Repeat without changing transaction behavior."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


DOCTYPES = (
    "Purchase Invoice", "Sales Invoice", "Purchase Order", "Purchase Receipt",
    "Quotation", "Supplier Quotation", "Sales Order", "Delivery Note",
    "Journal Entry", "Subcontracting Order", "Payment Entry", "POS Invoice",
)


def install():
    """Run after customization sync on installation and every migration.

    Existing fields are never rewritten. Conflicting fields or unsupported
    DocTypes are reported and skipped rather than forcing a configuration.
    """
    result = {}
    for doctype in DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            result[doctype] = "skipped: DocType is not installed"
            continue
        meta = frappe.get_meta(doctype, cached=False)
        field = meta.get_field("auto_repeat")
        if meta.istable or meta.issingle or meta.is_virtual:
            result[doctype] = "skipped: unsupported DocType storage"
            continue
        if field and (field.fieldtype != "Link" or field.options != "Auto Repeat"):
            result[doctype] = "skipped: existing auto_repeat field is not a Link to Auto Repeat"
            continue
        if not field:
            create_custom_field(doctype, {
                "fieldname": "auto_repeat", "label": "Auto Repeat",
                "fieldtype": "Link", "options": "Auto Repeat",
                "insert_after": meta.fields[-1].fieldname,
                "read_only": 1, "no_copy": 1, "print_hide": 1,
            })
        if not meta.allow_auto_repeat:
            setters = frappe.get_all("Property Setter", filters={
                "doc_type": doctype, "doctype_or_field": "DocType",
                "property": "allow_auto_repeat",
            }, pluck="name")
            if setters:
                for name in setters:
                    setter = frappe.get_doc("Property Setter", name)
                    setter.value = "1"
                    setter.save(ignore_permissions=True)
            else:
                make_property_setter(
                    doctype, None, "allow_auto_repeat", "1", "Check", for_doctype=True,
                    # This DocType-level flag does not change field definitions.
                    validate_fields_for_doctype=False,
                )
        result[doctype] = "enabled"
    for doctype, status in result.items():
        if status != "enabled":
            print(f"Retail Auto Repeat: {doctype}: {status}")
    return result
