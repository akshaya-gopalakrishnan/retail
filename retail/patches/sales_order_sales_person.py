"""Show Sales Person identity directly below the customer's purchase order."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields({"Sales Order": [
		{
			"fieldname": "sales_person_id", "label": "Sales Person ID",
			"fieldtype": "Autocomplete", "options": "", "insert_after": "po_no",
			"description": "Unique Sales Person Code from the Sales Person master.",
			"read_only_depends_on": "eval:doc.docstatus != 0", "allow_on_submit": 0,
			"no_copy": 1,
		},
		{
			"fieldname": "sales_person_name", "label": "Sales Person Name",
			"fieldtype": "Data", "insert_after": "sales_person_id",
			"fetch_from": "", "read_only": 1,
			"allow_on_submit": 0, "no_copy": 1,
		},
	]}, ignore_validate=True)
