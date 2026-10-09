from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


FOC_ITEM_DOCTYPES = (
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
	"Sales Order Item",
	"Delivery Note Item",
	"Sales Invoice Item",
	"POS Invoice Item",
	"Stock Entry Detail",
)

FOC_PARENT_DOCTYPES = (
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
	"POS Invoice",
	"Stock Entry",
)

FOC_STOCK_DOCTYPES = (
	"Purchase Receipt",
	"Purchase Invoice",
	"Delivery Note",
	"Sales Invoice",
	"POS Invoice",
	"Stock Entry",
)


def ensure_foc_fields():
	"""Add FOC quantity fields to retail buying/selling item rows."""
	create_custom_fields(
		{
			doctype: [
				{
					"fieldname": "custom_foc_qty",
					"label": "FOC Qty",
					"fieldtype": "Float",
					"insert_after": "qty",
					"in_list_view": 1,
					"columns": 1,
				},
				{
					"fieldname": "custom_total_stock_qty",
					"label": "Total Stock Qty",
					"fieldtype": "Float",
					"insert_after": "custom_foc_qty",
					"read_only": 1,
					"in_list_view": 1,
					"columns": 1,
				},
				{"fieldname": "custom_foc_key", "label": "FOC Relationship",
				 "fieldtype": "Data", "hidden": 1, "read_only": 1},
				{"fieldname": "custom_foc_parent", "label": "FOC Paid Row Relationship",
				 "fieldtype": "Data", "hidden": 1, "read_only": 1},
			]
			for doctype in FOC_ITEM_DOCTYPES
		}
		| {
				"Stock Ledger Entry": [
					{
						"fieldname": "custom_is_foc_stock_entry",
						"label": "FOC Stock Entry",
						"fieldtype": "Check",
						"insert_after": "actual_qty",
						"read_only": 1,
						"no_copy": 1,
						"in_standard_filter": 1,
					}
				]
		},
		ignore_validate=True,
	)

	field_name = "Stock Ledger Entry-custom_is_foc_stock_entry"
	if frappe.db.exists("Custom Field", field_name):
		frappe.db.set_value(
			"Custom Field",
			field_name,
			{
				"label": "FOC Stock Entry",
				"in_list_view": 0,
				"in_standard_filter": 1,
				"read_only": 1,
				"no_copy": 1,
			},
			update_modified=False,
		)

	for doctype in FOC_ITEM_DOCTYPES:
		frappe.db.updatedb(doctype)
		frappe.clear_cache(doctype=doctype)
	frappe.db.updatedb("Stock Ledger Entry")
	frappe.clear_cache(doctype="Stock Ledger Entry")


def apply_foc_quantities(doc, method=None):
	"""Keep paid qty for amounts and show paid+FOC as the row total."""
	if doc.doctype not in FOC_PARENT_DOCTYPES:
		return

	for row in doc.get("items") or []:
		if not row.meta.has_field("custom_foc_qty"):
			continue

		foc_qty = flt(row.get("custom_foc_qty"))
		paid_qty = flt(row.get("qty"))
		total_qty = paid_qty + foc_qty

		row.set("custom_total_stock_qty", total_qty)

		_set_paid_amounts(doc, row, paid_qty)


def _set_paid_amounts(doc, row, paid_qty):
	rate = flt(row.get("rate"))
	net_rate = flt(row.get("net_rate") or rate)
	base_rate = flt(row.get("base_rate") or rate)
	base_net_rate = flt(row.get("base_net_rate") or net_rate or base_rate)
	conversion_rate = flt(doc.get("conversion_rate") or 1)

	if row.meta.has_field("amount"):
		row.set("amount", flt(paid_qty * rate, row.precision("amount")))
	if row.meta.has_field("net_amount"):
		row.set("net_amount", flt(paid_qty * net_rate, row.precision("net_amount")))
	if row.meta.has_field("base_rate"):
		row.set("base_rate", flt(base_rate or rate * conversion_rate, row.precision("base_rate")))
	if row.meta.has_field("base_amount"):
		row.set("base_amount", flt(paid_qty * flt(row.get("base_rate")), row.precision("base_amount")))
	if row.meta.has_field("base_net_rate"):
		row.set(
			"base_net_rate",
			flt(base_net_rate or net_rate * conversion_rate, row.precision("base_net_rate")),
		)
	if row.meta.has_field("base_net_amount"):
		row.set("base_net_amount", flt(paid_qty * flt(row.get("base_net_rate")), row.precision("base_net_amount")))


