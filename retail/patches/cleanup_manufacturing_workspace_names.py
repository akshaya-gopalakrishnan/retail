import frappe


RENAMED_WORKSPACES = {
	"MFG BOM": "BOM",
	"MFG Production Plan": "Production Plan",
	"MFG Work Orders": "Work Orders",
	"MFG Job Cards": "Job Cards",
	"MFG Stock Entries": "Stock Entries",
	"MFG Quality Inspection": "Quality Inspection",
	"MFG Reports": "Manufacturing Reports",
	"MFG Setup": "Manufacturing Setup",
	"MFG Material Requests": "Manufacturing Material Requests",
}


def execute():
	if not frappe.db.table_exists("Workspace"):
		return

	for old_name, new_name in RENAMED_WORKSPACES.items():
		if not frappe.db.exists("Workspace", old_name):
			continue

		if frappe.db.exists("Workspace", new_name):
			frappe.db.set_value(
				"Workspace",
				old_name,
				{"public": 0, "is_hidden": 1, "parent_page": ""},
				update_modified=False,
			)
			continue

		frappe.rename_doc("Workspace", old_name, new_name, force=True)
		frappe.db.set_value(
			"Workspace",
			new_name,
			{"label": new_name, "title": new_name},
			update_modified=False,
		)

	frappe.clear_cache()
