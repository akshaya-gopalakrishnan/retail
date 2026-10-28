"""Add serial/batch columns once without replacing personal purchase layouts."""

import json

import frappe

from retail.grid_view_settings import _get_user_settings, _save_user_settings


DOCTYPES = ("Purchase Invoice", "Purchase Receipt")


def add_columns(columns):
	if not isinstance(columns, list) or not columns:
		return columns
	result = list(columns)
	anchor = next((i for i, c in enumerate(result) if c.get("fieldname") == "item_name"), None)
	if anchor is None:
		anchor = next((i for i, c in enumerate(result) if c.get("fieldname") == "item_code"), None)
	if anchor is None:
		return columns
	for field in ("serial_no", "batch_no"):
		if not any(c.get("fieldname") == field for c in result):
			anchor += 1
			result.insert(anchor, {"fieldname": field, "columns": 2})
	return result


def execute():
	for user in frappe.get_all("User", pluck="name"):
		if user == "Guest":
			continue
		for parent in DOCTYPES:
			settings = _get_user_settings(user, parent)
			cache_key = f"{parent}::{user}"
			cached = frappe.cache.hget("_user_settings", cache_key)
			if cached is not None:
				settings.update(json.loads(cached or "{}"))
			changed = False
			for namespace, table in (("GridView", parent + " Item"), ("RetailScrollableGrid", "items")):
				mapping = settings.get(namespace)
				if not isinstance(mapping, dict) or table not in mapping:
					continue
				updated = add_columns(mapping[table])
				if updated != mapping[table]:
					mapping[table] = updated
					changed = True
			if changed:
				_save_user_settings(user, parent, settings)

				def invalidate(key=cache_key):
					frappe.cache.hdel("_user_settings", key)

				frappe.db.after_commit.add(invalidate)
				frappe.db.after_rollback.add(invalidate)
