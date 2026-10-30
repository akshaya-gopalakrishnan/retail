"""Item-master scale labels: 7-digit identity, fixed payload, trailing check digit.

The trailing digit is excluded, not validated: the scale's checksum algorithm
has not been specified. Monetary payloads always contain five cents digits.
"""

import frappe
from frappe import _
from frappe.utils import flt


PAYLOAD_LENGTHS = {"WEIGHT": 5, "QUANTITY": 5, "PRICE": 5,
	"WEIGHT+UPRICE": 10, "WEIGHT+TOTPRICE": 10}


def decode_label(barcode, barcode_type, uom):
	barcode_type = (barcode_type or "").upper().replace(" ", "")
	barcode_type = {"WEIGHT+UNITPRICE": "WEIGHT+UPRICE",
		"WEIGHT+UNIT_PRICE": "WEIGHT+UPRICE"}.get(barcode_type, barcode_type)
	if barcode_type not in PAYLOAD_LENGTHS:
		frappe.throw(_("Select a Scale Barcode Type in the Item master."))
	length = 8 + PAYLOAD_LENGTHS[barcode_type]
	if len(barcode) != length or not barcode.isascii() or not barcode.isdigit():
		frappe.throw(_("This item's scale barcode must contain {0} digits.").format(length))
	payload = barcode[7:-1]
	result = {"scale_barcode_type": barcode_type, "master_barcode": barcode[:7],
		"barcode": barcode, "uom": uom, "scale_qty": None,
		"scale_rate": None, "scale_amount": None}
	if barcode_type == "QUANTITY":
		result["scale_qty"] = int(payload)
	elif barcode_type == "PRICE":
		result["scale_amount"] = int(payload) / 100
	else:
		# The scale encodes grams. Keep grams for a Gram sales UOM.
		divisor = 1000 if (uom or "").strip().upper() in ("KG", "KGS", "KILOGRAM", "KILOGRAMS") else 1
		result["scale_qty"] = int(payload[:5]) / divisor
		if barcode_type == "WEIGHT+UPRICE":
			result["scale_rate"] = int(payload[5:]) / 100
		elif barcode_type == "WEIGHT+TOTPRICE":
			result["scale_amount"] = int(payload[5:]) / 100
	if result["scale_qty"] is not None and result["scale_qty"] <= 0:
		frappe.throw(_("Scale quantity must be greater than zero."))
	return result


def resolve_label(barcode):
	barcode = str(barcode or "").strip()
	if len(barcode) <= 7 or not barcode[:7].isascii() or not barcode[:7].isdigit():
		return None
	item = frappe.db.get_value("Item", {"custom_barcode": barcode[:7],
		"custom_scale_item": 1, "disabled": 0, "is_sales_item": 1},
		["name", "stock_uom", "scale_uom", "custom_scale_barcode_type"], as_dict=True)
	if not item:
		return None
	frappe.get_doc("Item", item.name).check_permission("read")
	return {"item_code": item.name, **decode_label(barcode,
		item.custom_scale_barcode_type, item.scale_uom or item.stock_uom)}


def sale_values(label, master_rate):
	"""Use the transaction's rate; retain full precision for derived quantities."""
	qty, rate, amount = label["scale_qty"], label["scale_rate"], label["scale_amount"]
	rate = flt(master_rate) if rate is None else rate
	if qty is None:
		qty = amount / rate if rate else 1
		if not rate:
			rate = amount
	elif amount is not None:
		rate = amount / qty
	elif not rate:
		frappe.throw(_("Enter a selling rate for this scale item."))
	return {"qty": qty, "rate": rate, "amount": amount if amount is not None else qty * rate}


def prepare_precision(doc, method=None):
	"""Keep derived rates/quantities through ERPNext's ordinary rounding.

	Precision caches belong to this document only. No global field precision or
	stored quantity/rate is changed, and no saved sale is decoded/repriced.
	"""
	if doc.docstatus == 2 or (doc.get_doc_before_save() and doc.get_doc_before_save().docstatus != 0):
		return
	if doc.get("pos_sync_source") or doc.get("is_consolidated"):
		return  # Completed external POS facts already own their quantity and price.
	from retail.domains.item.packing_scan import scan_barcode
	for row in doc.get("items", []):
		row.flags.pop("retail_scale_price", None)
		barcode = row.get("barcode") or row.get("custom_barcode_scan") or ""
		if len(barcode) not in (13, 18) or not barcode.isascii() or not barcode.isdigit():
			continue
		label = scan_barcode(barcode)
		if not label.get("scale_barcode_type") or label["item_code"] != row.item_code:
			continue
		row.flags.retail_scale_price = label["scale_rate"] is not None or label["scale_amount"] is not None
		# Parent.round_floats_in uses the parent's child-table precision cache.
		doc.precision("rate", "items")
		for field in ("qty", "rate", "price_list_rate"):
			doc._precision["items"][field] = 9
		for item in doc.items:
			item.precision("rate")
			for field in ("qty", "rate", "price_list_rate"):
				item._precision["main"][field] = 9
