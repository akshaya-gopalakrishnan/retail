"""Use Tables as the display name while retaining the document identity."""
import frappe


def execute():
    for name in ("Restaurant", "Restaurant Tables Link"):
        if not frappe.db.exists("Workspace", name):
            continue
        doc = frappe.get_doc("Workspace", name)
        for shortcut in doc.shortcuts:
            if shortcut.link_to == "Restaurant Table":
                shortcut.label = "Tables"
        doc.content = doc.content.replace("Restaurant Table", "Tables")
        doc.save(ignore_permissions=True)
    frappe.clear_cache()
