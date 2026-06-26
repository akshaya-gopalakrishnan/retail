"""Add the stable customer identifier used by offline POS upserts."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Customer": [
				{
					"fieldname": "external_pos_customer_id",
					"label": "External POS Customer ID",
					"fieldtype": "Data",
					"unique": 1,
					"no_copy": 1,
					"insert_after": "customer_name",
				}
			]
		},
		ignore_validate=True,
		update=True,
	)
