"""Selected transaction-row barcodes, without rewriting completed documents."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

PARENTS = (
	"Quotation", "Sales Order", "Sales Invoice", "POS Invoice", "Delivery Note",
	"Purchase Order", "Purchase Receipt", "Purchase Invoice", "Material Request",
	"Stock Entry", "Stock Reconciliation", "Supplier Quotation", "Request for Quotation",
)


def install():
	fields = {}
	for parent in PARENTS:
		for table in frappe.get_meta(parent).get_table_fields():
			meta = frappe.get_meta(table.options)
			code = meta.get_field("item_code")
			if not code or code.options != "Item" or not meta.has_field("item_name"):
				continue
			fields[table.options] = [dict(
				fieldname="custom_item_barcode", label="Barcode", fieldtype="Data",
				insert_after="item_name", read_only=1, in_list_view=1, columns=2,
				fetch_from="",
			), dict(
				fieldname="custom_packing_detail", label="Selected Packing", fieldtype="Data",
				insert_after="custom_item_barcode", hidden=1, read_only=1, no_copy=0,
			)]
	create_custom_fields(fields)


def resolve(rows, items, packings):
	"""Prefer exact packing identity, then a scanned barcode, then matching UOM."""
	result = {}
	for row in rows:
		code = row.get("item_code")
		if code not in items:
			continue
		choices = [p for p in packings if p.parent == code and p.uom == row.get("uom")]
		selected = next((p for p in choices if p.name == row.get("custom_packing_detail")), None)
		if selected:
			barcode = selected.barcode or ""
		elif row.get("barcode"):
			barcode = row["barcode"]
		elif len(choices) == 1 and row.get("uom") != items[code].stock_uom:
			barcode = choices[0].barcode or ""
		elif row.get("uom") in (None, "", items[code].stock_uom):
			barcode = items[code].custom_barcode or ""
		else:
			barcode = row.get("custom_item_barcode") or ""
		result[row.get("name")] = barcode
	return result


@frappe.whitelist()
def get_barcodes(rows):
	rows = frappe.parse_json(rows) if isinstance(rows, str) else rows
	codes = list({r.get("item_code") for r in rows if r.get("item_code")})
	if not codes:
		return {}
	items = frappe.get_list("Item", filters={"name": ["in", codes]},
		fields=["name", "stock_uom", "custom_barcode"], limit_page_length=len(codes))
	allowed = [item.name for item in items]
	packings = frappe.get_all("Retail Packing Detail", filters={
		"parent": ["in", allowed], "parenttype": "Item",
	}, fields=["name", "parent", "uom", "barcode"]) if allowed else []
	return resolve(rows, {item.name: item for item in items}, packings)


def validate(doc, method=None):
	if doc.docstatus != 0:
		return
	for table in doc.meta.get_table_fields():
		rows = [row for row in doc.get(table.fieldname) or []
			if row.meta.has_field("custom_item_barcode") and row.get("item_code")]
		if not rows:
			continue
		barcodes = get_barcodes([row.as_dict() for row in rows])
		for row in rows:
			if row.name in barcodes:
				row.custom_item_barcode = barcodes[row.name]
