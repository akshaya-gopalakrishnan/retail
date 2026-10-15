"""Stable date/time and target fields for Retail's external POS clients."""
import frappe
from frappe.utils import getdate, get_time


def promotion_payload(doc):
	data = doc.as_dict()
	for field in ("active_from", "active_to"):
		value = doc.get(field)
		data[field] = getdate(value).isoformat() if value else None
	for field in ("active_from_time", "active_to_time"):
		value = doc.get(field)
		data[field] = get_time(value).strftime("%H:%M:%S") if value is not None and value != "" else None
	if doc.doctype in ("Promo Price", "Buy X Get Y Promotion"):
		products = doc.get("products") or []
		if doc.doctype == "Buy X Get Y Promotion":
			products = [row for row in products if row.get("add_to") == "Buy Item"]
		data["promotion_scope"] = doc.get("promotion_scope") or (
			"CATEGORY" if products and products[0].get("item_group") else
			"BRAND" if products and products[0].get("brand") else "ITEM"
		)
	if doc.doctype == "Gift Voucher Promotion":
		for row in data.get("excluded_item_groups") or []:
			row["matching_item_groups"] = matching_item_groups(row.get("item_group"))
	return data


def matching_item_groups(item_group):
	"""Include the selected category and its descendants, as Retail matching does."""
	if not item_group:
		return []
	bounds = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=True)
	if not bounds or not bounds.lft or not bounds.rgt:
		return [item_group]
	groups = frappe.get_all("Item Group", filters={
		"lft": [">=", bounds.lft], "rgt": ["<=", bounds.rgt],
	}, pluck="name", order_by="lft asc")
	return groups or [item_group]
