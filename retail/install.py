"""Prepare custom DocTypes before Frappe imports Retail's field fixtures."""

import frappe
from frappe.core.doctype.data_import.data_import import import_doc


def prepare_fixture_doctypes():
	# Frappe imports fixture filenames alphabetically: custom_field.json precedes
	# doctype.json. Counter must exist before its Link fields are validated.
	import_doc(frappe.get_app_path("retail", "fixtures", "doctype.json"))
	# Repair partial installs before custom-field validation. The compact-code
	# installer writes options and their default together and never renames data.
	from retail.short_codes import install

	install()


def ensure_workspace_routes():
	"""Repair legacy titles so subsequent fixture exports keep safe routes."""
	for name, legacy in (
		("Manufacturing BOM", "BOM"),
		("Manufacturing Production Plan", "Production Plan"),
		("Manufacturing Quality Inspection", "Quality Inspection"),
	):
		if frappe.db.get_value("Workspace", name, "title") == legacy:
			frappe.db.set_value("Workspace", name, "title", name)
			frappe.clear_cache(doctype="Workspace")
