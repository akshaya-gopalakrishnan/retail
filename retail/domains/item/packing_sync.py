"""Keep Item UOM and barcode rows aligned with Retail packing rows."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

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
	map_packing_uoms(doc)
	fill_packing_identifiers(doc)
	# Preserve existing conversions used by historical documents and other workflows.
	conversions = {}
	for row in doc.get("uoms") or []:
		if row.uom in conversions:
			frappe.throw(f"Duplicate Item UOM {row.uom}; resolve it before saving.")
		conversions[row.uom] = row.conversion_factor
	conversions[default_uom] = 1
	for row in doc.get("custom_retail_packing_detail") or []:
		if row.get("uom"):
			if row.uom in conversions and Decimal(str(conversions[row.uom])) != Decimal(str(row.conversion_factor)):
				frappe.throw(f"Item UOM {row.uom} already has a different conversion factor.")
			conversions[row.uom] = row.conversion_factor
	doc.set("uoms", [])
	for uom, factor in conversions.items():
		doc.append("uoms", {"uom": uom, "conversion_factor": factor})

	doc.set("barcodes", [])
	seen_barcodes = {}

	if doc.get("custom_barcode"):
		barcode = doc.custom_barcode.strip()
		if barcode:
			doc.append("barcodes", {"barcode": barcode, "uom": default_uom})
			seen_barcodes[barcode] = default_uom

	for row in doc.get("custom_retail_packing_detail") or []:
		if not row.get("barcode"):
			continue

		barcode = row.barcode.strip()
		if barcode in seen_barcodes and seen_barcodes[barcode] != row.uom:
			frappe.throw(f"Barcode {barcode} is assigned to different packing UOMs.")
		if barcode and barcode not in seen_barcodes:
			doc.append("barcodes", {"barcode": barcode, "uom": row.get("uom") or default_uom})
			seen_barcodes[barcode] = row.uom


def map_packing_uoms(doc):
	"""Keep the existing uom field authoritative for every downstream consumer."""
	seen = set()
	for row in doc.get("custom_retail_packing_detail") or []:
		base = (row.get("packing_uom") or row.get("uom") or "").strip()
		if not base:
			frappe.throw("Each packing row requires a UOM.")
		try:
			factor = Decimal(str(row.get("conversion_factor")))
		except (InvalidOperation, ValueError):
			frappe.throw("Packing conversion factor must be positive.")
		if not factor.is_finite() or factor <= 0:
			frappe.throw("Packing conversion factor must be positive.")
		suffix = format(factor, "f")
		if "." in suffix:
			suffix = suffix.rstrip("0").rstrip(".")
		# Accept already-qualified legacy rows without adding the suffix twice.
		if not row.get("packing_uom") and base.endswith("-" + suffix):
			base = base[:-(len(suffix) + 1)]
		uom = base if base == doc.get("stock_uom") and factor == 1 else f"{base}-{suffix}"
		if uom == doc.get("stock_uom") and factor != 1:
			frappe.throw("Stock UOM must have conversion factor 1.")
		if uom in seen:
			frappe.throw(f"Duplicate packing UOM {uom}; use one packing row per UOM and factor.")
		seen.add(uom)
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom,
				"enabled": 1, "must_be_whole_number": frappe.db.get_value(
					"UOM", base, "must_be_whole_number") or 0}).insert(
					ignore_permissions=True, ignore_if_duplicate=True)
		row.packing_uom = base
		row.uom = uom


def validate_packing_uoms(doc, method=None):
	"""Reject conflicts introduced by ERPNext's global UOM conversion defaults."""
	conversions = {row.uom: row.conversion_factor for row in doc.get("uoms") or []}
	for row in doc.get("custom_retail_packing_detail") or []:
		if Decimal(str(conversions.get(row.uom))) != Decimal(str(row.conversion_factor)):
			frappe.throw(f"ERPNext conversion for {row.uom} differs from its packing factor.")


def fill_packing_identifiers(doc):
	item_code = doc.get("item_code") or doc.get("name")
	item_name = doc.get("item_name") or item_code
	for row in doc.get("custom_retail_packing_detail") or []:
		if not row.get("packing_code"):
			row.packing_code = make_packing_code(item_code, row.get("uom"), row.get("idx"))
		if not row.get("packing_name") or is_auto_packing_name(row.get("packing_name"), item_name, row.get("packing_uom") or row.get("uom")):
			row.packing_name = make_packing_name(item_name, row.get("packing_uom") or row.get("uom"), row.get("conversion_factor"))


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
