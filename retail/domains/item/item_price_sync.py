import frappe
from frappe.utils import flt


def sync_simple_item_prices(doc, method=None):
	if isinstance(doc, str):
		doc = frappe.get_doc("Item", doc)

	sync_item_price(doc, "Standard Selling", doc.get("standard_rate"))
	sync_item_price(doc, "Standard Buying", doc.get("custom_default_purchase_rate"))


def sync_item_price(doc, price_list, rate):
    rate = flt(rate)
    if rate <= 0:
        return

    item_code = doc.get("item_code") or doc.name
    uom = doc.get("stock_uom") or "Nos"

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


def disable_legacy_last_purchase_rate_script():
	"""Prevent the old Item script from overwriting Standard Buying with history."""
	if frappe.db.exists("Server Script", "purchase rate submit"):
		frappe.db.set_value("Server Script", "purchase rate submit", "disabled", 1, update_modified=False)


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
