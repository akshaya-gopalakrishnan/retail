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
			{"label": old_name, "title": old_name, "parent_page": "Manufacturing", "public": 1, "is_hidden": 0},
			update_modified=False,
		)

	frappe.clear_cache()
