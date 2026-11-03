"""Backfill group/row quantities without changing existing offer meanings."""
import frappe
from frappe.utils import flt, now_datetime
from retail.promotions.buy_get_groups import row_values


def execute():
	frappe.reload_doc("retail_app", "doctype", "buy_x_get_y_item")
	frappe.reload_doc("retail_app", "doctype", "buy_x_get_y_promotion")
	for name in frappe.get_all("Buy X Get Y Promotion", pluck="name"):
		doc = frappe.get_doc("Buy X Get Y Promotion", name)
		changed = False
		for row in doc.products:
			# Newly added Float columns may load as 0 rather than NULL.
			if not flt(row.get("qty")):
				row.qty = doc.buy_qty if row.add_to == "Buy Item" else doc.free_qty
			values = row_values(doc, row)
			stored = frappe.db.get_value(row.doctype, row.name, ["group_no", "qty"], as_dict=True)
			if stored.group_no == values["group_no"] and flt(stored.qty) == values["qty"]:
				continue
			frappe.db.set_value(row.doctype, row.name, values, update_modified=False)
			changed = True
		if changed:
			# Existing incremental API clients must download the patched rows.
			frappe.db.set_value(doc.doctype, name, "modified", now_datetime(), update_modified=False)
			frappe.clear_document_cache(doc.doctype, name)
			from retail.promotions.history import record_revision
			record_revision(frappe.get_doc(doc.doctype, name))
