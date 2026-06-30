"""Item-master VAT price conversion with net rates as the accounting base."""

from __future__ import annotations

import json

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

ITEM_PRICING_LAYOUT_FIELDS = [
	"custom_pricing_summary_section",
	"last_purchase_rate",
	"custom_pricing_row_1_column",
	"custom_average_purchase_rate",
	"custom_pricing_row_2",
	"custom_purchase_rate_entry",
	"custom_pricing_row_2_column",
	"custom_sales_rate_entry",
	"custom_pricing_row_3",
	"custom_purchase_tax_template",
	"custom_pricing_row_3_column",
	"custom_tax",
	"custom_pricing_row_4",
	"custom_purchase_rate_includes_vat",
	"custom_pricing_row_4_column",
	"custom_sales_rate_includes_vat",
	"custom_pricing_row_5",
	"custom_purchase_net_rate",
	"custom_pricing_row_5_column",
	"custom_sales_net_rate",
	"custom_pricing_row_6",
	"custom_purchase_vat_amount",
	"custom_pricing_row_6_column",
	"custom_sales_vat_amount",
	"custom_pricing_row_7",
	"custom_purchase_gross_rate",
	"custom_pricing_row_7_column",
	"custom_sales_gross_rate",
	"custom_pricing_row_8",
	"valuation_rate",
	"custom_pricing_row_8_column",
	"custom_b2b",
	"custom_pricing_row_8_column_2",
	"custom_margin",
	"custom_pricing_row_8_column_3",
	"custom_margin_",
	"custom_default_purchase_rate",
	"standard_rate",
]

OBSOLETE_ITEM_PRICING_FIELDS = (
	"custom_pricing_summary_column",
	"custom_pricing_summary_column_2",
	"custom_pricing_summary_column_3",
	"custom_vat_purchase_column",
	"custom_pricing_summary_metrics_section",
	"custom_price_metrics_section",
	"custom_price_metrics_column_1",
	"custom_price_metrics_column_2",
	"custom_price_metrics_column_3",
	"custom_pricing_row_9",
	"custom_pricing_row_9_column",
	"custom_column_break_kcr7n",
)


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
					"fieldname": "custom_pricing_row_1_column",
					"fieldtype": "Column Break",
					"insert_after": "last_purchase_rate",
				},
				{
					"fieldname": "custom_pricing_row_2",
					"fieldtype": "Section Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_2_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_3",
					"fieldtype": "Section Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_3_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_4",
					"fieldtype": "Section Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_4_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_5",
					"fieldtype": "Section Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_5_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_6",
					"fieldtype": "Section Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_6_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_7",
					"fieldtype": "Section Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_7_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_8",
					"fieldtype": "Section Break",
					"insert_after": "custom_pricing_summary_section",
				},
				{
					"fieldname": "custom_pricing_row_8_column",
					"fieldtype": "Column Break",
					"insert_after": "valuation_rate",
				},
				{
					"fieldname": "custom_pricing_row_8_column_2",
					"fieldtype": "Column Break",
					"insert_after": "custom_b2b",
				},
				{
					"fieldname": "custom_pricing_row_8_column_3",
					"fieldtype": "Column Break",
					"insert_after": "custom_margin",
				},
				{
					"fieldname": "custom_vat_pricing_section",
					"label": "VAT Pricing",
					"fieldtype": "Section Break",
					"insert_after": "custom_margin_",
				},
				{
					"fieldname": "custom_sales_rate_entry",
					"label": "Selling Rate Entered",
					"fieldtype": "Currency",
					"insert_after": "custom_tax",
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
					"insert_after": "custom_purchase_tax_template",
				},
				{
					"fieldname": "custom_purchase_rate_includes_vat",
					"label": "Purchase Rate Includes VAT",
					"fieldtype": "Check",
					"default": "0",
					"insert_after": "custom_purchase_rate_entry",
				},
				{
					"fieldname": "custom_purchase_net_rate",
					"label": "Purchase Net Rate",
					"fieldtype": "Currency",
					"read_only": 1,
					"insert_after": "custom_purchase_rate_includes_vat",
				},
				{
					"fieldname": "custom_purchase_vat_amount",
					"label": "Purchase VAT Amount",
					"fieldtype": "Currency",
					"read_only": 1,
					"insert_after": "custom_purchase_net_rate",
				},
				{
					"fieldname": "custom_purchase_gross_rate",
					"label": "Purchase Rate Including VAT",
					"fieldtype": "Currency",
					"read_only": 1,
					"insert_after": "custom_purchase_vat_amount",
				},
			]
		},
		ignore_validate=True,
	)
	_set_field_property("custom_tax", "label", "Sales VAT Template", "Data")
	_set_field_property("custom_pricing_summary_section", "label", "Pricing Summary", "Data")
	_set_field_property("custom_vat_pricing_section", "label", "Purchase & Sales VAT Pricing", "Data")
	_set_field_property("custom_vat_pricing_section", "hidden", "1", "Check")
	_set_field_property("custom_b2b", "label", "B2B Price", "Data")
	_set_field_property("custom_margin", "label", "Margin", "Data")
	_set_field_property("custom_margin_", "label", "Margin %", "Data")
	_set_field_property("standard_rate", "hidden", "1", "Check")
	_set_field_property("custom_default_purchase_rate", "hidden", "1", "Check")
	_delete_obsolete_item_pricing_fields()
	arrange_item_vat_pricing_layout()
	ensure_item_pricing_list_view()
	frappe.clear_cache(doctype="Item")


