"""Cost for Item pricing guidance; never changes buying prices or stock valuation."""

import frappe
import frappe.defaults
from frappe.utils import flt


def get_margin_cost(doc):
	for field in ("custom_purchase_net_rate", "custom_default_purchase_rate", "last_purchase_rate"):
		if flt(doc.get(field)) > 0:
			return {"cost": flt(doc.get(field)), "source": "Maintained purchase cost"}

	if doc.get("name") and not doc.get("__islocal"):
		company = frappe.defaults.get_user_default("Company")
		companies = frappe.get_list("Company", pluck="name")
		if company:
			companies = [company] if company in companies else []
		if companies:
			stock = frappe.db.sql("""
				select sum(b.stock_value) as value, sum(b.actual_qty) as qty
				from `tabBin` b
				join `tabWarehouse` w on w.name = b.warehouse
				where b.item_code = %s and w.company in %s
				  and b.actual_qty > 0 and b.stock_value > 0
			""", (doc.name, tuple(companies)), as_dict=True)[0]
			if flt(stock.qty) > 0:
				return {
					"cost": flt(stock.value) / flt(stock.qty),
					"source": "Weighted current stock valuation: " + ", ".join(companies),
				}

	for field in ("valuation_rate", "custom_average_purchase_rate"):
		if flt(doc.get(field)) > 0:
			return {"cost": flt(doc.get(field)), "source": "Item " + field.replace("_", " ")}
	return {"cost": None, "source": "Cost unavailable; margin cannot be calculated"}


@frappe.whitelist()
def get_stock_margin_cost(item_code):
	doc = frappe.get_doc("Item", item_code)
	doc.check_permission("read")
	# The browser applies its unsaved purchase inputs itself.
	for field in ("custom_purchase_net_rate", "custom_default_purchase_rate", "last_purchase_rate"):
		doc.set(field, 0)
	return get_margin_cost(doc)
