"""Replace only the Oldest Items workspace chart with the fast-moving report."""
import json

import frappe


def execute():
    frappe.reload_doc("retail_app", "dashboard_chart", "fast_moving_items")
    if not frappe.db.exists("Workspace", "Items"):
        return
    doc = frappe.get_doc("Workspace", "Items")
    for row in doc.charts:
        if row.chart_name == "Oldest Items":
            row.chart_name = row.label = "Fast Moving Items"
    blocks = json.loads(doc.content or "[]")
    for row in blocks:
        if row.get("type") == "chart" and row.get("data", {}).get("chart_name") == "Oldest Items":
            row["data"]["chart_name"] = "Fast Moving Items"
            row["id"] = "chart_fast_moving_items"
    doc.content = json.dumps(blocks, separators=(",", ":"))
    doc.db_update()
    doc.update_children()
    frappe.clear_cache(doctype="Workspace")
