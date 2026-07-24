from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


OPEN_PRICE_FIELD = "custom_is_open_price"


def ensure_item_pos_flags():
	create_custom_fields(
		{
			"Item": [
				{
					"fieldname": OPEN_PRICE_FIELD,
					"label": "Open Price",
					"fieldtype": "Check",
					"insert_after": "custom_scale_barcode_type",
					"description": "Allow POS cashier to enter the selling rate for this item.",
				},
			],
		},
		update=True,
	)
