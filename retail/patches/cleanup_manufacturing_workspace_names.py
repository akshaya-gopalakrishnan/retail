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

		if workspace_exists(new_name) or workspace_label_exists(new_name, exclude=old_name):
			hide_workspace(old_name)
			continue

		frappe.rename_doc("Workspace", old_name, new_name, force=True)
		frappe.db.set_value(
			"Workspace",
			new_name,
			{"label": new_name, "title": new_name},
			update_modified=False,
		)

	frappe.clear_cache()


def workspace_exists(name):
	return frappe.db.exists("Workspace", name)


def workspace_label_exists(label, exclude=None):
	name = frappe.db.get_value("Workspace", {"label": label}, "name")
	return bool(name and name != exclude)


def hide_workspace(name):
	frappe.db.set_value(
		"Workspace",
		name,
		{"public": 0, "is_hidden": 1, "parent_page": ""},
		update_modified=False,
	)
