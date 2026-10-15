"""Reduce chart loading only in the requested workspaces."""
import json

import frappe


def trim(data):
    name = data.get("name")
    if name not in ("Reports", "Promotions", "Settings"):
        return
    remove_all = name in ("Promotions", "Settings")
    data["charts"] = [row for row in data.get("charts", [])
                      if not (remove_all or row.get("chart_name") == "Profit and Loss")]
    blocks = json.loads(data.get("content") or "[]")
    data["content"] = json.dumps([
        row for row in blocks
        if not (row.get("type") == "chart" and
                (remove_all or row.get("data", {}).get("chart_name") == "Profit and Loss"))
    ], separators=(",", ":"))
    if name == "Reports":
        blocks = json.loads(data["content"])
        for row in blocks:
            if row.get("type") == "chart":
                row["data"]["col"] = 6
        data["content"] = json.dumps(blocks, separators=(",", ":"))


def execute():
    for name in ("Reports", "Promotions", "Settings"):
        if not frappe.db.exists("Workspace", name):
            continue
        doc = frappe.get_doc("Workspace", name)
        data = dict(name=name, content=doc.content, charts=[r.as_dict() for r in doc.charts])
        trim(data)
        doc.content = data["content"]
        doc.set("charts", data["charts"])
        doc.db_update()
        doc.update_children()
    frappe.clear_cache(doctype="Workspace")
