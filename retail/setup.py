import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


RETAIL_WORKSPACE_MODULE = "Retail-app"
HIDDEN_STANDARD_WORKSPACES = {"Home"}
VISIBLE_RETAIL_WORKSPACES = {"Business Home", "Manufacturing"}
DEFAULT_RETAIL_WORKSPACE = "Business Home"
DEFAULT_PRINT_FORMATS = {
	"Sales Invoice": "Sales Invoice - Copy",
	"Delivery Note": "Delivery Note- Copy",
}
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
		if workspace.module == RETAIL_WORKSPACE_MODULE and workspace.name not in HIDDEN_STANDARD_WORKSPACES:
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
			values = {"public": 1, "is_hidden": 0}
			if workspace_name == DEFAULT_RETAIL_WORKSPACE:
				values["sequence_id"] = 0
			frappe.db.set_value("Workspace", workspace_name, values, update_modified=False)

	if updates or VISIBLE_RETAIL_WORKSPACES:
		frappe.clear_cache()


def clear_url_shortcut_link_targets():
	"""URL workspace shortcuts must not carry Dynamic Link targets."""
	if not frappe.db.table_exists("Workspace Shortcut"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabWorkspace Shortcut`
		SET link_to = NULL
		WHERE type = 'URL' AND link_to IS NOT NULL
		"""
	)


def ensure_default_print_formats():
	"""Keep Retail print formats as defaults after fixture sync and upgrades."""
	if not frappe.db.table_exists("Print Format") or not frappe.db.table_exists("Property Setter"):
		return

	for doctype, print_format in DEFAULT_PRINT_FORMATS.items():
		if not frappe.db.exists("Print Format", print_format):
			continue

		property_setter = f"{doctype}-main-default_print_format"
		if frappe.db.exists("Property Setter", property_setter):
			frappe.db.set_value(
				"Property Setter",
				property_setter,
				"value",
				print_format,
				update_modified=False,
			)
			continue

		make_property_setter(
			doctype,
			"main",
			"default_print_format",
			print_format,
			"Data",
			for_doctype=True,
			validate_fields_for_doctype=False,
		)

	for doctype in DEFAULT_PRINT_FORMATS:
		frappe.clear_cache(doctype=doctype)


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
