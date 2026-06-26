import frappe


POS_CHANNEL = "POS"
TRADING_CHANNEL = "Trading"


def get_sales_channel(doc):
	if doc.doctype == "Payment Entry":
		return get_payment_entry_sales_channel(doc)

	if doc.get("is_pos") or doc.get("external_pos_reference") or doc.get("pos_sync_source"):
		return POS_CHANNEL

	return doc.get("sales_channel") or TRADING_CHANNEL


def set_sales_channel(doc, method=None):
	if doc.meta.has_field("sales_channel"):
		doc.sales_channel = get_sales_channel(doc)


def get_payment_entry_sales_channel(doc):
	if doc.get("external_pos_reference") or doc.get("pos_sync_source"):
		return POS_CHANNEL

	for reference in doc.get("references", []):
		if reference.reference_doctype != "Sales Invoice" or not reference.reference_name:
			continue

		sales_channel = frappe.db.get_value("Sales Invoice", reference.reference_name, "sales_channel")
		if sales_channel:
			return sales_channel

	return doc.get("sales_channel") or TRADING_CHANNEL
