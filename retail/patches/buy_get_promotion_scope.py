"""Keep existing Buy X Get Y targets when introducing the explicit scope."""
import frappe


def execute():
	for name in frappe.get_all("Buy X Get Y Promotion", pluck="name"):
		doc = frappe.get_doc("Buy X Get Y Promotion", name)
		if doc.get("promotion_scope"):
			continue
		rows = [row for row in doc.products if row.add_to == "Buy Item"]
		scope = "CATEGORY" if rows and rows[0].item_group else "BRAND" if rows and rows[0].get("brand") else "ITEM"
		frappe.db.set_value(doc.doctype, name, "promotion_scope", scope)