def prepare_foc_items(doc, method=None):
	"""Materialize free goods as native child rows BEFORE core validation/posting.

	The paid row retains its qty, price and promotion fields. A stable relationship
	key survives saves and document mapping; each free row has its own voucher
	detail ID, so core can value, account for, cancel and repost it normally.
	"""
	if doc.doctype not in FOC_PARENT_DOCTYPES or doc.docstatus == 2:
		return
	rows = list(doc.get("items") or [])
	free_rows = {}
	for row in rows:
		if row.get("custom_foc_parent"):
			key = row.custom_foc_parent
			if key in free_rows:
				frappe.throw("Duplicate FOC relationship; remove the duplicate free row.")
			free_rows[key] = row

	items = []
	keys = set()
	for paid in rows:
		if paid.get("custom_foc_parent"):
			continue
		items.append(paid)
		qty = flt(paid.get("custom_foc_qty"))
		# Core return mapping reverses native quantities but copies custom fields.
		if doc.get("is_return") and doc.get("return_against") and flt(paid.qty) < 0 and qty > 0:
			qty = -qty
			paid.custom_foc_qty = qty
		if not qty:
			continue
		if not paid.meta.has_field("custom_foc_key"):
			frappe.throw("Install the Retail FOC relationship fields before posting FOC quantities.")
		if not flt(paid.qty) or qty * flt(paid.qty) < 0:
			frappe.throw("FOC quantity must have the same sign as a non-zero paid quantity.")
		key = paid.get("custom_foc_key") or frappe.generate_hash(length=20)
		if key in keys:
			frappe.throw("Duplicate paid FOC relationship; recreate the copied item row.")
		keys.add(key)
		paid.custom_foc_key = key
		free = free_rows.get(key)
		if free is None:
			free = doc.append("items", {})
			# Copy business context, not identifiers, quantities or financial state.
			for field in ("item_code", "item_name", "description", "uom", "stock_uom",
				"conversion_factor", "warehouse", "s_warehouse", "t_warehouse",
				"expense_account", "income_account", "cost_center", "project",
				"item_tax_template", "custom_tax", "brand", "item_group"):
				if free.meta.has_field(field):
					free.set(field, paid.get(field))
		# Keep explicit serial/batch allocations on the free row separate from paid goods.
		for field in ("item_code", "uom", "stock_uom", "conversion_factor", "warehouse",
			"s_warehouse", "t_warehouse", "expense_account", "income_account", "cost_center", "project"):
			if free.meta.has_field(field):
				free.set(field, paid.get(field))
		free.custom_foc_parent = key
		free.custom_foc_key = None
		free.custom_foc_qty = 0
		free.qty = qty
		if free.meta.has_field("received_qty"):
			free.received_qty = qty
		if doc.doctype != "Stock Entry":
			for field in free.meta.fields:
				if field.fieldtype == "Currency" or field.fieldname in (
					"discount_percentage", "margin_rate_or_amount", "pricing_rules"):
					free.set(field.fieldname, 0 if field.fieldtype != "Data" else None)
			free.is_free_item = 1
			free.allow_zero_valuation_rate = 1
		else:
			# Stock transfers/issues continue to obtain their incoming rate from core.
			free.basic_rate = paid.get("basic_rate")
			free.allow_zero_valuation_rate = paid.get("allow_zero_valuation_rate")
		items.append(free)

	doc.set("items", items)
	for index, row in enumerate(doc.items, 1):
		row.idx = index


def validate_foc_items(doc, method=None):
	"""Fail before posting if another customization changed the free goods contract."""
	paid_rows = {row.get("custom_foc_key"): row for row in doc.get("items") or []
		if row.get("custom_foc_key") and flt(row.get("custom_foc_qty"))}
	for key, paid in paid_rows.items():
		free_rows = [row for row in doc.items if row.get("custom_foc_parent") == key]
		if len(free_rows) != 1 or flt(free_rows[0].qty) != flt(paid.custom_foc_qty):
			frappe.throw("FOC quantity relationship changed during validation; posting stopped.")
		if doc.doctype != "Stock Entry" and any(flt(free_rows[0].get(field))
			for field in ("rate", "amount", "base_net_amount")):
			frappe.throw("A pricing rule changed the free goods price; posting stopped.")


def add_foc_stock_ledger_entries(doc, method=None):
	"""Legacy entry point: independent stock posting is intentionally prohibited."""
	frappe.throw("Late FOC stock posting is disabled. Submit a document with native FOC item rows.")


@frappe.whitelist()
def post_foc_stock_ledger_for_voucher(doctype, name):
	frappe.throw("Late FOC stock posting is disabled. Historical repair requires a separate approved procedure.")
