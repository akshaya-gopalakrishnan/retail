from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt

from retail.domains.item.item_price_sync import sync_item_price
from retail.domains.item.vat_pricing import get_item_tax_rate


PURCHASE_DOCTYPES = ("Purchase Receipt", "Purchase Invoice")
PURCHASE_ITEM_DOCTYPES = ("Purchase Receipt Item", "Purchase Invoice Item")
SELLING_PRICE_LIST = "Standard Selling"


def ensure_purchase_selling_price_fields():
	"""Add optional selling-price update fields to PR/PI item rows."""
	create_custom_fields(
		{
			doctype: [
				{
					"fieldname": "custom_upd_sell_price",
					"label": "Upd SP",
					"fieldtype": "Check",
					"insert_after": "rate",
					"in_list_view": 0,
					"columns": 1,
				},
				{
					"fieldname": "custom_cur_sell_rate",
					"label": "Cur SP",
					"fieldtype": "Currency",
					"options": "currency",
					"insert_after": "custom_upd_sell_price",
					"read_only": 1,
					"in_list_view": 1,
					"columns": 1,
				},
				{
					"fieldname": "custom_new_sell_rate",
					"label": "New SP",
					"fieldtype": "Currency",
					"options": "currency",
					"insert_after": "custom_cur_sell_rate",
					"depends_on": "eval:doc.custom_upd_sell_price",
					"in_list_view": 1,
					"columns": 1,
				},
				{
					"fieldname": "custom_new_sell_incl",
					"label": "SP Incl",
					"fieldtype": "Currency",
					"options": "currency",
					"insert_after": "custom_new_sell_rate",
					"depends_on": "eval:doc.custom_upd_sell_price",
					"in_list_view": 1,
					"columns": 1,
				},
				{
					"fieldname": "custom_sell_margin",
					"label": "Margin",
					"fieldtype": "Currency",
					"options": "currency",
					"insert_after": "custom_new_sell_incl",
					"read_only": 1,
					"in_list_view": 1,
					"columns": 1,
				},
				{
					"fieldname": "custom_sell_margin_pct",
					"label": "Mgn %",
					"fieldtype": "Percent",
					"insert_after": "custom_sell_margin",
					"read_only": 1,
					"in_list_view": 0,
					"columns": 1,
				},
			]
			for doctype in PURCHASE_ITEM_DOCTYPES
		},
		ignore_validate=True,
	)

	_update_field_metadata()
	_update_standard_grid_metadata()
	for doctype in PURCHASE_ITEM_DOCTYPES:
		frappe.db.updatedb(doctype)
		frappe.clear_cache(doctype=doctype)


def set_selling_price_margins(doc, method=None):
	if doc.doctype not in PURCHASE_DOCTYPES:
		return

	for row in doc.get("items") or []:
		if not row.meta.has_field("custom_new_sell_rate"):
			continue

		current_selling_rate = get_standard_selling_rate(row.get("item_code"), row.get("uom"))
		if current_selling_rate and not flt(row.get("custom_cur_sell_rate")):
			row.set("custom_cur_sell_rate", current_selling_rate)

		if flt(row.get("custom_upd_sell_price")) and not flt(row.get("custom_new_sell_rate")):
			row.set("custom_new_sell_rate", current_selling_rate)

		_set_exclusive_selling_rate(row)
		_set_inclusive_selling_rate(row)
		_set_margin_values(row)


def update_selected_selling_prices(doc, method=None):
	if doc.doctype not in PURCHASE_DOCTYPES:
		return

	for row in doc.get("items") or []:
		if not row.meta.has_field("custom_upd_sell_price"):
			continue
		if not flt(row.get("custom_upd_sell_price")):
			continue
		if not row.get("item_code") or flt(row.get("custom_new_sell_rate")) <= 0:
			continue

		sync_item_price(
			{"item_code": row.get("item_code")},
			SELLING_PRICE_LIST,
			row.get("custom_new_sell_rate"),
			uom=row.get("uom"),
		)


@frappe.whitelist()
def get_standard_selling_rate(item_code, uom=None):
	if not item_code:
		return 0

	uom = uom or frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
	rate = frappe.db.get_value(
		"Item Price",
		{
			"item_code": item_code,
			"price_list": SELLING_PRICE_LIST,
			"uom": uom,
		},
		"price_list_rate",
	)
	if rate is None:
		rate = frappe.db.get_value(
			"Item Price",
			{
				"item_code": item_code,
				"price_list": SELLING_PRICE_LIST,
				"uom": ("is", "not set"),
			},
			"price_list_rate",
		)
	return flt(rate)


