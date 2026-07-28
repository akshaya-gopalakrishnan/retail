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

PACKING_VAT_FIELDS = {
	"purchase": {
		"entry": "purchase_rate",
		"mode": "purchase_vat_mode",
		"rate": "purchase_vat_rate",
		"confirmed": "purchase_vat_confirmed",
		"net": "purchase_net_rate",
		"vat": "purchase_vat_amount",
		"gross": "purchase_gross_rate",
		"status": "purchase_vat_status",
		"template": "custom_purchase_tax_template",
	},
	"selling": {
		"entry": "selling_rate",
		"mode": "selling_vat_mode",
		"rate": "selling_vat_rate",
		"confirmed": "selling_vat_confirmed",
		"net": "selling_net_rate",
		"vat": "selling_vat_amount",
		"gross": "selling_gross_rate",
		"status": "selling_vat_status",
		"template": "custom_tax",
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

DEFAULT_VAT_TEMPLATE_TITLE = "UAE VAT 5%"


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
					"default": "1",
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
					"reqd": 1,
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
					"default": "1",
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
	frappe.db.updatedb("Item")
	default_vat_template = get_default_vat_template()
	_set_field_property("custom_tax", "label", "Sales VAT Template", "Data")
	_set_field_property("custom_tax", "reqd", "1", "Check")
	_set_field_property("custom_purchase_tax_template", "reqd", "1", "Check")
	_set_field_property("custom_purchase_rate_includes_vat", "default", "1", "Check")
	_set_field_property("custom_sales_rate_includes_vat", "default", "1", "Check")
	if default_vat_template:
		_set_field_property("custom_tax", "default", default_vat_template, "Data")
		_set_field_property("custom_purchase_tax_template", "default", default_vat_template, "Data")
		_set_empty_item_vat_templates(default_vat_template)
	_set_field_property("custom_pricing_summary_section", "label", "Pricing Summary", "Data")
	_set_field_property("custom_vat_pricing_section", "label", "Purchase & Sales VAT Pricing", "Data")
	_set_field_property("custom_vat_pricing_section", "hidden", "1", "Check")
	_set_field_property("custom_b2b", "label", "B2B Price", "Data")
	_set_field_property("custom_margin", "label", "Margin", "Data")
	_set_field_property("custom_margin_", "label", "Margin %", "Data")
	_set_field_property("standard_rate", "hidden", "1", "Check")
	_set_field_property("last_purchase_rate", "read_only", "1", "Check")
	_set_field_property("custom_default_purchase_rate", "hidden", "1", "Check")
	_delete_obsolete_item_pricing_fields()
	arrange_item_vat_pricing_layout()
	ensure_item_pricing_list_view()
	frappe.clear_cache(doctype="Item")


def ensure_packing_vat_pricing_fields():
	"""Add VAT confirmation and breakdown fields to Retail Packing Detail rows."""
	create_custom_fields(
		{
			"Retail Packing Detail": [
				{
					"fieldname": "purchase_vat_status",
					"label": "P VAT",
					"fieldtype": "Data",
					"read_only": 1,
					"in_list_view": 1,
					"columns": 1,
					"insert_after": "purchase_rate",
				},
				{
					"fieldname": "selling_vat_status",
					"label": "S VAT",
					"fieldtype": "Data",
					"read_only": 1,
					"in_list_view": 1,
					"columns": 1,
					"insert_after": "selling_rate",
				},
				{
					"fieldname": "packing_vat_section",
					"label": "VAT Breakdown",
					"fieldtype": "Section Break",
					"insert_after": "selling_vat_status",
				},
				{
					"fieldname": "purchase_vat_mode",
					"label": "Purchase VAT Mode",
					"fieldtype": "Select",
					"options": "Excluding VAT\nIncluding VAT",
					"default": "Excluding VAT",
					"insert_after": "packing_vat_section",
				},
				{
					"fieldname": "purchase_vat_rate",
					"label": "Purchase VAT %",
					"fieldtype": "Percent",
					"insert_after": "purchase_vat_mode",
				},
				{
					"fieldname": "purchase_vat_confirmed",
					"label": "Purchase VAT Confirmed",
					"fieldtype": "Check",
					"default": "0",
					"insert_after": "purchase_vat_rate",
				},
				{
					"fieldname": "purchase_net_rate",
					"label": "Purchase Rate Excl. VAT",
					"fieldtype": "Currency",
					"read_only": 0,
					"insert_after": "purchase_vat_confirmed",
				},
				{
					"fieldname": "purchase_vat_amount",
					"label": "Purchase VAT Amount",
					"fieldtype": "Currency",
					"read_only": 1,
					"insert_after": "purchase_net_rate",
				},
				{
					"fieldname": "purchase_gross_rate",
					"label": "Purchase Rate Incl. VAT",
					"fieldtype": "Currency",
					"read_only": 0,
					"insert_after": "purchase_vat_amount",
				},
				{
					"fieldname": "packing_vat_column",
					"fieldtype": "Column Break",
					"insert_after": "purchase_gross_rate",
				},
				{
					"fieldname": "selling_vat_mode",
					"label": "Selling VAT Mode",
					"fieldtype": "Select",
					"options": "Excluding VAT\nIncluding VAT",
					"default": "Excluding VAT",
					"insert_after": "packing_vat_column",
				},
				{
					"fieldname": "selling_vat_rate",
					"label": "Selling VAT %",
					"fieldtype": "Percent",
					"insert_after": "selling_vat_mode",
				},
				{
					"fieldname": "selling_vat_confirmed",
					"label": "Selling VAT Confirmed",
					"fieldtype": "Check",
					"default": "0",
					"insert_after": "selling_vat_rate",
				},
				{
					"fieldname": "selling_net_rate",
					"label": "Selling Rate Excl. VAT",
					"fieldtype": "Currency",
					"read_only": 0,
					"insert_after": "selling_vat_confirmed",
				},
				{
					"fieldname": "selling_vat_amount",
					"label": "Selling VAT Amount",
					"fieldtype": "Currency",
					"read_only": 1,
					"insert_after": "selling_net_rate",
				},
				{
					"fieldname": "selling_gross_rate",
					"label": "Selling Rate Incl. VAT",
					"fieldtype": "Currency",
					"read_only": 0,
					"insert_after": "selling_vat_amount",
				},
				{
					"fieldname": "packing_margin",
					"label": "Margin Excl. VAT",
					"fieldtype": "Currency",
					"read_only": 1,
					"insert_after": "selling_gross_rate",
				},
			],
		},
		ignore_validate=True,
	)
	frappe.db.updatedb("Retail Packing Detail")
	for fieldname in ("purchase_net_rate", "purchase_gross_rate", "selling_net_rate", "selling_gross_rate"):
		_set_custom_field_value("Retail Packing Detail", fieldname, "read_only", 0)
	frappe.clear_cache(doctype="Retail Packing Detail")


def get_default_vat_template():
	"""Return the site-specific Item Tax Template used as the default 5% VAT template."""
	template = frappe.db.get_value("Item Tax Template", {"title": DEFAULT_VAT_TEMPLATE_TITLE}, "name")
	if template:
		return template

	detail = frappe.qb.DocType("Item Tax Template Detail")
	rows = (
		frappe.qb.from_(detail)
		.select(detail.parent)
		.where(detail.tax_rate == 5)
		.limit(1)
	).run()
	return rows[0][0] if rows else None


def _set_empty_item_vat_templates(default_vat_template):
	for fieldname in ("custom_tax", "custom_purchase_tax_template"):
		frappe.db.sql(
			f"""
			update `tabItem`
			set `{fieldname}` = %s
			where coalesce(`{fieldname}`, '') = ''
			""",
			default_vat_template,
		)


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
		"last_purchase_rate": "1",
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

	_sync_last_purchase_rate_from_item_master(doc)
	_update_margin(doc)
	update_packing_vat_prices(doc)


def sync_last_purchase_rate_from_item_master(doc, method=None):
	"""Persist the Item Master purchase entry as the latest maintained purchase rate."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Item", doc)

	rate = _get_item_master_purchase_rate(doc)
	if rate <= 0:
		return

	doc.set("last_purchase_rate", rate)
	frappe.db.set_value("Item", doc.name, "last_purchase_rate", rate, update_modified=False)


def backfill_item_master_last_purchase_rates():
	"""Repair existing Items where purchase entry exists but last purchase rate is stale."""
	if not frappe.db.has_column("Item", "custom_purchase_rate_entry"):
		return

	for item_code in frappe.get_all(
		"Item",
		filters={"custom_purchase_rate_entry": [">", 0]},
		pluck="name",
	):
		sync_last_purchase_rate_from_item_master(item_code)


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


def _sync_last_purchase_rate_from_item_master(doc):
	"""Use the Item Master purchase entry as this item's latest maintained buying rate."""
	rate = _get_item_master_purchase_rate(doc)
	if rate > 0:
		doc.set("last_purchase_rate", rate)


def _get_item_master_purchase_rate(doc):
	if doc.get("custom_purchase_rate_entry") in (None, ""):
		return 0

	return flt(doc.get("custom_purchase_net_rate") or doc.get("custom_default_purchase_rate"), 2)


def update_packing_vat_prices(doc):
	"""Recalculate VAT breakdowns held on each Retail Packing Detail row."""
	if not doc.meta.has_field("custom_retail_packing_detail"):
		return

	for row in doc.get("custom_retail_packing_detail") or []:
		for direction in PACKING_VAT_FIELDS:
			_apply_packing_direction(doc, row, direction)

		row.set("packing_margin", flt(row.get("selling_net_rate") - row.get("purchase_net_rate"), 2))


def _apply_packing_direction(doc, row, direction):
	fields = PACKING_VAT_FIELDS[direction]
	entry = flt(row.get(fields["entry"]))
	template = doc.get(fields["template"])
	default_rate = get_item_tax_rate(template) if template else 0.0
	rate = flt(row.get(fields["rate"]) if row.get(fields["rate"]) not in (None, "") else default_rate)
	mode = row.get(fields["mode"]) or "Excluding VAT"

	if mode == "Including VAT" and rate:
		net = entry / (1 + rate / 100)
		gross = entry
		vat = gross - net
	else:
		net = entry
		vat = net * rate / 100
		gross = net + vat

	row.set(fields["mode"], mode)
	row.set(fields["rate"], flt(rate, 3))
	row.set(fields["net"], flt(net, 2))
	row.set(fields["vat"], flt(vat, 2))
	row.set(fields["gross"], flt(gross, 2))
	row.set(fields["status"], _get_packing_vat_status(mode, rate, row.get(fields["confirmed"])))


def _get_packing_vat_status(mode, rate, confirmed):
	if not rate:
		return "Exempt"

	status = f"{'Incl' if mode == 'Including VAT' else 'Excl'} {flt(rate, 3):g}%"
	if confirmed:
		return f"{status} OK"

	return f"{status} Pending"


def _update_margin(doc):
	selling_net = _get_selling_net_rate(doc)
	cost_net = _get_cost_net_rate(doc)
	margin = selling_net - cost_net if selling_net else 0
	margin_percent = (margin / selling_net * 100) if selling_net else 0

	doc.set("custom_margin", flt(margin, 2))
	doc.set("custom_margin_", flt(margin_percent, 3))


def _get_selling_net_rate(doc):
	if flt(doc.get("custom_sales_rate_entry")) > 0:
		return flt(doc.get("custom_sales_net_rate"))

	return flt(doc.get("standard_rate"))


def _get_cost_net_rate(doc):
	if doc.get("custom_purchase_rate_entry") not in (None, ""):
		return flt(doc.get("custom_purchase_net_rate"))

	return flt(
		doc.get("custom_default_purchase_rate")
		or doc.get("last_purchase_rate")
		or doc.get("valuation_rate")
		or doc.get("custom_average_purchase_rate")
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


def _set_custom_field_value(doctype, fieldname, property_name, value):
	name = f"{doctype}-{fieldname}"
	if frappe.db.exists("Custom Field", name):
		frappe.db.set_value("Custom Field", name, property_name, value, update_modified=False)
