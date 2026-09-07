import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint


def execute():
	create_custom_fields(
		{
			"Employee": [
				{
					"fieldname": "pos_login_id",
					"label": "POS Login ID",
					"fieldtype": "Int",
					"insert_after": "pos_login_enabled",
					"description": "Unique numeric login ID used by cashier in POS.",
				},
			],
		},
		ignore_validate=True,
		update=True,
	)
	frappe.db.updatedb("Employee")
	backfill_pos_login_ids()
	frappe.clear_cache(doctype="Employee")


def backfill_pos_login_ids():
	if not frappe.get_meta("Employee").has_field("pos_login_id"):
		return

	next_id = 101
	used = {
		cint(row.pos_login_id)
		for row in frappe.get_all(
			"Employee",
			filters=[["pos_login_id", "is", "set"]],
			fields=["pos_login_id"],
			limit_page_length=0,
		)
		if cint(row.pos_login_id) > 0
	}
	if used:
		next_id = max(next_id, max(used) + 1)

	for row in frappe.get_all(
		"Employee",
		filters={"status": "Active", "pos_login_enabled": 1},
		fields=["name"],
		order_by="creation asc",
		limit_page_length=0,
	):
		if cint(frappe.db.get_value("Employee", row.name, "pos_login_id")) > 0:
			continue
		while next_id in used:
			next_id += 1
		frappe.db.set_value("Employee", row.name, "pos_login_id", next_id, update_modified=False)
		used.add(next_id)
		next_id += 1
