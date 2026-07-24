import json
from pathlib import Path

import frappe


FIXTURE_FILE = "user_grid_view_settings.json"


def get_fixture_path():
	return Path(frappe.get_app_path("retail", FIXTURE_FILE))


def export_user_grid_view_settings(user=None):
	"""Export form child-table GridView columns from __UserSettings.

	These settings are not normal DocType fixtures. This helper captures only
	the GridView part so list filters, last views, and personal preferences do
	not become app defaults accidentally.
	"""
	filters = "WHERE data LIKE %s"
	values = ["%GridView%"]
	if user:
		filters += " AND user = %s"
		values.append(user)

	rows = frappe.db.sql(
		f"SELECT user, doctype, data FROM `__UserSettings` {filters} ORDER BY user, doctype",
		values,
		as_dict=True,
	)

	settings = {}
	for row in rows:
		data = json.loads(row.data or "{}")
		grid_view = data.get("GridView")
		if not isinstance(grid_view, dict) or not grid_view:
			continue

		parent_settings = settings.setdefault(row.doctype, {})
		for child_doctype, columns in grid_view.items():
			if isinstance(columns, list) and columns:
				parent_settings[child_doctype] = columns

	fixture_path = get_fixture_path()
	fixture_path.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n")
	frappe.msgprint(f"Exported GridView settings to {fixture_path}")
	return settings


def install_default_grid_view_settings(overwrite=False):
	if not get_fixture_path().exists():
		return

	defaults = json.loads(get_fixture_path().read_text() or "{}")
	if not defaults:
		return

	users = frappe.get_all(
		"User",
		filters={"enabled": 1},
		pluck="name",
	)
	for user in users:
		if user == "Guest":
			continue
		apply_default_grid_view_settings_for_user(user, defaults=defaults, overwrite=overwrite)


def apply_default_grid_view_settings_for_user(doc=None, method=None, defaults=None, overwrite=False):
	user = doc.name if hasattr(doc, "name") else doc
	if not user or user == "Guest":
		return

	defaults = defaults or json.loads(get_fixture_path().read_text() or "{}")
	for parent_doctype, grid_view_defaults in defaults.items():
		current = _get_user_settings(user, parent_doctype)
		current_grid_view = current.setdefault("GridView", {})
		changed = False

		for child_doctype, columns in grid_view_defaults.items():
			if current_grid_view.get(child_doctype) and not overwrite:
				continue
			current_grid_view[child_doctype] = columns
			changed = True

		if changed:
			_save_user_settings(user, parent_doctype, current)


def _get_user_settings(user, doctype):
	data = frappe.db.sql(
		"SELECT data FROM `__UserSettings` WHERE user=%s AND doctype=%s",
		(user, doctype),
	)
	return json.loads(data[0][0] or "{}") if data else {}


def _save_user_settings(user, doctype, data):
	serialized = json.dumps(data)
	frappe.db.multisql(
		{
			"mariadb": """INSERT INTO `__UserSettings`(`user`, `doctype`, `data`)
				VALUES (%s, %s, %s)
				ON DUPLICATE KEY UPDATE `data`=%s""",
			"postgres": """INSERT INTO "__UserSettings" ("user", "doctype", "data")
				VALUES (%s, %s, %s)
				ON CONFLICT ("user", "doctype") DO UPDATE SET "data"=%s""",
		},
		(user, doctype, serialized, serialized),
	)
	frappe.cache.hdel("_user_settings", f"{doctype}::{user}")
