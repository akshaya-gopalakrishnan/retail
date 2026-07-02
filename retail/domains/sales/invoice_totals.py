from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt


SHIPPING_DESCRIPTION = "Shipping Charges"
VAT_DESCRIPTION_PREFIX = "Sales Tax"


def ensure_sales_invoice_retail_totals_fields():
	"""Add a clean Retail totals panel to Sales Invoice without changing standard fields."""
	create_custom_fields(
		{
			"Sales Invoice": [
				{
					"fieldname": "custom_retail_sales_person",
					"label": "Sales Man",
					"fieldtype": "Link",
					"options": "Sales Person",
					"insert_after": "column_break_14",
				},
				{
					"fieldname": "custom_retail_delivery_person",
					"label": "Delivery Person",
					"fieldtype": "Data",
					"insert_after": "custom_retail_sales_person",
				},
				{
					"fieldname": "custom_retail_totals_section",
					"label": "Retail Totals",
					"fieldtype": "Column Break",
					"insert_after": "net_total",
				},
				{
					"fieldname": "custom_retail_shipping_charges",
					"label": "Shipping Charges",
					"fieldtype": "Currency",
					"insert_after": "custom_retail_totals_section",
				},
				{
					"fieldname": "custom_retail_totals_summary",
					"label": "Retail Totals Summary",
					"fieldtype": "HTML",
					"insert_after": "custom_retail_shipping_charges",
				},
			],
		},
		ignore_validate=True,
	)
	frappe.db.updatedb("Sales Invoice")
	_update_sales_invoice_retail_field_layout()
	frappe.clear_cache(doctype="Sales Invoice")


def _update_sales_invoice_retail_field_layout():
	"""Keep custom Sales Invoice fields in the intended positions even with field_order setters."""
	if frappe.db.exists("Custom Field", "Sales Invoice-custom_retail_totals_section"):
		frappe.db.set_value(
			"Custom Field",
			"Sales Invoice-custom_retail_totals_section",
			{"fieldtype": "Column Break", "insert_after": "net_total"},
			update_modified=False,
		)
	make_property_setter(
		"Sales Invoice",
		"company",
		"hidden",
		0,
		"Check",
		validate_fields_for_doctype=False,
	)
	for fieldname in ("total", "net_total"):
		make_property_setter(
			"Sales Invoice",
			fieldname,
			"hidden",
			1,
			"Check",
			validate_fields_for_doctype=False,
		)

	field_order = _get_sales_invoice_field_order()
	field_order = _place_after(
		field_order,
		"column_break_14",
		["custom_retail_sales_person", "custom_retail_delivery_person"],
	)
	field_order = _place_after(
		field_order,
		"net_total",
		[
			"custom_retail_totals_section",
			"custom_retail_shipping_charges",
			"custom_retail_totals_summary",
		],
	)

	make_property_setter(
		"Sales Invoice",
		None,
		"field_order",
		json.dumps(field_order),
		"JSON",
		validate_fields_for_doctype=False,
	)


def _get_sales_invoice_field_order():
	property_value = frappe.db.get_value(
		"Property Setter",
		{"doc_type": "Sales Invoice", "property": "field_order", "field_name": ["is", "not set"]},
		"value",
	)
	if property_value:
		return json.loads(property_value)

	return [field.fieldname for field in frappe.get_meta("Sales Invoice").fields if field.fieldname]


def _place_after(field_order, anchor, fieldnames):
	ordered = [field for field in field_order if field not in fieldnames]
	if anchor not in ordered:
		ordered.extend(field for field in fieldnames if field not in ordered)
		return ordered

	insert_at = ordered.index(anchor) + 1
	return ordered[:insert_at] + list(fieldnames) + ordered[insert_at:]


def apply_retail_shipping_charges(doc, method=None):
	"""Mirror friendly retail VAT/shipping values into ERPNext's standard Taxes table."""
	if not doc.meta.has_field("custom_retail_shipping_charges"):
		return

	doc.set(
		"taxes",
		[
			row
			for row in (doc.get("taxes") or [])
			if not _is_shipping_row(row) and not _is_managed_vat_row(row)
		],
	)

	_append_vat_rows(doc)
	_append_shipping_row(doc)
	doc.calculate_taxes_and_totals()


def _append_vat_rows(doc):
	vat_groups = _get_vat_groups(doc)
	for group in vat_groups.values():
		if not group["amount"]:
			continue

		doc.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": group["account_head"],
				"description": group["description"],
				"rate": group["rate"],
				"tax_amount": flt(group["amount"], 2),
				"cost_center": doc.get("cost_center"),
			},
		)


def _get_vat_groups(doc):
	groups = {}
	for item in doc.get("items") or []:
		template = item.get("item_tax_template") or _get_item_sales_tax_template(item.get("item_code"))
		if not template:
			continue

		for tax in _get_item_tax_template_details(template):
			rate = flt(tax.tax_rate)
			if not rate:
				continue

			account_head = tax.tax_type
			amount = _get_item_net_amount(item) * rate / 100
			key = (account_head, rate, template)
			if key not in groups:
				groups[key] = {
					"account_head": account_head,
					"rate": rate,
					"amount": 0,
					"description": f"{VAT_DESCRIPTION_PREFIX} [{template}]",
				}

			groups[key]["amount"] += amount

	return groups


def _append_shipping_row(doc):
	if doc.get("custom_retail_shipping_charges") in (None, ""):
		return

	shipping_amount = flt(doc.get("custom_retail_shipping_charges"))
	shipping_account = _get_shipping_account(doc)

	if shipping_amount:
		if not shipping_account:
			frappe.throw(
				_(
					"Set a Shipping Charges row in the selected Sales Taxes and Charges Template, "
					"or configure a Default Income Account for the company."
				)
			)

		doc.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": shipping_account,
				"description": SHIPPING_DESCRIPTION,
				"tax_amount": shipping_amount,
				"cost_center": doc.get("cost_center"),
			},
		)


def _get_shipping_account(doc):
	for row in doc.get("taxes") or []:
		if _is_shipping_row(row) and row.get("account_head"):
			return row.account_head

	if doc.get("taxes_and_charges"):
		account = frappe.db.get_value(
			"Sales Taxes and Charges",
			{
				"parent": doc.taxes_and_charges,
				"parenttype": "Sales Taxes and Charges Template",
				"description": ["like", f"%{SHIPPING_DESCRIPTION}%"],
			},
			"account_head",
		)
		if account:
			return account

	if doc.get("company"):
		return frappe.db.get_value("Company", doc.company, "default_income_account")


def _is_shipping_row(row):
	return (row.get("description") or "").strip().lower() == SHIPPING_DESCRIPTION.lower()


def _is_managed_vat_row(row):
	description = (row.get("description") or "").strip()
	return description.startswith(f"{VAT_DESCRIPTION_PREFIX} [")


def _get_item_sales_tax_template(item_code):
	if not item_code:
		return None

	return frappe.db.get_value("Item", item_code, "custom_tax")


def _get_item_tax_template_details(template):
	return frappe.get_all(
		"Item Tax Template Detail",
		filters={"parent": template},
		fields=["tax_type", "tax_rate"],
		limit_page_length=0,
	)


def _get_item_net_amount(item):
	if item.get("net_amount") not in (None, ""):
		return flt(item.get("net_amount"))

	if item.get("amount") not in (None, ""):
		return flt(item.get("amount"))

	return flt(item.get("qty")) * flt(item.get("rate"))
