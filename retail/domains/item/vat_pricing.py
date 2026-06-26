"""Item-master VAT price conversion with net rates as the accounting base."""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt


VAT_PRICE_FIELDS = {
	"sales": {
		"template": "custom_tax",
		"entry": "custom_sales_rate_entry",
		"inclusive": "custom_sales_rate_includes_vat",
		"net": "custom_sales_net_rate",
		"vat": "custom_sales_vat_amount",
		"gross": "custom_sales_gross_rate",
		"base": "standard_rate",
	},
	"purchase": {
		"template": "custom_purchase_tax_template",
		"entry": "custom_purchase_rate_entry",
		"inclusive": "custom_purchase_rate_includes_vat",
		"net": "custom_purchase_net_rate",
		"vat": "custom_purchase_vat_amount",
		"gross": "custom_purchase_gross_rate",
		"base": "custom_default_purchase_rate",
	},
}


def ensure_item_vat_pricing_fields():
	"""Add the reusable Sales/Purchase VAT pricing controls to Item."""
	create_custom_fields(
		{
			"Item": [
				{
					"fieldname": "custom_pricing_summary_section",
					"label": "Pricing Summary",
					"fieldtype": "Section Break",
					"insert_after": "custom_pricing__tax",
				},
				{
					"fieldname": "custom_pricing_summary_column",
					"fieldtype": "Column Break",
					"insert_after": "valuation_rate",
				},
				{
					"fieldname": "custom_vat_pricing_section",
					"label": "VAT Pricing",
					"fieldtype": "Section Break",
					"insert_after": "custom_tax",
				},
				{
					"fieldname": "custom_sales_rate_entry",
					"label": "Selling Rate Entered",
					"fieldtype": "Currency",
					"insert_after": "custom_vat_pricing_section",
				},
				{
					"fieldname": "custom_sales_rate_includes_vat",
					"label": "Selling Rate Includes VAT",
					"fieldtype": "Check",
					"default": "0",
					"insert_after": "custom_sales_rate_entry",
				},
				{
					"fieldname": "custom_sales_net_rate",
					"label": "Selling Net Rate",
					"fieldtype": "Currency",
					"read_only": 1,
					"insert_after": "custom_sales_rate_includes_vat",
				},
				{
					"fieldname": "custom_sales_vat_amount",
					"label": "Selling VAT Amount",
					"fieldtype": "Currency",
					"read_only": 1,
					"insert_after": "custom_sales_net_rate",
				},
				{
					"fieldname": "custom_sales_gross_rate",
					"label": "Selling Rate Including VAT",
					"fieldtype": "Currency",
					"read_only": 1,
					"insert_after": "custom_sales_vat_amount",
				},
				{
					"fieldname": "custom_vat_purchase_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_purchase_gross_rate",
				},
				{
					"fieldname": "custom_purchase_tax_template",
					"label": "Purchase VAT Template",
					"fieldtype": "Link",
					"options": "Item Tax Template",
					"insert_after": "custom_vat_pricing_section",
				},
				{
					"fieldname": "custom_purchase_rate_entry",
					"label": "Purchase Rate Entered",
					"fieldtype": "Currency",
					"insert_after": "custom_vat_purchase_column",
				},
				{
					"fieldname": "custom_purchase_rate_includes_vat",
					"label": "Purchase Rate Includes VAT",
					"fieldtype": "Check",
					"default": "0",
					"insert_after": "custom_purchase_tax_template",
				},
				{
					"fieldname": "custom_purchase_net_rate",
					"label": "Purchase Net Rate",
					"fieldtype": "Currency",
					"read_only": 1,
					"insert_after": "custom_purchase_rate_entry",
				},
				{
					"fieldname": "custom_purchase_vat_amount",
					"label": "Purchase VAT Amount",
					"fieldtype": "Currency",
					"read_only": 1,
					"insert_after": "custom_purchase_rate_includes_vat",
				},
				{
					"fieldname": "custom_purchase_gross_rate",
					"label": "Purchase Rate Including VAT",
					"fieldtype": "Currency",
					"read_only": 1,
					"insert_after": "custom_purchase_net_rate",
				},
			]
		},
		ignore_validate=True,
	)
	_set_field_property("custom_tax", "label", "Sales VAT Template", "Data")
	_set_field_property("custom_pricing_summary_section", "label", "Pricing Summary", "Data")
	_set_field_property("custom_vat_pricing_section", "label", "Purchase & Sales VAT Pricing", "Data")
	_set_field_property("standard_rate", "hidden", "1", "Check")
	_set_field_property("custom_default_purchase_rate", "hidden", "1", "Check")
	arrange_item_vat_pricing_layout()
	frappe.clear_cache(doctype="Item")


