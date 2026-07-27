from __future__ import annotations

from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils import cint, flt


@dataclass
class ScaleBarcodeResult:
	item_code: str
	plu: str
	qty: float
	weight: float
	rate: float
	amount: float
	uom: str
	prefix: str
	barcode_type: str
	value: float


def parse_scale_barcode(barcode, price_list=None, currency=None):
	barcode = normalize_barcode(barcode)
	formats = get_matching_formats(barcode)
	if not formats:
		return None

	last_error = None
	for fmt in formats:
		try:
			return parse_with_format(barcode, fmt, price_list=price_list, currency=currency)
		except Exception as exc:
			last_error = exc

	if last_error:
		raise last_error
	return None


def parse_with_format(barcode, fmt, price_list=None, currency=None):
	if len(barcode) != cint(fmt.total_length):
		frappe.throw(_("Invalid scale barcode length."))

	prefix = slice_value(barcode, fmt.prefix_start, fmt.prefix_length)
	if prefix != fmt.prefix:
		frappe.throw(_("Invalid scale barcode prefix."))

	if cint(fmt.check_digit_enabled):
		validate_check_digit(barcode, fmt.check_digit_method)

	plu = slice_value(barcode, fmt.plu_start, fmt.plu_length)
	raw_value = slice_value(barcode, fmt.value_start, fmt.value_length)
	value = flt(raw_value) / (10 ** cint(fmt.decimal_places))
	item = get_scale_item(plu, prefix)
	barcode_type = (item.scale_barcode_type or fmt.value_type or "WEIGHT").upper()
	uom = item.scale_uom or item.stock_uom
	rate = get_item_rate(item.name, price_list=price_list, uom=uom, currency=currency)

	if barcode_type == "WEIGHT":
		qty = value
		weight = value
		amount = qty * rate
	elif barcode_type == "PRICE":
		amount = value
		qty = amount / rate if rate else 0
		weight = qty if uom == item.stock_uom else 0
	elif barcode_type == "QUANTITY":
		qty = value
		weight = 0
		amount = qty * rate
	else:
		frappe.throw(_("Unsupported scale barcode type {0}.").format(barcode_type))

	return ScaleBarcodeResult(
		item_code=item.name,
		plu=plu,
		qty=flt(qty),
		weight=flt(weight),
		rate=flt(rate),
		amount=flt(amount),
		uom=uom,
		prefix=prefix,
		barcode_type=barcode_type,
		value=value,
	)


def normalize_barcode(barcode):
	barcode = str(barcode or "").strip()
	if not barcode.isdigit():
		frappe.throw(_("Barcode must contain digits only."))
	return barcode


def get_matching_formats(barcode):
	formats = frappe.get_all(
		"Scale Barcode Format",
		filters={"enabled": 1, "total_length": len(barcode)},
		fields=[
			"name",
			"prefix",
			"total_length",
			"prefix_start",
			"prefix_length",
			"plu_start",
			"plu_length",
			"value_start",
			"value_length",
			"value_type",
			"decimal_places",
			"check_digit_enabled",
			"check_digit_method",
		],
		order_by="modified desc",
		limit_page_length=0,
	)
	return [fmt for fmt in formats if barcode.startswith(fmt.prefix or "")]


def slice_value(barcode, start, length):
	start = cint(start)
	length = cint(length)
	if start < 1 or length < 1:
		frappe.throw(_("Scale barcode format positions must start from 1."))
	return barcode[start - 1 : start - 1 + length]


def validate_check_digit(barcode, method):
	method = (method or "EAN13").upper()
	if method != "EAN13":
		frappe.throw(_("Unsupported check digit method {0}.").format(method))
	expected = ean13_check_digit(barcode[:-1])
	if expected != barcode[-1]:
		frappe.throw(_("Invalid scale barcode check digit."))


def ean13_check_digit(body):
	total = 0
	for index, digit in enumerate(reversed(body)):
		total += cint(digit) * (3 if index % 2 == 0 else 1)
	return str((10 - (total % 10)) % 10)


def get_scale_item(plu, prefix):
	item = frappe.db.get_value(
		"Item",
		{
			"scale_plu_number": plu,
			"scale_prefix": prefix,
			"scale_enabled": 1,
			"disabled": 0,
		},
		["name", "stock_uom", "scale_uom", "scale_barcode_type"],
		as_dict=True,
	)
	if not item:
		frappe.throw(_("Unknown scale PLU {0}.").format(plu))
	return item


def get_item_rate(item_code, price_list=None, uom=None, currency=None):
	filters = {"item_code": item_code, "selling": 1}
	if price_list:
		filters["price_list"] = price_list
	if uom:
		filters["uom"] = ["in", [uom, None, ""]]
	if currency:
		filters["currency"] = currency

	price = frappe.db.get_value(
		"Item Price",
		filters,
		"price_list_rate",
		order_by="valid_from desc, modified desc",
	)
	if price is None:
		price = frappe.db.get_value("Item", item_code, "standard_rate")
	return flt(price)
