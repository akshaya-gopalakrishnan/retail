"""Keep Item UOM and barcode rows aligned with Retail packing rows."""

from __future__ import annotations

import frappe

from retail.retail_app.doctype.retail_packing_detail.retail_packing_detail import (
	is_auto_packing_name,
	make_packing_code,
	make_packing_name,
)


LEGACY_UOM_BARCODE_SCRIPT = "UOM&Barcode table sync Retail Packing Detail"


def sync_uoms_and_barcodes(doc, method=None):
	if isinstance(doc, str):
		doc = frappe.get_doc("Item", doc)

	default_uom = doc.get("stock_uom") or "Nos"
	fill_packing_identifiers(doc)
	doc.set("uoms", [])
	doc.append("uoms", {"uom": default_uom, "conversion_factor": 1})

	seen_uoms = {default_uom}
	for row in doc.get("custom_retail_packing_detail") or []:
		if row.get("uom") and row.uom not in seen_uoms:
			doc.append(
				"uoms",
				{"uom": row.uom, "conversion_factor": row.get("conversion_factor") or 1},
			)
			seen_uoms.add(row.uom)

	doc.set("barcodes", [])
	seen_barcodes = set()

	if doc.get("custom_barcode"):
		barcode = doc.custom_barcode.strip()
		if barcode:
			doc.append("barcodes", {"barcode": barcode, "uom": default_uom})
			seen_barcodes.add(barcode)

	for row in doc.get("custom_retail_packing_detail") or []:
		if not row.get("barcode"):
			continue

		barcode = row.barcode.strip()
		if barcode and barcode not in seen_barcodes:
			doc.append("barcodes", {"barcode": barcode, "uom": row.get("uom") or default_uom})
			seen_barcodes.add(barcode)


def fill_packing_identifiers(doc):
	item_code = doc.get("item_code") or doc.get("name")
	item_name = doc.get("item_name") or item_code
	for row in doc.get("custom_retail_packing_detail") or []:
		if not row.get("packing_code"):
			row.packing_code = make_packing_code(item_code, row.get("uom"), row.get("idx"))
		if not row.get("packing_name") or is_auto_packing_name(row.get("packing_name"), item_name, row.get("uom")):
			row.packing_name = make_packing_name(item_name, row.get("uom"), row.get("conversion_factor"))


def disable_legacy_uom_barcode_script():
	if frappe.db.exists("Server Script", LEGACY_UOM_BARCODE_SCRIPT):
		frappe.db.set_value(
			"Server Script",
			LEGACY_UOM_BARCODE_SCRIPT,
			"disabled",
			1,
			update_modified=False,
		)
		frappe.cache.delete_value("server_script_map")
