import frappe
from frappe.utils import flt


def sync_simple_item_prices(doc, method=None):
    if isinstance(doc, str):
        doc = frappe.get_doc("Item", doc)

    sync_item_price(doc, "Standard Selling", doc.get("standard_rate"))


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
