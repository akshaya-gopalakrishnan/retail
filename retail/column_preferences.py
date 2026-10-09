"""Durable personal table columns, restricted to Retail's configured forms."""

import json
from pathlib import Path

import frappe

from retail.grid_view_settings import _get_user_settings, _save_user_settings


COLUMN_KEYS = frozenset({"GridView", "RetailScrollableGrid"})


def supported_doctypes():
	return json.loads(Path(__file__).with_name("column_preference_doctypes.json").read_text())


def boot_session(bootinfo):
	bootinfo.retail_column_doctypes = supported_doctypes()


@frappe.whitelist(methods=["POST"])
def save(doctype, key, value=None):
	"""Only column namespaces, only Retail forms, and only the current user."""
	if frappe.session.user == "Guest":
		frappe.throw("Login required", frappe.PermissionError)
	if doctype not in supported_doctypes() or key not in COLUMN_KEYS:
		frappe.throw("Only Retail table column preferences can be saved here", frappe.ValidationError)
	if not frappe.has_permission(doctype, "read"):
		frappe.throw("Not permitted to read this DocType", frappe.PermissionError)

	value = frappe.parse_json(value) if isinstance(value, str) else value
	if value is not None and not isinstance(value, dict):
		frappe.throw("Column preferences must be an object or null", frappe.ValidationError)

	tables = {df.fieldname: df.options for df in frappe.get_meta(doctype).get_table_fields()}
	normalized = None if value is None else {}
	for table, columns in (value or {}).items():
		child = tables.get(table) if key == "RetailScrollableGrid" else table
		if child not in tables.values() or not isinstance(columns, list):
			frappe.throw("Invalid child table column preferences", frappe.ValidationError)
		fields = {df.fieldname for df in frappe.get_meta(child).fields}
		normalized[table] = []
		for column in columns:
			if not isinstance(column, dict) or column.get("fieldname") not in fields:
				frappe.throw("Unknown column in table preferences", frappe.ValidationError)
			width = column.get("columns")
			width = 1 if width is None else width
			if (
				isinstance(width, bool) or not isinstance(width, (int, float))
				or not 1 <= width <= 12 or int(width) != width
			):
				frappe.throw("Column width must be a whole number from 1 to 12", frappe.ValidationError)
			normalized[table].append({"fieldname": column["fieldname"], "columns": int(width)})

	user = frappe.session.user
	current = _get_user_settings(user, doctype)
	# Preserve cached native preferences, without accepting edits to them here.
	cached = frappe.cache.hget("_user_settings", f"{doctype}::{user}")
	if cached is not None:
		cached = json.loads(cached or "{}")
		if isinstance(cached, dict):
			current.update(cached)
	if normalized is None:
		current[key] = None
	else:
		existing = current.get(key)
		current[key] = {**(existing if isinstance(existing, dict) else {}), **normalized}

	_save_user_settings(user, doctype, current)

	def invalidate():
		frappe.cache.hdel("_user_settings", f"{doctype}::{user}")

	# Invalidate again in case another reader refilled Redis before commit.
	frappe.db.after_commit.add(invalidate)
	frappe.db.after_rollback.add(invalidate)
	return current
