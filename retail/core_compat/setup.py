"""Persist former core UI customizations using supported site metadata."""
import json
from pathlib import Path

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def install():
    for field, prop in (("item_group", "allow_in_quick_entry"),
                        ("has_batch_no", "in_standard_filter"),
                        ("has_serial_no", "in_standard_filter")):
        make_property_setter("Item", field, prop, 1, "Check", validate_fields_for_doctype=False)
    frappe.clear_cache(doctype="Item")

    if frappe.db.exists("Workspace", "Users"):
        doc = frappe.get_doc("Workspace", "Users")
        content = json.loads(doc.content or "[]")
        for name in ("Customer License", "License History"):
            if not frappe.db.exists("DocType", name):
                continue
            if not any(row.label == name for row in doc.shortcuts):
                doc.append("shortcuts", dict(label=name, link_to=name, type="DocType", doc_view="List", color="Grey", stats_filter="[]"))
            if not any(row.get("type") == "shortcut" and row.get("data", {}).get("shortcut_name") == name for row in content):
                index = next((i for i, row in enumerate(content) if row.get("type") == "spacer"), len(content))
                content.insert(index, dict(id="retail_" + frappe.scrub(name), type="shortcut", data=dict(shortcut_name=name, col=3)))
        for row in doc.links:
            if row.link_to == "Document Share Report":
                row.report_ref_doctype = "DocShare"
        # db_update avoids developer-mode exporting a standard workspace to core.
        doc.content = json.dumps(content)
        doc.db_update()
        doc.update_children()
        frappe.clear_document_cache("Workspace", "Users")

    data = json.loads(Path(__file__).with_name("sales_invoice_copy.json").read_text())
    if not frappe.db.exists("Print Format", data["name"]):
        doc = frappe.get_doc(data)
        # Insert as custom to avoid developer-mode export; ownership is Retail.
        doc.standard = "No"
        doc.insert(ignore_permissions=True)
    frappe.db.set_value("Print Format", data["name"], "module", "Retail-app", update_modified=False)
