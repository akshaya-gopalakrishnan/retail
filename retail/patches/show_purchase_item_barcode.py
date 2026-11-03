"""Show the Item master barcode after the purchase item name."""
import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from retail.grid_view_settings import _get_user_settings, _save_user_settings

PARENTS = ("Purchase Invoice", "Purchase Receipt")
FIELD = "custom_item_barcode"


def install():
	create_custom_fields({parent + " Item": [dict(
		fieldname=FIELD, label="Barcode", fieldtype="Data", insert_after="item_name",
		read_only=1, fetch_from="item_code.custom_barcode", in_list_view=1,
		columns=2,
	)] for parent in PARENTS})


def add_barcode(columns):
	if not isinstance(columns, list) or not any(c.get("fieldname") == "item_name" for c in columns):
		return columns
	barcode = next((c for c in columns if c.get("fieldname") == FIELD),
		{"fieldname": FIELD, "columns": 2})
	result = [c for c in columns if c.get("fieldname") != FIELD]
	index = next(i for i, c in enumerate(result) if c.get("fieldname") == "item_name")
	result.insert(index + 1, barcode)
	return result


def execute():
	install()
	for user in frappe.get_all("User", pluck="name"):
		if user == "Guest":
			continue
		for parent in PARENTS:
			settings = _get_user_settings(user, parent)
			key = f"{parent}::{user}"
			cached = frappe.cache.hget("_user_settings", key)
			if cached is not None:
				settings.update(json.loads(cached or "{}"))
			changed = False
			for namespace, table in (("GridView", parent + " Item"), ("RetailScrollableGrid", "items")):
				mapping = settings.get(namespace)
				if not isinstance(mapping, dict) or table not in mapping:
					continue
				updated = add_barcode(mapping[table])
				if updated != mapping[table]:
					mapping[table] = updated
					changed = True
			if changed:
				_save_user_settings(user, parent, settings)
				frappe.db.after_commit.add(lambda key=key: frappe.cache.hdel("_user_settings", key))
				frappe.db.after_rollback.add(lambda key=key: frappe.cache.hdel("_user_settings", key))
