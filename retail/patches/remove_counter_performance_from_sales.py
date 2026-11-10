"""Remove Counter Performance navigation from trading sales workspaces."""
import json

import frappe


REPORT = "Counter Performance"


def remove_report_links(data):
    links = []
    card = None
    for row in data.get("links", []):
        if row.get("type") == "Card Break":
            card = row
        if row.get("link_to") == REPORT:
            if card:
                card["link_count"] = max(0, (card.get("link_count") or 0) - 1)
            continue
        links.append(row)
    data["links"] = links
    data["shortcuts"] = [row for row in data.get("shortcuts", []) if row.get("link_to") != REPORT]
    blocks = json.loads(data.get("content") or "[]")
    data["content"] = json.dumps([
        block for block in blocks if not (
            block.get("type") == "shortcut"
            and block.get("data", {}).get("shortcut_name") == REPORT
        )
    ], separators=(",", ":"))


def execute():
    for name in ("Sales", "Reports"):
        if not frappe.db.exists("Workspace", name):
            continue
        doc = frappe.get_doc("Workspace", name)
        data = dict(content=doc.content, links=[r.as_dict() for r in doc.links],
                    shortcuts=[r.as_dict() for r in doc.shortcuts])
        before = json.dumps(data, default=str)
        remove_report_links(data)
        if before != json.dumps(data, default=str):
            doc.content = data["content"]
            for field in ("links", "shortcuts"):
                for idx, row in enumerate(data[field], 1):
                    row["idx"] = idx
                doc.set(field, data[field])
            doc.db_update()
            doc.update_children()
        doc.clear_cache()
