import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from retail.domains.sales.channel import POS_CHANNEL, TRADING_CHANNEL


def execute():
	frappe.flags.in_patch = True
	create_custom_fields(get_custom_fields(), ignore_validate=True, update=True)
	backfill_sales_channel()

	for doctype in ("Sales Invoice", "Sales Order", "Delivery Note", "Payment Entry"):
		frappe.clear_cache(doctype=doctype)


def get_custom_fields():
	sales_channel_field = {
		"fieldname": "sales_channel",
		"label": "Sales Channel",
		"fieldtype": "Select",
		"options": f"\n{TRADING_CHANNEL}\n{POS_CHANNEL}",
		"default": TRADING_CHANNEL,
		"insert_after": "company",
		"in_list_view": 1,
		"in_standard_filter": 1,
		"allow_on_submit": 1,
		"read_only": 1,
		"no_copy": 1,
	}

	payment_entry_field = sales_channel_field.copy()
	payment_entry_field["insert_after"] = "payment_type"

	return {
		"Sales Invoice": [sales_channel_field],
		"Sales Order": [sales_channel_field.copy()],
		"Delivery Note": [sales_channel_field.copy()],
		"Payment Entry": [payment_entry_field],
	}


def backfill_sales_channel():
	if not frappe.db.has_column("Sales Invoice", "sales_channel"):
		return

	pos_conditions = []
	if frappe.db.has_column("Sales Invoice", "is_pos"):
		pos_conditions.append("ifnull(is_pos, 0) = 1")
	if frappe.db.has_column("Sales Invoice", "external_pos_reference"):
		pos_conditions.append("ifnull(external_pos_reference, '') != ''")
	if frappe.db.has_column("Sales Invoice", "pos_sync_source"):
		pos_conditions.append("ifnull(pos_sync_source, '') != ''")

	if pos_conditions:
		frappe.db.sql(
			f"""
			update `tabSales Invoice`
			set sales_channel = case
				when {' or '.join(pos_conditions)} then %s
				else %s
			end
			""",
			(POS_CHANNEL, TRADING_CHANNEL),
		)

	for doctype in ("Sales Order", "Delivery Note"):
		if frappe.db.has_column(doctype, "sales_channel"):
			frappe.db.sql(
				f"""
				update `tab{doctype}`
				set sales_channel = %s
				where ifnull(sales_channel, '') = ''
				""",
				TRADING_CHANNEL,
			)

	if frappe.db.has_column("Payment Entry", "sales_channel"):
		payment_pos_conditions = []
		if frappe.db.has_column("Payment Entry", "external_pos_reference"):
			payment_pos_conditions.append("ifnull(external_pos_reference, '') != ''")
		if frappe.db.has_column("Payment Entry", "pos_sync_source"):
			payment_pos_conditions.append("ifnull(pos_sync_source, '') != ''")

		if payment_pos_conditions:
			frappe.db.sql(
				f"""
				update `tabPayment Entry`
				set sales_channel = %s
				where ifnull(sales_channel, '') = ''
					and ({' or '.join(payment_pos_conditions)})
				""",
				POS_CHANNEL,
			)

		frappe.db.sql(
			"""
			update `tabPayment Entry`
			set sales_channel = %s
			where ifnull(sales_channel, '') = ''
			""",
			TRADING_CHANNEL,
		)