@frappe.whitelist()
def get_item_selling_vat_rate(item_code):
	if not item_code:
		return 0

	template = frappe.db.get_value("Item", item_code, "custom_tax")
	return flt(get_item_tax_rate(template)) if template else 0


def _update_field_metadata():
	field_updates = {
		"custom_rate_including_vat": {"in_list_view": 0},
		"custom_amount_including_vat": {"in_list_view": 0},
		"custom_upd_sell_price": {"label": "Upd SP", "insert_after": "rate", "in_list_view": 0},
		"custom_cur_sell_rate": {"label": "Cur SP", "insert_after": "custom_upd_sell_price", "in_list_view": 1},
		"custom_new_sell_rate": {"label": "New SP", "insert_after": "custom_cur_sell_rate", "in_list_view": 1},
		"custom_new_sell_incl": {"label": "SP Incl", "insert_after": "custom_new_sell_rate", "in_list_view": 1},
		"custom_sell_margin": {"label": "Margin", "insert_after": "custom_new_sell_incl", "in_list_view": 1},
		"custom_sell_margin_pct": {"label": "Mgn %", "insert_after": "custom_sell_margin", "in_list_view": 0},
	}
	for doctype in PURCHASE_ITEM_DOCTYPES:
		for fieldname, values in field_updates.items():
			custom_field = f"{doctype}-{fieldname}"
			if frappe.db.exists("Custom Field", custom_field):
				frappe.db.set_value("Custom Field", custom_field, values, update_modified=False)


def _update_standard_grid_metadata():
	field_updates = {
		"item_code": {"in_list_view": 1, "columns": 1},
		"qty": {"in_list_view": 1, "columns": 1},
		"rejected_qty": {"in_list_view": 1, "columns": 1},
		"rate": {"in_list_view": 1, "columns": 1},
	}
	for doctype in PURCHASE_ITEM_DOCTYPES:
		for fieldname, values in field_updates.items():
			if not frappe.get_meta(doctype).has_field(fieldname):
				continue
			for property_name, value in values.items():
				property_type = "Check" if property_name == "in_list_view" else "Int"
				_set_property(doctype, fieldname, property_name, value, property_type)


def _set_property(doctype, fieldname, property_name, value, property_type):
	property_setter = f"{doctype}-{fieldname}-{property_name}"
	if frappe.db.exists("Property Setter", property_setter):
		frappe.db.set_value("Property Setter", property_setter, "value", value, update_modified=False)
		return

	make_property_setter(
		doctype,
		fieldname,
		property_name,
		value,
		property_type,
		validate_fields_for_doctype=False,
	)


def _set_inclusive_selling_rate(row):
	if not row.meta.has_field("custom_new_sell_incl"):
		return

	exclusive_rate = flt(row.get("custom_new_sell_rate") or row.get("custom_cur_sell_rate"))
	if exclusive_rate <= 0:
		row.set("custom_new_sell_incl", 0)
		return

	vat_rate = get_item_selling_vat_rate(row.get("item_code"))
	row.set("custom_new_sell_incl", flt(exclusive_rate * (1 + vat_rate / 100), row.precision("custom_new_sell_incl")))


def _set_exclusive_selling_rate(row):
	if not row.meta.has_field("custom_new_sell_incl"):
		return
	if flt(row.get("custom_new_sell_rate")) > 0 or flt(row.get("custom_new_sell_incl")) <= 0:
		return

	vat_rate = get_item_selling_vat_rate(row.get("item_code"))
	divisor = 1 + vat_rate / 100
	row.set(
		"custom_new_sell_rate",
		flt(flt(row.get("custom_new_sell_incl")) / divisor if divisor else row.get("custom_new_sell_incl")),
	)


def _set_margin_values(row):
	new_selling_rate = flt(row.get("custom_new_sell_rate") or row.get("custom_cur_sell_rate"))
	purchase_rate = flt(row.get("net_rate") or row.get("rate"))
	margin = new_selling_rate - purchase_rate if new_selling_rate else 0
	margin_pct = (margin / new_selling_rate * 100) if new_selling_rate else 0

	row.set("custom_sell_margin", flt(margin, row.precision("custom_sell_margin")))
	row.set("custom_sell_margin_pct", flt(margin_pct, row.precision("custom_sell_margin_pct")))
