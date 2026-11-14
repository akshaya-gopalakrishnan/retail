"""Remove Rate with Margin from saved purchase item table layouts."""
import json

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from retail.grid_view_settings import _get_user_settings, _save_user_settings

PARENTS = ("Purchase Invoice", "Purchase Receipt")


def execute():
	for parent in PARENTS:
		make_property_setter(parent + " Item", "rate_with_margin", "in_list_view", 0,
			"Check", validate_fields_for_doctype=False)
		frappe.clear_cache(doctype=parent + " Item")
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
				updated = [column for column in mapping[table]
					if column.get("fieldname") != "rate_with_margin"]
				if updated != mapping[table]:
					mapping[table] = updated
					changed = True
			if changed:
				_save_user_settings(user, parent, settings)
				frappe.db.after_commit.add(lambda key=key: frappe.cache.hdel("_user_settings", key))
				frappe.db.after_rollback.add(lambda key=key: frappe.cache.hdel("_user_settings", key))
