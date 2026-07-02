import frappe
from frappe.utils import flt


LEGACY_ITEM_PRICE_SCRIPTS = (
	"for unique row unique price",
	"purchase rate submit",
	"UOM&Barcode table sync Retail Packing detail after save",
)


def sync_simple_item_prices(doc, method=None):
	if isinstance(doc, str):
		doc = frappe.get_doc("Item", doc)

	sync_item_price(doc, "Standard Selling", doc.get("standard_rate"))
	sync_item_price(doc, "Standard Buying", doc.get("custom_default_purchase_rate"))
	sync_packing_item_prices(doc)


def sync_packing_item_prices(doc):
	for row in doc.get("custom_retail_packing_detail") or []:
		if not row.get("uom"):
			continue

		sync_item_price(
			doc, "Standard Selling", row.get("selling_net_rate") or row.get("selling_rate"), uom=row.uom
		)
		sync_item_price(
			doc, "Standard Buying", row.get("purchase_net_rate") or row.get("purchase_rate"), uom=row.uom
		)


def sync_item_price(doc, price_list, rate, uom=None):
	rate = flt(rate)
	if rate <= 0:
		return

	item_code = doc.get("item_code") or doc.name
	uom = uom or doc.get("stock_uom") or "Nos"

	price_name = frappe.db.get_value(
		"Item Price",
		{
			"item_code": item_code,
			"price_list": price_list,
			"uom": uom,
		},
	)

	if price_name:
		frappe.db.set_value(
			"Item Price",
			price_name,
			"price_list_rate",
			rate,
			update_modified=False,
		)
		return

	frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": item_code,
			"price_list": price_list,
			"price_list_rate": rate,
			"uom": uom,
		}
	).insert(ignore_permissions=True)


def disable_legacy_item_price_scripts():
	"""Prevent old server scripts from competing with the app's Item Price sync."""
	for script_name in LEGACY_ITEM_PRICE_SCRIPTS:
		if frappe.db.exists("Server Script", script_name):
			frappe.db.set_value("Server Script", script_name, "disabled", 1, update_modified=False)


def disable_legacy_last_purchase_rate_script():
	"""Backward-compatible patch entry point."""
	disable_legacy_item_price_scripts()


def ensure_standard_purchase_rate_field():
	"""Make the maintained buying cost visible on Item Master."""
	field_name = "Item-custom_default_purchase_rate"
	if not frappe.db.exists("Custom Field", field_name):
		return

	frappe.db.set_value(
		"Custom Field",
		field_name,
		{
			"label": "Standard Purchase Rate",
			"description": None,
			"hidden": 0,
		},
		update_modified=False,
	)
	if frappe.db.exists("Property Setter", "Item-custom_default_purchase_rate-hidden"):
		frappe.db.set_value(
			"Property Setter", "Item-custom_default_purchase_rate-hidden", "value", "0", update_modified=False
		)
	frappe.clear_cache(doctype="Item")
