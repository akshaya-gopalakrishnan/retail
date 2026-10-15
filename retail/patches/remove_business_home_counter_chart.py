"""Remove only the Business Home counter chart; preserve the POS workspace."""
import json

import frappe


def execute():
    if not frappe.db.exists("Workspace", "Business Home"):
        return
    doc = frappe.get_doc("Workspace", "Business Home")
    blocks = json.loads(doc.content or "[]")
    doc.content = json.dumps([
        row for row in blocks
        if not (row.get("type") == "chart"
                and row.get("data", {}).get("chart_name") == "Sales by Counter")
    ], separators=(",", ":"))
    doc.set("charts", [row for row in doc.charts if row.chart_name != "Sales by Counter"])
    # Avoid developer-mode export and preserve every other saved workspace setting.
    doc.db_update()
    doc.update_children()
    frappe.clear_cache(doctype="Workspace")
