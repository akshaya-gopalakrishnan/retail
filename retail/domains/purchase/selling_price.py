from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt

from retail.domains.item.item_price_sync import sync_item_price
from retail.domains.item.vat_pricing import get_default_vat_template, get_item_tax_rate


PURCHASE_DOCTYPES = ("Purchase Receipt", "Purchase Invoice")
PURCHASE_ITEM_DOCTYPES = ("Purchase Receipt Item", "Purchase Invoice Item")
SELLING_PRICE_LIST = "Standard Selling"
ALLOW_SELLING_PRICE_INSERT_AFTER = {
	"Purchase Receipt": "supplier_warehouse",
	"Purchase Invoice": "is_subcontracted",
}
ALLOW_SELLING_PRICE_DEFAULT = {
	"Purchase Receipt": "1",
	"Purchase Invoice": "1",
}


def ensure_purchase_selling_price_fields():
	"""Add optional selling-price update fields to PR/PI item rows."""
	create_custom_fields(
		{
			doctype: [
				{
					"fieldname": "custom_allow_selling_price",
					"label": "Update Selling Price",
					"fieldtype": "Check",
					"insert_after": ALLOW_SELLING_PRICE_INSERT_AFTER[doctype],
					"default": ALLOW_SELLING_PRICE_DEFAULT[doctype],
					"print_hide": 1,
				},
				{
					"fieldname": "custom_update_item_master_rates",
					"label": "Update Item Master Rates",
					"fieldtype": "Check",
					"insert_after": "custom_allow_selling_price",
					"default": "0",
					"no_copy": 1,
					"print_hide": 1,
					"depends_on": "eval:!doc.is_return",
					"description": "",
				},
			]
			for doctype in PURCHASE_DOCTYPES
		},
		ignore_validate=True,
	)
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
					"in_list_view": 1,
					"columns": 1,
				},
				{
					"fieldname": "custom_new_sell_incl",
					"label": "SP Incl",
					"fieldtype": "Currency",
					"options": "currency",
					"insert_after": "custom_new_sell_rate",
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

	create_custom_fields({
		**{doctype: [{"fieldname": "custom_packing_selling_prices", "label": "Packing Selling Prices",
			"fieldtype": "Long Text", "hidden": 1, "no_copy": 1, "print_hide": 1}]
			for doctype in PURCHASE_ITEM_DOCTYPES},
		"Item Price": [{"fieldname": "custom_retail_selling_revision", "label": "Selling Price Revision",
			"fieldtype": "Data", "read_only": 1, "hidden": 1, "no_copy": 1}],
	}, ignore_validate=True)
	_update_field_metadata()
	_update_standard_grid_metadata()
	for doctype in PURCHASE_ITEM_DOCTYPES:
		frappe.db.updatedb(doctype)
		frappe.clear_cache(doctype=doctype)


def set_selling_price_margins(doc, method=None):
	if doc.doctype not in PURCHASE_DOCTYPES:
		return
	if doc.get("is_return") or not flt(doc.get("custom_allow_selling_price")):
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
	if doc.doctype not in PURCHASE_DOCTYPES or doc.get("is_return"):
		return
	from retail.domains.purchase.price_history import lock_item, sync_selling_state
	# Deterministic lock order also covers repeated items and concurrent submissions.
	for item_code in sorted({row.item_code for row in doc.get("items") or [] if row.item_code}):
		lock_item(item_code)
	from retail.domains.purchase.master_rates import update_purchase_master_rates, update_selling_master_rate
	update_purchase_master_rates(doc)
	if not flt(doc.get("custom_allow_selling_price")):
		return
	for row in doc.get("items") or []:
		if not row.get("item_code") or not flt(row.get("custom_upd_sell_price")):
			continue
		item = frappe.get_doc("Item", row.item_code)
		requests = {row.get("uom") or item.stock_uom: flt(row.get("custom_new_sell_rate"))}
		allowed = {entry["uom"] for entry in _packing_prices(item)}
		for entry in _packing_requests(row):
			if entry.get("item_code") != row.item_code:
				continue  # Mapped/changed rows must not apply another item's saved overrides.
			if entry.get("uom") not in allowed:
				frappe.throw("Selling price UOM is not in this Item's Retail Packing Detail.")
			if flt(entry.get("update")):
				requests[entry["uom"]] = flt(entry.get("new_rate"))
			elif entry["uom"] in requests:
				requests.pop(entry["uom"])
		for uom, rate in requests.items():
			if rate <= 0:
				continue
			# Compare to the authoritative key, never the draft's stale Current SP.
			current = get_standard_selling_rate(row.item_code, uom)
			if rate == current:
				continue
			sync_item_price(row, SELLING_PRICE_LIST, rate, uom=uom,
				source={"doctype": doc.doctype, "name": doc.name, "company": doc.company, "row": row.name})
			# Stock-UOM Item Master changes use the explicit, audited checkbox below.
			if uom != item.stock_uom:
				sync_selling_state(row.item_code, uom, rate)
		if flt(doc.get("custom_update_item_master_rates")):
			update_selling_master_rate(doc, row, item, requests)


def _packing_requests(row):
	entries = frappe.parse_json(row.get("custom_packing_selling_prices") or "[]")
	if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
		frappe.throw("Invalid packing selling prices.")
	if len({entry.get("uom") for entry in entries}) != len(entries):
		frappe.throw("Only one selling price per packing UOM is allowed.")
	return entries


def _packing_prices(item):
	from retail.domains.item.item_price_sync import get_item_price_barcode
	stock_rate = get_standard_selling_rate(item.name, item.stock_uom)
	rows = [{"uom": item.stock_uom, "conversion_factor": 1}]
	seen = {item.stock_uom}
	for row in item.get("custom_retail_packing_detail") or []:
		if row.uom and row.uom not in seen:
			rows.append({"uom": row.uom, "conversion_factor": flt(row.conversion_factor) or 1})
			seen.add(row.uom)
	for row in rows:
		row.update(item_code=item.name, barcode=get_item_price_barcode(item.name, row["uom"]),
			current_rate=get_standard_selling_rate(item.name, row["uom"]),
			suggested_rate=stock_rate * row["conversion_factor"],
			vat_rate=get_item_selling_vat_rate(item.name))
	return rows


@frappe.whitelist()
def get_packing_selling_prices(item_code):
	item = frappe.get_doc("Item", item_code)
	item.check_permission("read")
	return _packing_prices(item)


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
	return flt(rate)


@frappe.whitelist()
def get_item_selling_vat_rate(item_code):
	if not item_code:
		return 0

	template = (
		frappe.db.get_value("Item", item_code, "custom_tax")
		or get_default_vat_template()
	)
	return flt(get_item_tax_rate(template)) if template else 0


def _update_field_metadata():
	for doctype in PURCHASE_DOCTYPES:
		custom_field = f"{doctype}-custom_allow_selling_price"
		if frappe.db.exists("Custom Field", custom_field):
			frappe.db.set_value(
				"Custom Field",
				custom_field,
				{
					"label": "Update Selling Price",
					"insert_after": ALLOW_SELLING_PRICE_INSERT_AFTER[doctype],
					"default": ALLOW_SELLING_PRICE_DEFAULT[doctype],
					"print_hide": 1,
				},
				update_modified=False,
			)

	field_updates = {
		"custom_rate_including_vat": {"in_list_view": 1},
		"custom_amount_including_vat": {"in_list_view": 0},
		"custom_upd_sell_price": {"label": "Upd SP", "insert_after": "rate", "in_list_view": 0},
		"custom_cur_sell_rate": {"label": "Cur SP", "insert_after": "custom_upd_sell_price", "in_list_view": 1},
		"custom_new_sell_rate": {
			"label": "New SP",
			"insert_after": "custom_cur_sell_rate",
			"in_list_view": 1,
			"depends_on": "",
			"read_only": 0,
		},
		"custom_new_sell_incl": {
			"label": "SP Incl",
			"insert_after": "custom_new_sell_rate",
			"in_list_view": 1,
			"depends_on": "",
			"read_only": 0,
		},
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
		"custom_foc_qty": {"in_list_view": 1, "columns": 1},
		"rate": {"in_list_view": 1, "columns": 1},
		"custom_rate_including_vat": {"in_list_view": 1, "columns": 1},
		"amount": {"in_list_view": 1, "columns": 1},
		"custom_cur_sell_rate": {"in_list_view": 1, "columns": 1},
		"custom_new_sell_rate": {"in_list_view": 1, "columns": 1},
		"custom_new_sell_incl": {"in_list_view": 1, "columns": 1},
		"custom_sell_margin": {"in_list_view": 1, "columns": 1},
	}
	receipt_only_field_updates = {
		"item_code": {"in_list_view": 1, "columns": 1},
		"qty": {"in_list_view": 1, "columns": 1},
		"rejected_qty": {"in_list_view": 1, "columns": 1},
		"rate": {"in_list_view": 1, "columns": 1},
	}
	for doctype in PURCHASE_ITEM_DOCTYPES:
		doctype_updates = dict(field_updates)
		if doctype == "Purchase Receipt Item":
			doctype_updates.update(receipt_only_field_updates)
			doctype_updates["custom_sell_margin"] = {"in_list_view": 0, "columns": 1}

		for fieldname, values in doctype_updates.items():
			if not frappe.get_meta(doctype).has_field(fieldname):
				continue
			for property_name, value in values.items():
				property_type = "Check" if property_name == "in_list_view" else "Int"
				_set_property(doctype, fieldname, property_name, value, property_type)

	_clear_purchase_grid_settings()


def _clear_purchase_grid_settings():
	frappe.db.sql(
		"delete from `__UserSettings` where doctype in %(doctypes)s",
		{"doctypes": PURCHASE_DOCTYPES},
	)


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
	purchase_rate = flt(row.get("net_rate") if row.get("net_rate") is not None else row.get("rate"))
	margin = new_selling_rate - purchase_rate if new_selling_rate else 0
	margin_pct = (margin / new_selling_rate * 100) if new_selling_rate else 0

	row.set("custom_sell_margin", flt(margin, row.precision("custom_sell_margin")))
	row.set("custom_sell_margin_pct", flt(margin_pct, row.precision("custom_sell_margin_pct")))
