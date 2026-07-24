import copy
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt


QTY_FIELDS = {
	"actual_qty",
	"in_qty",
	"out_qty",
	"qty_after_transaction",
	"bal_qty",
	"opening_qty",
	"reserved_stock",
}
RATE_FIELDS = {"incoming_rate", "valuation_rate", "in_out_rate", "val_rate"}


def add_packing_columns(columns):
	columns = copy.deepcopy(columns)
	insert_at = 2
	columns[insert_at:insert_at] = [
		{"label": _("Row Type"), "fieldname": "row_type", "fieldtype": "Data", "width": 90},
		{"label": _("Barcode"), "fieldname": "barcode", "fieldtype": "Data", "width": 130},
		{"label": _("Packing UOM"), "fieldname": "packing_uom", "fieldtype": "Link", "options": "UOM", "width": 100},
		{"label": _("Conversion"), "fieldname": "conversion_factor", "fieldtype": "Float", "width": 95},
	]
	add_pack_breakdown_columns(columns)
	return columns


def add_pack_breakdown_columns(columns):
	column_labels = {
		"in_qty": _("In Packing"),
		"out_qty": _("Out Packing"),
		"qty_after_transaction": _("Balance Packing"),
		"bal_qty": _("Balance Packing"),
		"opening_qty": _("Opening Packing"),
		"reserved_stock": _("Reserved Packing"),
	}

	index = 0
	while index < len(columns):
		column = columns[index]
		fieldname = column.get("fieldname")
		if fieldname in column_labels:
			columns.insert(
				index + 1,
				{
					"label": column_labels[fieldname],
					"fieldname": f"{fieldname}_packing_display",
					"fieldtype": "Data",
					"width": 150,
				},
			)
			index += 1
		index += 1


def expand_rows_with_packings(rows):
	if not rows:
		return []

	item_codes = sorted({row.get("item_code") for row in rows if row.get("item_code")})
	packings_by_item = get_packings_by_item(item_codes)
	item_barcodes = get_item_barcodes(item_codes)

	expanded = []
	for row in rows:
		expanded.append(prepare_display_row(row, item_barcodes.get(row.get("item_code"))))

		for packing in packings_by_item.get(row.get("item_code"), []):
			expanded.append(prepare_display_row(row, packing.barcode, packing))

	return expanded


def get_packings_by_item(item_codes):
	if not item_codes:
		return {}

	packings = frappe.get_all(
		"Retail Packing Detail",
		filters={
			"parent": ("in", item_codes),
			"parenttype": "Item",
			"parentfield": "custom_retail_packing_detail",
		},
		fields=["parent", "idx", "barcode", "uom", "conversion_factor"],
		order_by="parent, idx",
	)

	packings_by_item = defaultdict(list)
	for packing in packings:
		packings_by_item[packing.parent].append(packing)

	return packings_by_item


def get_item_barcodes(item_codes):
	if not item_codes:
		return {}

	barcodes = frappe.get_all(
		"Item Barcode",
		filters={"parent": ("in", item_codes)},
		fields=["parent", "barcode", "uom", "idx"],
		order_by="parent, idx",
	)

	item_barcodes = {}
	for barcode in barcodes:
		item_barcodes.setdefault(barcode.parent, barcode.barcode)

	return item_barcodes


def prepare_display_row(row, barcode=None, packing=None):
	display_row = frappe._dict(copy.deepcopy(row))
	stock_uom = row.get("stock_uom")
	factor = flt(packing.conversion_factor) if packing else 1
	if not factor:
		factor = 1

	display_row.row_type = _("Packing") if packing else _("Item")
	display_row.barcode = barcode
	display_row.packing_uom = packing.uom if packing else stock_uom
	display_row.conversion_factor = factor
	set_pack_breakdown_values(display_row, factor, display_row.packing_uom, stock_uom)

	if packing:
		display_row.stock_uom = packing.uom
		for fieldname in QTY_FIELDS:
			if fieldname in display_row:
				display_row[fieldname] = flt(display_row[fieldname]) / factor

		for fieldname in RATE_FIELDS:
			if fieldname in display_row:
				display_row[fieldname] = flt(display_row[fieldname]) * factor

	return display_row


def set_pack_breakdown_values(row, factor, packing_uom, stock_uom):
	display_fields = [
		"in_qty",
		"out_qty",
		"qty_after_transaction",
		"bal_qty",
		"opening_qty",
		"reserved_stock",
	]

	for fieldname in display_fields:
		if fieldname in row:
			row[f"{fieldname}_packing_display"] = get_pack_breakdown(row.get(fieldname), factor, packing_uom, stock_uom)


def get_pack_breakdown(qty, factor, packing_uom, stock_uom):
	qty = flt(qty)
	factor = flt(factor)
	if not qty:
		return ""

	if not factor or factor == 1 or packing_uom == stock_uom:
		return f"{format_pack_qty(qty)} {stock_uom or ''}".strip()

	sign = -1 if qty < 0 else 1
	absolute_qty = abs(qty)
	full_packs = int(absolute_qty // factor)
	loose_qty = absolute_qty - (full_packs * factor)

	parts = []
	if full_packs:
		parts.append((full_packs, packing_uom))
	if loose_qty:
		parts.append((loose_qty, stock_uom))

	return join_pack_parts(parts, sign)


def join_pack_parts(parts, sign):
	if not parts:
		return ""

	prefix = "-" if sign < 0 else ""
	formatted_parts = [f"{format_pack_qty(value)} {uom}" for value, uom in parts]
	separator = " - " if sign < 0 else " + "
	return prefix + separator.join(formatted_parts)


def format_pack_qty(value):
	value = flt(value, 3)
	if value == int(value):
		return str(int(value))

	return str(value).rstrip("0").rstrip(".")
