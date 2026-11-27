"""Add log navigation and editor capabilities without changing existing log access."""
import json
from pathlib import Path

import frappe


def execute():
	frappe.reload_doc("retail_app", "doctype", "van_sales_sync_log", force=True)
	base = Path(frappe.get_app_path("retail")) / "retail_app" / "workspace"
	for slug in ("van_sales_sync_logs", "sales_order_api_logs"):
		data = json.loads((base / slug / (slug + ".json")).read_text())
		if frappe.db.exists("Workspace", data["name"]):
			doc = frappe.get_doc("Workspace", data["name"])
			values = {key: data[key] for key in ("parent_page", "sequence_id", "module", "is_hidden", "label", "title", "content")}
			if any(doc.get(key) != value for key, value in values.items()):
				doc.update(values)
				doc.save(ignore_permissions=True)
		else:
			frappe.get_doc(data).insert(ignore_permissions=True)
	from retail.sidebar_registry import registry, routes, labels
	registry.cache_clear()
	routes.cache_clear()
	labels.cache_clear()
	# Administrator already has all native access. Extend only its navigation
	# preference for these new links; never enable logs for ordinary users.
	value = frappe.db.get_value("User", "Administrator", "retail_sidebar_permissions")
	if value:
		try:
			config = json.loads(value)
			selected = set(config["allowed"]) if config.get("version") == 1 else None
		except (ValueError, TypeError, KeyError):
			selected = None
		if selected is not None:
			before = selected.copy()
			for group in registry():
				if group["id"] not in selected:
					continue
				selected.update(child["id"] for child in group["children"]
					if child["workspace"] in {"Van Sales Sync Logs", "Sales Order API Logs"})
			if selected != before:
				frappe.db.set_value("User", "Administrator", "retail_sidebar_permissions",
					json.dumps({**config, "allowed": sorted(selected)}))
	frappe.clear_cache()
