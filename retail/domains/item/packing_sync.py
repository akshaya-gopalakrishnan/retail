"""Keep Item UOM and barcode rows aligned with Retail packing rows."""

from __future__ import annotations

import frappe


LEGACY_UOM_BARCODE_SCRIPT = "UOM&Barcode table sync Retail Packing Detail"


def sync_uoms_and_barcodes(doc, method=None):
	if isinstance(doc, str):
		doc = frappe.get_doc("Item", doc)

	default_uom = doc.get("stock_uom") or "Nos"
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
