"""Resolve invoice scans by packing barcode, using the exact ERPNext UOM."""

import frappe
from frappe.utils import flt
from erpnext.stock.get_item_details import get_item_details as standard_item_details
from erpnext.stock.utils import scan_barcode as standard_scan_barcode


def resolve_packing(barcode, item_code=None):
	filters = {"barcode": barcode.strip(), "parenttype": "Item"}
	if item_code:
		filters["parent"] = item_code
	rows = frappe.get_all("Retail Packing Detail", filters=filters,
		fields=["name", "parent", "uom", "conversion_factor", "disabled"], limit_page_length=2)
	if not rows:
		return None
	if len(rows) != 1:
		frappe.throw("Barcode matches multiple Retail Packing Detail rows.")
	packing = rows[0]
	frappe.get_doc("Item", packing.parent).check_permission("read")
	if packing.disabled or flt(packing.conversion_factor) <= 0:
		frappe.throw("Scanned packing is disabled or has no positive conversion factor.")
	return packing


@frappe.whitelist()
def scan_barcode(search_value, ctx=None):
	search_value = str(search_value or "").strip()
	packing = resolve_packing(search_value)
	if packing:
		return {"item_code": packing.parent, "barcode": search_value,
			"uom": packing.uom, "conversion_factor": packing.conversion_factor}
	# Exact identities always win, even if they resemble a printed scale label.
	item = frappe.db.get_value("Item", {"custom_barcode": search_value, "disabled": 0},
		["name", "stock_uom"], as_dict=True)
	if item:
		frappe.get_doc("Item", item.name).check_permission("read")
		return {"item_code": item.name, "barcode": search_value, "uom": item.stock_uom}
	standard = standard_scan_barcode(search_value, ctx=ctx)
	if standard:
		return standard
	from retail.domains.item.scale_sales import resolve_label
	return resolve_label(search_value) or {}


@frappe.whitelist()
def get_item_details(args, doc=None, for_validate=False, overwrite_warehouse=True):
	from retail.core_compat.runtime import install
	install()
	args = frappe._dict(frappe.parse_json(args))
	document = frappe.parse_json(doc) if doc else {}
	barcode = args.get("barcode")
	if args.get("doctype") == "Sales Invoice":
		# ERPNext clears row.barcode before this RPC, but serializes the scan field.
		for row in document.get("items", []):
			if row.get("name") == args.get("child_docname") and row.get("item_code") == args.get("item_code"):
				barcode = row.get("custom_barcode_scan") or barcode
				break
	packing = resolve_packing(barcode, args.get("item_code")) if barcode else None
	if packing and args.get("uom") and args.uom != packing.uom:
		packing = None
	if packing:
		args.update(uom=packing.uom)
		# Let ERPNext obtain the factor and price from Item UOM / Item Price.
		args.pop("conversion_factor", None)
	return standard_item_details(args, doc, for_validate, overwrite_warehouse)
