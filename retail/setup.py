import frappe


RETAIL_WORKSPACE_MODULE = "Retail-app"


def hide_non_retail_workspaces():
	"""Keep the Desk sidebar focused on Retail's workspace tree."""
	if not frappe.db.table_exists("Workspace"):
		return

	updates = []
	for workspace in frappe.get_all("Workspace", fields=["name", "module", "public", "is_hidden"]):
		if workspace.module == RETAIL_WORKSPACE_MODULE:
			continue

		if workspace.public or not workspace.is_hidden:
			updates.append(workspace.name)

	for workspace_name in updates:
		frappe.db.set_value(
			"Workspace",
			workspace_name,
			{"public": 0, "is_hidden": 1},
			update_modified=False,
		)

	if updates:
		frappe.clear_cache()
