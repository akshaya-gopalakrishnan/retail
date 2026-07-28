from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint


DEFAULT_SCALE_PREFIX = "99"
DEFAULT_SCALE_FORMAT = "Prefix 99 - 2-5-5"
LEGACY_SCALE_BARCODE_SCRIPT = "generate unique scale barcode"


def is_scale_item(doc) -> bool:
	return bool(cint(doc.get("is_scale_item")) or cint(doc.get("custom_scale_item")))


def validate_scale_item(doc, method=None):
	if not is_scale_item(doc):
		return

	if not doc.get("scale_barcode_type") and doc.get("custom_scale_barcode_type"):
		doc.scale_barcode_type = normalize_barcode_type(doc.custom_scale_barcode_type)
	if not doc.get("custom_scale_barcode_type") and doc.get("scale_barcode_type"):
		doc.custom_scale_barcode_type = doc.scale_barcode_type.title().replace("_", " ")
	if not doc.get("scale_barcode_type"):
		doc.scale_barcode_type = "WEIGHT"

	if doc.scale_barcode_type not in ("WEIGHT", "PRICE", "QUANTITY"):
		frappe.throw(_("Scale Barcode Type must be WEIGHT, PRICE, or QUANTITY."))


def validate_unique_enabled_plu(doc):
	if not cint(doc.get("scale_enabled")):
		return

	duplicate = frappe.db.get_value(
		"Item",
		{
			"name": ["!=", doc.name],
			"scale_plu_number": doc.scale_plu_number,
			"scale_enabled": 1,
			"disabled": 0,
		},
		"name",
	)
	if duplicate:
		frappe.throw(_("PLU {0} is already used by scale item {1}.").format(doc.scale_plu_number, duplicate))


def validate_static_barcode_not_dynamic(doc):
	barcode = (doc.get("custom_barcode") or "").strip()
	if not barcode or not doc.get("scale_prefix"):
		return

	scale_format = frappe.db.get_value("Scale Barcode Format", doc.scale_format, ["total_length"], as_dict=True)
	if scale_format and len(barcode) == cint(scale_format.total_length) and barcode.startswith(doc.scale_prefix):
		frappe.throw(
			_("Do not save printed scale barcodes in the normal Barcode field. Use PLU and Scale Prefix instead.")
		)


def clean_digits(value, label):
	value = str(value or "").strip()
	if not re.fullmatch(r"\d+", value):
		frappe.throw(_("{0} must contain digits only.").format(_(label)))
	return value


def normalize_barcode_type(value):
	value = (value or "").strip().upper().replace(" ", "_")
	if value == "WEIGHT+UNIT_PRICE":
		return "WEIGHT"
	return value


def ensure_scale_item_setup():
	ensure_scale_item_fields()
	disable_legacy_scale_barcode_script()


def ensure_scale_item_fields():
	create_custom_fields(
		{
			"Item": [
				{
					"fieldname": "is_scale_item",
					"label": "Is Scale Item",
					"fieldtype": "Check",
					"insert_after": "custom_scale_barcode_type",
					"hidden": 1,
				},
				{
					"fieldname": "scale_enabled",
					"label": "Scale Enabled",
					"fieldtype": "Check",
					"default": "1",
					"insert_after": "is_scale_item",
					"hidden": 1,
				},
				{
					"fieldname": "scale_plu_number",
					"label": "PLU Number",
					"fieldtype": "Data",
					"insert_after": "scale_enabled",
					"hidden": 1,
					"in_standard_filter": 1,
				},
				{
					"fieldname": "scale_prefix",
					"label": "Scale Prefix",
					"fieldtype": "Data",
					"default": DEFAULT_SCALE_PREFIX,
					"insert_after": "scale_plu_number",
					"hidden": 1,
				},
				{
					"fieldname": "scale_barcode_type",
					"label": "Scale Barcode Type",
					"fieldtype": "Select",
					"options": "\nWEIGHT\nPRICE\nQUANTITY",
					"default": "WEIGHT",
					"insert_after": "scale_prefix",
					"hidden": 1,
				},
				{
					"fieldname": "scale_uom",
					"label": "Scale UOM",
					"fieldtype": "Link",
					"options": "UOM",
					"insert_after": "scale_barcode_type",
					"hidden": 1,
				},
				{
					"fieldname": "scale_expiry_days",
					"label": "Scale Expiry Days",
					"fieldtype": "Int",
					"insert_after": "scale_uom",
					"hidden": 1,
				},
				{
					"fieldname": "scale_format",
					"label": "Scale Format",
					"fieldtype": "Link",
					"options": "Scale Barcode Format",
					"default": DEFAULT_SCALE_FORMAT,
					"insert_after": "scale_expiry_days",
					"hidden": 1,
				},
				{
					"fieldname": "scale_unit_code",
					"label": "Scale Unit Code",
					"fieldtype": "Data",
					"default": "1",
					"insert_after": "scale_format",
					"hidden": 1,
				},
			],
		},
		update=True,
	)


def disable_legacy_scale_barcode_script():
	if frappe.db.exists("Client Script", LEGACY_SCALE_BARCODE_SCRIPT):
		frappe.db.set_value(
			"Client Script",
			LEGACY_SCALE_BARCODE_SCRIPT,
			"enabled",
			0,
			update_modified=False,
		)
		frappe.clear_cache(doctype="Item")
