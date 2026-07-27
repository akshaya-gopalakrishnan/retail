from __future__ import annotations

import csv
import io

import frappe
from frappe import _
from frappe.utils import flt


DEFAULT_EXPERTS_TEMPLATE = "EXPERTS weighing.txt"


def export_scale_items(template=None, price_list=None):
	template_doc = get_template(template)
	rows = get_scale_rows(price_list=price_list)
	buffer = io.StringIO()
	writer = csv.writer(buffer, lineterminator="\n")
	writer.writerow([column.output_label for column in template_doc.columns])
	for row in rows:
		writer.writerow([get_column_value(row, column) for column in template_doc.columns])
	return buffer.getvalue()


def get_template(template=None):
	name = template or DEFAULT_EXPERTS_TEMPLATE
	if not frappe.db.exists("Scale Export Template", name):
		frappe.throw(_("Scale Export Template {0} was not found.").format(name))
	return frappe.get_doc("Scale Export Template", name)


def get_scale_rows(price_list=None):
	items = frappe.get_all(
		"Item",
		filters={"scale_enabled": 1, "disabled": 0},
		fields=[
			"name",
			"item_code",
			"item_name",
			"stock_uom",
			"scale_plu_number",
			"scale_prefix",
			"scale_uom",
			"scale_expiry_days",
			"scale_unit_code",
			"scale_barcode_type",
		],
		order_by="scale_plu_number asc",
		limit_page_length=0,
	)
	for item in items:
		item.unit_price = get_item_price(item.name, price_list=price_list, uom=item.scale_uom or item.stock_uom)
		item.scale_base_barcode = make_scale_base_barcode(item)
	return items


def get_item_price(item_code, price_list=None, uom=None):
	filters = {"item_code": item_code, "selling": 1}
	if price_list:
		filters["price_list"] = price_list
	if uom:
		filters["uom"] = ["in", [uom, None, ""]]
	price = frappe.db.get_value(
		"Item Price",
		filters,
		"price_list_rate",
		order_by="valid_from desc, modified desc",
	)
	if price is None:
		price = frappe.db.get_value("Item", item_code, "standard_rate")
	return flt(price)


def make_scale_base_barcode(item):
	plu = str(item.scale_plu_number or "").strip()
	if not plu:
		return ""
	return f"{item.scale_prefix or '99'}{plu.zfill(5)}"


def get_column_value(row, column):
	source = column.source_field
	if source == "plu":
		return row.scale_plu_number
	if source == "barcode":
		return row.scale_base_barcode
	if source == "item_name":
		return row.item_name
	if source == "price":
		return f"{flt(row.unit_price):.2f}"
	if source == "unit":
		return row.scale_unit_code or "1"
	if source == "shelf_days":
		return row.scale_expiry_days or 0
	if source == "item_code":
		return row.item_code
	if source == "uom":
		return row.scale_uom or row.stock_uom
	if source == "prefix":
		return row.scale_prefix or "99"
	if source == "barcode_type":
		return row.scale_barcode_type or "WEIGHT"
	return row.get(source) or ""


def ensure_default_scale_export_template():
	if frappe.db.exists("Scale Export Template", DEFAULT_EXPERTS_TEMPLATE):
		return

	doc = frappe.get_doc(
		{
			"doctype": "Scale Export Template",
			"template_name": DEFAULT_EXPERTS_TEMPLATE,
			"enabled": 1,
			"file_extension": "txt",
		}
	)
	for idx, (label, source) in enumerate(
		[
			("plu no", "plu"),
			("barcode", "barcode"),
			("item name", "item_name"),
			("price", "price"),
			("unit", "unit"),
			("shelf days", "shelf_days"),
		],
		1,
	):
		doc.append("columns", {"idx": idx, "output_label": label, "source_field": source})
	doc.insert(ignore_permissions=True)
