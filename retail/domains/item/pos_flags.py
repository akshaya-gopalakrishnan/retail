from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


OPEN_PRICE_FIELD = "custom_is_open_price"
FAST_PLU_FIELD = "custom_is_fast_plu_item"


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
				{
					"fieldname": FAST_PLU_FIELD,
					"label": "Fast PLU Item",
					"fieldtype": "Check",
					"insert_after": OPEN_PRICE_FIELD,
					"description": "Show this item in the POS fast PLU item list.",
				},
			],
		},
		update=True,
	)