def arrange_item_vat_pricing_layout():
	"""Arrange Item pricing as a compact summary followed by VAT detail."""
	# Cost/valuation is read top-to-bottom on the left. Commercial figures are
	# deliberately kept in the right column so they do not interrupt that flow.
	_set_field_property("last_purchase_rate", "insert_after", "custom_pricing_summary_section", "Data")
	_set_field_property("valuation_rate", "insert_after", "custom_average_purchase_rate", "Data")
	insert_after = {
		"custom_pricing_summary_section": "custom_pricing__tax",
		"custom_average_purchase_rate": "last_purchase_rate",
		"custom_pricing_summary_column": "valuation_rate",
		"custom_b2b": "custom_pricing_summary_column",
		"custom_margin": "custom_b2b",
		"custom_margin_": "custom_margin",
		"custom_vat_pricing_section": "custom_margin_",
		"custom_purchase_tax_template": "custom_vat_pricing_section",
		"custom_purchase_rate_entry": "custom_purchase_tax_template",
		"custom_purchase_rate_includes_vat": "custom_purchase_rate_entry",
		"custom_purchase_net_rate": "custom_purchase_rate_includes_vat",
		"custom_purchase_vat_amount": "custom_purchase_net_rate",
		"custom_purchase_gross_rate": "custom_purchase_vat_amount",
		"custom_vat_purchase_column": "custom_purchase_gross_rate",
		"custom_tax": "custom_vat_purchase_column",
		"custom_sales_rate_entry": "custom_tax",
		"custom_sales_rate_includes_vat": "custom_sales_rate_entry",
		"custom_sales_net_rate": "custom_sales_rate_includes_vat",
		"custom_sales_vat_amount": "custom_sales_net_rate",
		"custom_sales_gross_rate": "custom_sales_vat_amount",
	}

	for fieldname, previous_field in insert_after.items():
		name = f"Item-{fieldname}"
		if frappe.db.exists("Custom Field", name):
			frappe.db.set_value("Custom Field", name, "insert_after", previous_field, update_modified=False)


def update_item_vat_prices(doc, method=None):
	"""Recalculate item VAT figures and persist net rates used by accounting."""
	if not doc.meta.has_field("custom_sales_rate_entry"):
		return

	for direction in VAT_PRICE_FIELDS:
		_apply_direction(doc, direction)


def _apply_direction(doc, direction):
	fields = VAT_PRICE_FIELDS[direction]
	template = doc.get(fields["template"])
	rate = get_item_tax_rate(template) if template else 0.0
	entry = doc.get(fields["entry"])

	if entry in (None, ""):
		net = flt(doc.get(fields["base"]))
		vat = net * rate / 100
		gross = net + vat
	else:
		entry = flt(entry)
		if doc.get(fields["inclusive"]) and rate:
			net = entry / (1 + rate / 100)
			gross = entry
			vat = gross - net
		else:
			net = entry
			vat = net * rate / 100
			gross = net + vat
		doc.set(fields["base"], flt(net, 2))

	doc.set(fields["net"], flt(net, 2))
	doc.set(fields["vat"], flt(vat, 2))
	doc.set(fields["gross"], flt(gross, 2))


@frappe.whitelist()
def get_item_tax_rate(template=None):
	"""Return the combined percentage configured in an Item Tax Template."""
	if not template:
		return 0.0

	return sum(
		flt(row.tax_rate)
		for row in frappe.get_all(
			"Item Tax Template Detail", filters={"parent": template}, fields=["tax_rate"]
		)
	)


def _set_field_property(fieldname, property_name, value, property_type):
	name = f"Item-{fieldname}-{property_name}"
	if frappe.db.exists("Property Setter", name):
		frappe.db.set_value("Property Setter", name, "value", value, update_modified=False)
		return

	make_property_setter(
		"Item", fieldname, property_name, value, property_type, validate_fields_for_doctype=False
	)
