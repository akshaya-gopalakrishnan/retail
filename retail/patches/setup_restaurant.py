"""Install Restaurant navigation on existing sites."""
import json
from pathlib import Path

import frappe


def execute():
    base = Path(__file__).resolve().parents[1] / "retail_app" / "workspace"
    for name in ("restaurant", "restaurant_table_locations_link", "restaurant_tables_link"):
        data = json.loads((base / name / f"{name}.json").read_text())
        if frappe.db.exists("Workspace", data["name"]):
            continue
        doc = frappe.get_doc(data)
        doc.insert(ignore_permissions=True)
    frappe.clear_cache()
