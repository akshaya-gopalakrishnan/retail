import json

import frappe


def execute():
	if not frappe.db.exists("Workspace", "Sales"):
		return

	doc = frappe.get_doc("Workspace", "Sales")
	blocks = json.loads(doc.content or "[]")
	filtered = [
		block for block in blocks
		if not (
			block.get("type") == "shortcut"
			and block.get("data", {}).get("shortcut_name") == "Sales Return"
		)
	]
	shortcuts = [row for row in doc.shortcuts if row.label != "Sales Return"]
	if filtered == blocks and len(shortcuts) == len(doc.shortcuts):
		return

	doc.content = json.dumps(filtered, separators=(",", ":"))
	doc.set("shortcuts", shortcuts)
	doc.save(ignore_permissions=True)
	frappe.clear_cache()