def arrange_item_vat_pricing_layout():
	"""Arrange Item pricing into clean paired rows: left field and right field."""
	insert_after = {
		"custom_pricing_summary_section": "custom_pricing__tax",

		# Row 1: purchase history side by side
		"last_purchase_rate": "custom_pricing_summary_section",
		"custom_pricing_row_1_column": "last_purchase_rate",
		"custom_average_purchase_rate": "custom_pricing_row_1_column",

		# Row 2: purchase rate / sales rate
		"custom_pricing_row_2": "custom_average_purchase_rate",
		"custom_purchase_rate_entry": "custom_pricing_row_2",
		"custom_pricing_row_2_column": "custom_purchase_rate_entry",
		"custom_sales_rate_entry": "custom_pricing_row_2_column",

		# Row 3: VAT templates
		"custom_pricing_row_3": "custom_sales_rate_entry",
		"custom_purchase_tax_template": "custom_pricing_row_3",
		"custom_pricing_row_3_column": "custom_purchase_tax_template",
		"custom_tax": "custom_pricing_row_3_column",

		# Row 4: VAT include checkboxes
		"custom_pricing_row_4": "custom_tax",
		"custom_purchase_rate_includes_vat": "custom_pricing_row_4",
		"custom_pricing_row_4_column": "custom_purchase_rate_includes_vat",
		"custom_sales_rate_includes_vat": "custom_pricing_row_4_column",

		# Row 5: net rates
		"custom_pricing_row_5": "custom_sales_rate_includes_vat",
		"custom_purchase_net_rate": "custom_pricing_row_5",
		"custom_pricing_row_5_column": "custom_purchase_net_rate",
		"custom_sales_net_rate": "custom_pricing_row_5_column",

		# Row 6: VAT amounts
		"custom_pricing_row_6": "custom_sales_net_rate",
		"custom_purchase_vat_amount": "custom_pricing_row_6",
		"custom_pricing_row_6_column": "custom_purchase_vat_amount",
		"custom_sales_vat_amount": "custom_pricing_row_6_column",

		# Row 7: gross rates
		"custom_pricing_row_7": "custom_sales_vat_amount",
		"custom_purchase_gross_rate": "custom_pricing_row_7",
		"custom_pricing_row_7_column": "custom_purchase_gross_rate",
		"custom_sales_gross_rate": "custom_pricing_row_7_column",

		# Row 8: valuation / B2B / margin / margin percent in one line
		"custom_pricing_row_8": "custom_sales_gross_rate",
		"valuation_rate": "custom_pricing_row_8",
		"custom_pricing_row_8_column": "valuation_rate",
		"custom_b2b": "custom_pricing_row_8_column",
		"custom_pricing_row_8_column_2": "custom_b2b",
		"custom_margin": "custom_pricing_row_8_column_2",
		"custom_pricing_row_8_column_3": "custom_margin",
		"custom_margin_": "custom_pricing_row_8_column_3",
	}

	for fieldname, previous_field in insert_after.items():
		name = f"Item-{fieldname}"
		if frappe.db.exists("Custom Field", name):
			frappe.db.set_value("Custom Field", name, "insert_after", previous_field, update_modified=False)

	for fieldname, previous_field in {
		"last_purchase_rate": "custom_pricing_summary_section",
		"custom_average_purchase_rate": "custom_pricing_row_1_column",
		"valuation_rate": "custom_pricing_row_8",
	}.items():
		_set_field_property(fieldname, "insert_after", previous_field, "Data")

	_set_item_pricing_field_order()


