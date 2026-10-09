import json
from pathlib import Path

import frappe
from frappe.utils.fixtures import sync_fixtures


WORKSPACE_SUFFIX = " Desk"


def execute():
	workspace_names = get_fixture_workspace_names()
	for new_name in workspace_names:
		if not new_name.endswith(WORKSPACE_SUFFIX):
			continue

		old_name = new_name[: -len(WORKSPACE_SUFFIX)]
		if old_name == new_name:
			continue

		if not frappe.db.exists("Workspace", old_name):
			continue
		if not frappe.db.exists("Workspace", new_name):
			continue

		module = frappe.db.get_value("Workspace", old_name, "module")
		if module != "Retail-app":
			continue

		frappe.delete_doc("Workspace", old_name, ignore_permissions=True, force=True)

	frappe.db.commit()
	sync_fixtures("retail")


def get_fixture_workspace_names():
	workspace_root = Path(frappe.get_app_path("retail")) / "retail_app" / "workspace"
	names = set()

	for path in workspace_root.glob("*/*.json"):
		with path.open() as fixture:
			data = json.load(fixture)
		if name := data.get("name"):
			names.add(name)

	return names
