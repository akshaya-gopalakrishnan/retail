"""One server round trip for a Purchase Receipt or Purchase Invoice line.

The desk used to resolve a barcode, load the item, price it, then price the UOM,
tax, VAT and selling rate as separate HTTP calls. Each call waited on the trip to
the server. This method does that work once and returns the row.
"""

import frappe
from frappe.utils import cint, flt

from retail.domains.item.packing_scan import get_item_details, scan_barcode
from retail.domains.purchase.selling_price import (
	get_item_selling_vat_rate,
	get_standard_selling_rate,
)
from retail.domains.transactions.vat import (
	get_transaction_item_vat_rate,
	get_transaction_vat_tax_rows,
)

PURCHASE_DOCTYPES = ("Purchase Receipt", "Purchase Invoice")
ITEM_FIELDS = (
	"name",
	"item_name",
	"stock_uom",
	"purchase_uom",
	"has_serial_no",
	"has_batch_no",
	"disabled",
	"is_purchase_item",
)
ROW_SKIP = {
	"name",
	"idx",
	"doctype",
	"parent",
	"parentfield",
	"parenttype",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"docstatus",
}


@frappe.whitelist()
def fill_line(doc, item_code=None, barcode=None, uom=None, search_value=None, child_name=None, qty=1):
	document = frappe.parse_json(doc) or {}
	parent = document.get("doctype")
	if parent not in PURCHASE_DOCTYPES:
		frappe.throw("Purchase line fill is available for purchase documents only")
	if cint(document.get("docstatus") or 0) != 0:
		frappe.throw("Submitted documents cannot be changed")
	_check_parent_permission(document)

	resolved = {}
	scanned = str(search_value or "").strip()
	if not item_code and (scanned or barcode):
		resolved = scan_barcode(scanned or barcode) or {}
		if resolved.get("scale_barcode_type"):
			return resolved
		if resolved.get("warehouse") and not resolved.get("item_code"):
			return resolved
		item_code = resolved.get("item_code")
		uom = uom or resolved.get("uom")
		barcode = barcode or scanned or resolved.get("barcode")
	if not item_code:
		return {}

	item = _item_summary(item_code)
	if not item or item.disabled or item.is_purchase_item == 0:
		return {}
	uom = uom or resolved.get("uom") or item.purchase_uom or item.stock_uom
	barcode = barcode or resolved.get("barcode") or ""
	child_doctype = parent + " Item"
	details = get_item_details(_detail_args(
		document, item, item_code, barcode, uom, child_name, child_doctype, qty,
	), document)
	details = _plain_row(details)
	details["item_code"] = item_code
	details["uom"] = details.get("uom") or uom
	if barcode:
		details["barcode"] = barcode
	actual_uom = details.get("uom") or uom
	selling_rate = get_standard_selling_rate(item_code, uom=actual_uom)
	selling_vat_rate = get_item_selling_vat_rate(item_code)
	purchase_vat_rate = get_transaction_item_vat_rate(
		item_code,
		child_doctype=child_doctype,
		parent_doctype=parent,
		transaction_type=document.get("transaction_type"),
		item_tax_template=details.get("item_tax_template"),
	)
	_apply_to_child(document, child_name, child_doctype, details, qty)
	return {
		"item_code": item_code,
		"uom": actual_uom,
		"barcode": barcode or details.get("barcode") or "",
		"batch_no": resolved.get("batch_no"),
		"serial_no": resolved.get("serial_no"),
		"conversion_factor": details.get("conversion_factor"),
		"details": details,
		"item": item,
		"selling_rate": selling_rate,
		"selling_vat_rate": selling_vat_rate,
		"purchase_vat_rate": purchase_vat_rate,
		"vat_tax": _vat_tax(document),
	}


def _check_parent_permission(document):
	name = str(document.get("name") or "")
	new_doc = document.get("__islocal") or name.startswith("new-") or not name
	frappe.has_permission(document.get("doctype"), "create" if new_doc else "write", throw=True)


def _item_summary(item_code):
	if not frappe.has_permission("Item", "read", item_code):
		frappe.throw("Not permitted to read this Item", frappe.PermissionError)
	fields = list(ITEM_FIELDS)
	if frappe.get_meta("Item").has_field("custom_barcode"):
		fields.append("custom_barcode")
	return frappe.db.get_value("Item", item_code, fields, as_dict=True)


def _detail_args(document, item, item_code, barcode, uom, child_name, child_doctype, qty):
	# Keep the scanned barcode and packing UOM. The desk item_code handler clears
	# both before get_item_details, which prices the stock UOM and then prices again.
	parent = document.get("doctype")
	return {
		"item_code": item_code,
		"barcode": barcode,
		"serial_no": None,
		"batch_no": None,
		"set_warehouse": document.get("set_warehouse"),
		"warehouse": document.get("set_warehouse"),
		"supplier": document.get("supplier"),
		"currency": document.get("currency"),
		"conversion_rate": document.get("conversion_rate"),
		"price_list": document.get("buying_price_list"),
		"price_list_currency": document.get("price_list_currency"),
		"plc_conversion_rate": document.get("plc_conversion_rate"),
		"company": document.get("company"),
		"is_internal_supplier": document.get("is_internal_supplier"),
		"update_stock": 1 if parent == "Purchase Receipt" else cint(document.get("update_stock")),
		"ignore_pricing_rule": document.get("ignore_pricing_rule"),
		"doctype": parent,
		"name": document.get("name"),
		"project": document.get("project"),
		"qty": flt(qty) or 1,
		"conversion_factor": 0,
		"uom": uom,
		"stock_uom": item.stock_uom,
		"tax_category": document.get("tax_category"),
		"child_doctype": child_doctype,
		"child_docname": child_name,
		"cost_center": document.get("cost_center"),
		"is_return": cint(document.get("is_return")),
	}


def _plain_row(details):
	row = {}
	for key, value in dict(details or {}).items():
		if key in ROW_SKIP or value is None:
			continue
		row[key] = value
	return row


def _apply_to_child(document, child_name, child_doctype, details, qty):
	items = document.setdefault("items", [])
	child = next((row for row in items if child_name and row.get("name") == child_name), None)
	if child is None:
		child = {
			"doctype": child_doctype,
			"name": child_name or frappe.generate_hash(length=10),
			"parentfield": "items",
			"parenttype": document.get("doctype"),
			"idx": len(items) + 1,
		}
		items.append(child)
	child.update(details)
	child["qty"] = flt(qty) or child.get("qty") or 1
	child["doctype"] = child_doctype
	child["parentfield"] = "items"
	child["parenttype"] = document.get("doctype")


def _vat_tax(document):
	# Tax rows are part of the same response. A failure here still leaves the
	# priced line usable; the form's existing VAT refresh remains the fallback.
	try:
		return get_transaction_vat_tax_rows(document)
	except Exception:
		frappe.logger("retail").warning("Purchase line VAT bundle failed", exc_info=True)
		return None
