from __future__ import annotations

import re
import secrets

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint


DEFAULT_SCALE_PREFIX = "99"
DEFAULT_SCALE_FORMAT = "Prefix 99 - 2-5-5"
LEGACY_SCALE_BARCODE_SCRIPT = "generate unique scale barcode"
VISIBLE_SCALE_TYPE_OPTIONS = "\nPrice\nWeight\nQuantity\nWeight+UPrice\nWeight+TotPrice"
BARCODE_GENERATION_MAX_ATTEMPTS = 200


def is_scale_item(doc) -> bool:
	if doc.get("custom_scale_item") is not None:
		return bool(cint(doc.get("custom_scale_item")))
	return bool(cint(doc.get("is_scale_item")))


def ensure_item_barcode(doc, method=None):
	"""Ensure Item custom barcode is always populated and unique."""
	barcode = (doc.get("custom_barcode") or "").strip()
	if is_scale_item(doc) and doc.get("__retail_scale_barcode_preview") == barcode:
		barcode = ""
		doc.__retail_scale_barcode_preview = None
	previous = doc.get_doc_before_save()
	if previous and is_scale_item(previous) != is_scale_item(doc):
		if barcode == (previous.get("custom_barcode") or "").strip():
			barcode = ""

	if barcode:
		existing = frappe.db.exists("Item", {"custom_barcode": barcode, "name": ["!=", doc.get("name") or ""]})
		if existing:
			frappe.throw(_("Barcode {0} is already used by item {1}.").format(barcode, existing))
		doc.custom_barcode = barcode
		return

	doc.custom_barcode = get_unique_item_barcode(doc.get("name"), scale_item=is_scale_item(doc))


def get_unique_item_barcode(exclude_name=None, scale_item=False):
	if scale_item:
		return get_next_scale_barcode()

	for _ in range(BARCODE_GENERATION_MAX_ATTEMPTS):
		barcode = generate_random_barcode(scale_item=scale_item)

		exists = frappe.db.exists("Item", {"custom_barcode": barcode, "name": ["!=", exclude_name or ""]})
		item_barcode_exists = frappe.db.exists("Item Barcode", {"barcode": barcode})
		if not exists and not item_barcode_exists:
			return barcode

	raise frappe.ValidationError("Unable to generate unique barcode. Please retry.")


def get_next_scale_barcode():
	"""Allocate the lowest unused scale number, holding the lock until commit/rollback."""
	# A stable database row serializes allocations across workers. Locking reads
	# below see committed barcodes even if this transaction already has a snapshot.
	frappe.db.sql("select name from `tabDocType` where name = 'Item' for update")
	used = set()
	for table, field in (("tabItem", "custom_barcode"), ("tabItem Barcode", "barcode")):
		rows = frappe.db.sql(
			f"select `{field}` from `{table}` "
			f"where `{field}` like '99%' and char_length(`{field}`) = 7 for update"
		)
		used.update(row[0] for row in rows)
	for number in range(1, 100000):
		barcode = f"99{number:05d}"
		if barcode not in used:
			return barcode
	raise frappe.ValidationError("All scale barcode numbers from 9900001 to 9999999 are in use.")


def generate_random_barcode(scale_item=False):
	if scale_item:
		return f"99{secrets.randbelow(10**5):05d}"
	return str(10**12 + secrets.randbelow(9 * 10**12))


def validate_scale_item(doc, method=None):
	if not is_scale_item(doc):
		doc.is_scale_item = 0
		doc.scale_enabled = 0
		doc.custom_scale_barcode_type = None
		doc.scale_barcode_type = None
		return

	barcode_type = doc.get("custom_scale_barcode_type") or doc.get("scale_barcode_type") or "WEIGHT"
	doc.scale_barcode_type = normalize_barcode_type(barcode_type)
	doc.custom_scale_barcode_type = display_barcode_type(barcode_type)

	if doc.scale_barcode_type not in ("WEIGHT", "PRICE", "QUANTITY"):
		frappe.throw(_("Scale Barcode Type must be Price, Weight, Quantity, Weight+UPrice or Weight+TotPrice."))
	doc.is_scale_item = 1
	doc.scale_enabled = 1


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
	if value in ("WEIGHT+UNIT_PRICE", "WEIGHT+UNITPRICE", "WEIGHT+UPRICE", "WEIGHT+TOTPRICE"):
		return "WEIGHT"
	return value


def display_barcode_type(value):
	value = (value or "").strip().upper().replace(" ", "_")
	return {
		"PRICE": "Price", "WEIGHT": "Weight", "QUANTITY": "Quantity",
		"WEIGHT+UNIT_PRICE": "Weight+UPrice", "WEIGHT+UNITPRICE": "Weight+UPrice",
		"WEIGHT+UPRICE": "Weight+UPrice", "WEIGHT+TOTPRICE": "Weight+TotPrice",
	}.get(value, value)


def ensure_scale_item_setup():
	ensure_visible_scale_fields()
	ensure_scale_item_fields()
	disable_legacy_scale_barcode_script()


def ensure_visible_scale_fields():
	if frappe.db.exists("Custom Field", "Item-custom_scale_item"):
		frappe.db.set_value("Custom Field", "Item-custom_scale_item", "hidden", 0, update_modified=False)
	if frappe.db.exists("Custom Field", "Item-custom_scale_barcode_type"):
		frappe.db.set_value(
			"Custom Field",
			"Item-custom_scale_barcode_type",
			{
				"hidden": 0,
				"options": VISIBLE_SCALE_TYPE_OPTIONS,
				"depends_on": "eval:doc.custom_scale_item == 1",
			},
			update_modified=False,
		)


def ensure_scale_item_fields():
	scale_format_field = {
		"fieldname": "scale_format",
		"label": "Scale Format",
		"fieldtype": "Link",
		"options": "Scale Barcode Format",
		"default": DEFAULT_SCALE_FORMAT,
		"insert_after": "scale_expiry_days",
		"hidden": 1,
	}
	existing_scale_format_type = frappe.db.get_value("Custom Field", "Item-scale_format", "fieldtype")
	if existing_scale_format_type == "Data":
		scale_format_field.pop("options")
		scale_format_field["fieldtype"] = "Data"

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
					"in_standard_filter": 0,
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
				scale_format_field,
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