def _delete_obsolete_item_pricing_fields():
	for fieldname in OBSOLETE_ITEM_PRICING_FIELDS:
		name = f"Item-{fieldname}"
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, force=True, ignore_permissions=True)


def _set_item_pricing_field_order():
	property_setter = "Item-main-field_order"
	field_order = _get_item_field_order(property_setter)
	pricing_fields = set(ITEM_PRICING_LAYOUT_FIELDS)
	pricing_fields.update(OBSOLETE_ITEM_PRICING_FIELDS)
	pricing_fields.update({"custom_vat_pricing_section", "custom_column_break_kcr7n"})

	rebuilt = []
	inserted = False
	for fieldname in field_order:
		if fieldname in pricing_fields:
			continue

		rebuilt.append(fieldname)
		if fieldname == "custom_pricing__tax":
			rebuilt.extend(ITEM_PRICING_LAYOUT_FIELDS)
			inserted = True

	if not inserted:
		rebuilt.extend(ITEM_PRICING_LAYOUT_FIELDS)

	value = json.dumps(rebuilt)
	if frappe.db.exists("Property Setter", property_setter):
		frappe.db.set_value("Property Setter", property_setter, "value", value, update_modified=False)
		return

	make_property_setter("Item", "main", "field_order", value, "Data", validate_fields_for_doctype=False)


def ensure_item_pricing_list_view():
	"""Show customer-facing VAT-inclusive prices in the Item list."""
	for fieldname, in_list_view in {
		"last_purchase_rate": "0",
		"standard_rate": "0",
		"custom_purchase_gross_rate": "1",
		"custom_sales_gross_rate": "1",
		"custom_margin": "1",
	}.items():
		_set_field_property(fieldname, "in_list_view", in_list_view, "Check")

	fields = [
		{"fieldname": "item_name", "label": "Item Name"},
		{"fieldname": "status_field", "label": "Status"},
		{"fieldname": "brand", "label": "Brand"},
		{"fieldname": "item_group", "label": "Item Group"},
		{"fieldname": "custom_purchase_gross_rate", "label": "Purchase Rate Incl. VAT"},
		{"fieldname": "custom_sales_gross_rate", "label": "Selling Rate Incl. VAT"},
		{"fieldname": "custom_margin", "label": "Margin"},
	]

	if frappe.db.exists("List View Settings", "Item"):
		settings = frappe.get_doc("List View Settings", "Item")
	else:
		settings = frappe.new_doc("List View Settings")
		settings.name = "Item"

	settings.fields = json.dumps(fields)
	settings.total_fields = str(len(fields))
	settings.save(ignore_permissions=True)
	frappe.clear_cache(doctype="Item")


def _get_item_field_order(property_setter):
	value = frappe.db.get_value("Property Setter", property_setter, "value")
	if value:
		try:
			return json.loads(value)
		except (TypeError, ValueError):
			pass

	return [field.fieldname for field in frappe.get_meta("Item").fields]


def update_item_vat_prices(doc, method=None):
	"""Recalculate item VAT figures and persist net rates used by accounting."""
	if not doc.meta.has_field("custom_sales_rate_entry"):
		return

	for direction in VAT_PRICE_FIELDS:
		_apply_direction(doc, direction)

	_update_margin(doc)


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


def _update_margin(doc):
	selling_net = _get_selling_net_rate(doc)
	cost_net = _get_cost_net_rate(doc)
	margin = selling_net - cost_net
	margin_percent = (margin / selling_net * 100) if selling_net else 0

	doc.set("custom_margin", flt(margin, 2))
	doc.set("custom_margin_", flt(margin_percent, 3))


def _get_selling_net_rate(doc):
	if doc.get("custom_sales_rate_entry") not in (None, ""):
		return flt(doc.get("custom_sales_net_rate"))

	return flt(doc.get("standard_rate") or doc.get("custom_b2b"))


def _get_cost_net_rate(doc):
	if doc.get("custom_purchase_rate_entry") not in (None, ""):
		return flt(doc.get("custom_purchase_net_rate"))

	return flt(
		doc.get("custom_average_purchase_rate")
		or doc.get("custom_default_purchase_rate")
		or doc.get("last_purchase_rate")
		or doc.get("valuation_rate")
	)


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
