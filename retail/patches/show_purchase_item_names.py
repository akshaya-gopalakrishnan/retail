"""Add purchase item names to existing layouts once, preserving other columns."""

import json

import frappe

from retail.grid_view_settings import _get_user_settings, _save_user_settings


PURCHASE_DOCTYPES = ("Purchase Order", "Purchase Invoice", "Purchase Receipt")


def add_item_name(columns):
	if not isinstance(columns, list) or not any(c.get("fieldname") == "item_code" for c in columns):
		return columns
	name = next(
		(c for c in columns if c.get("fieldname") == "item_name"),
		{"fieldname": "item_name", "columns": 2},
	)
	result = [c for c in columns if c.get("fieldname") != "item_name"]
	position = next(i for i, c in enumerate(result) if c.get("fieldname") == "item_code")
	result.insert(position + 1, name)
	return result


def execute():
	for user in frappe.get_all("User", pluck="name"):
		if user == "Guest":
			continue
		for parent in PURCHASE_DOCTYPES:
			current = _get_user_settings(user, parent)
			cache_key = f"{parent}::{user}"
			cached = frappe.cache.hget("_user_settings", cache_key)
			if cached is not None:
				current.update(json.loads(cached or "{}"))
			changed = False
			for namespace, table in (("GridView", parent + " Item"), ("RetailScrollableGrid", "items")):
				settings = current.get(namespace)
				if not isinstance(settings, dict) or table not in settings:
					continue
				columns = settings[table]
				updated = add_item_name(columns)
				if updated != columns:
					settings[table] = updated
					changed = True
			if changed:
				_save_user_settings(user, parent, current)
				# Keep rollback-safe invalidation if another request refills Redis.
				def invalidate(key=cache_key):
					frappe.cache.hdel("_user_settings", key)

				frappe.db.after_commit.add(invalidate)
				frappe.db.after_rollback.add(invalidate)
