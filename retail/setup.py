import frappe


RETAIL_WORKSPACE_MODULE = "Retail-app"
VISIBLE_RETAIL_WORKSPACES = {"Manufacturing"}
RETAIL_PRINT_LANGUAGES = {
	"ar": "Arabic",
	"hi": "Hindi",
	"ml": "Malayalam",
}


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

	for workspace_name in VISIBLE_RETAIL_WORKSPACES:
		if frappe.db.exists("Workspace", workspace_name):
			frappe.db.set_value(
				"Workspace",
				workspace_name,
				{"public": 1, "is_hidden": 0},
				update_modified=False,
			)

	if updates or VISIBLE_RETAIL_WORKSPACES:
		frappe.clear_cache()


def ensure_print_languages():
	"""Ensure required print languages are available on every site."""
	if not frappe.db.table_exists("Language"):
		return

	for language_code, language_name in RETAIL_PRINT_LANGUAGES.items():
		if frappe.db.exists("Language", language_code):
			frappe.db.set_value(
				"Language",
				language_code,
				{"language_name": language_name, "enabled": 1},
				update_modified=False,
			)
			continue

		frappe.get_doc(
			{
				"doctype": "Language",
				"language_code": language_code,
				"language_name": language_name,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)

	frappe.cache.delete_value("languages_with_name")
	frappe.cache.delete_value("languages")
