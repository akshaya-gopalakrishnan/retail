"""Persist a unique retry reference for orders created by the Sales Order app."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields({"Sales Order": [{
		"fieldname": "custom_app_order_id", "label": "App Order ID", "fieldtype": "Data",
		"insert_after": "po_no", "read_only": 1, "no_copy": 1, "unique": 1,
	}]}, ignore_validate=True)
