"""Show the Item master barcode after the Sales Order item name."""
import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from retail.grid_view_settings import _get_user_settings, _save_user_settings

PARENTS = ("Sales Order",)
FIELD = "custom_item_barcode"


def install():
	create_custom_fields({parent + " Item": [dict(
		fieldname=FIELD, label="Barcode", fieldtype="Data", insert_after="item_name",
		read_only=1, fetch_from="", in_list_view=1,
		columns=2,
	), dict(
		fieldname="custom_packing_detail", label="Selected Packing", fieldtype="Data",
		insert_after=FIELD, hidden=1, read_only=1, no_copy=0,
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
	update_print_dates()
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


def update_print_dates():
	"""Update only the known date expression in existing site-owned layouts."""
	old = "item.schedule_date or item.required_by or doc.schedule_date"
	new = "item.delivery_date or doc.delivery_date or item.schedule_date or item.required_by or doc.schedule_date"
	for name in frappe.get_all("Print Format", filters={"doc_type": "Sales Order"}, pluck="name"):
		doc = frappe.get_doc("Print Format", name)
		if old in (doc.html or "") and new not in doc.html:
			doc.html = doc.html.replace(old, new)
			doc.save(ignore_permissions=True)
