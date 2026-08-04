import frappe


RENAMED_WORKSPACES = {
	"BOM": "Manufacturing BOM",
	"Production Plan": "Manufacturing Production Plan",
	"Quality Inspection": "Manufacturing Quality Inspection",
}


def execute():
	if not frappe.db.table_exists("Workspace"):
		return

	for old_name, new_name in RENAMED_WORKSPACES.items():
		if not frappe.db.exists("Workspace", old_name):
			continue

		if (
			workspace_exists(new_name)
			or workspace_label_exists(new_name, exclude=old_name)
			or workspace_label_exists(old_name, exclude=old_name)
		):
			hide_workspace(old_name)
			continue

		frappe.rename_doc("Workspace", old_name, new_name, force=True)
		frappe.db.set_value(
			"Workspace",
			new_name,
			{"label": old_name, "title": old_name, "parent_page": "Manufacturing", "public": 1, "is_hidden": 0},
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
