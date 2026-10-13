import json

import frappe


def execute():
	if not frappe.db.exists("Workspace", "Business Home"):
		return

	content = frappe.db.get_value("Workspace", "Business Home", "content")
	blocks = json.loads(content or "[]")
	changed = False
	for block in blocks:
		data = block.get("data", {})
		if block.get("type") == "chart" and data.get("chart_name") in (
			"Top Selling Products",
			"Sales Trend 7 Days",
		):
			if data.get("col") != 6:
				data["col"] = 6
				changed = True

	if changed:
		frappe.db.set_value(
			"Workspace", "Business Home", "content", json.dumps(blocks, separators=(",", ":"))
		)
		frappe.clear_cache()
