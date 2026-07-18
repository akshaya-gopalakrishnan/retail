from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt


SHIPPING_DESCRIPTION = "Shipping Charges"
VAT_DESCRIPTION_PREFIX = "Sales Tax"
TRANSACTION_TOTALS_DOCTYPES = (
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Sales Order",
)

ALL_TOTALS_DOCTYPES = (
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Sales Order",
	"Sales Invoice",
	"Delivery Note",
	"POS Invoice",
	"Quotation",
)

CUSTOM_TOTALS_FIELDS = (
	"custom_retail_totals_section",
	"custom_retail_totals_summary",
)

SALES_INVOICE_TOTALS_FIELDS = CUSTOM_TOTALS_FIELDS + ("custom_retail_shipping_charges",)

STANDARD_TAX_FIELDS_TO_HIDE = (
	"taxes_section",
	"taxes_charges_section",
	"taxes_and_charges",
	"taxes",
)

STANDARD_TOTAL_FIELDS_TO_HIDE = (
	"base_total_taxes_and_charges",
	"taxes_and_charges_added",
	"taxes_and_charges_deducted",
	"base_in_words",
	"base_rounded_total",
	"in_words",
	"advance_paid",
)

STANDARD_TOTAL_FIELDS_TO_SHOW = (
	"total",
	"net_total",
	"total_taxes_and_charges",
	"totals",
	"totals_section",
	"base_grand_total",
	"grand_total",
	"rounded_total",
	"disable_rounded_total",
)


def ensure_sales_invoice_retail_totals_fields():
	"""Deprecated: restore ERPNext's standard totals section."""
	remove_custom_transaction_totals_fields()


def ensure_transaction_totals_summary_fields():
	"""Deprecated: restore ERPNext's standard totals section."""
	remove_custom_transaction_totals_fields()


def _update_sales_invoice_retail_field_layout():
	"""Keep custom Sales Invoice fields in the intended positions even with field_order setters."""
	if frappe.db.exists("Custom Field", "Sales Invoice-custom_retail_totals_section"):
		frappe.db.set_value(
			"Custom Field",
			"Sales Invoice-custom_retail_totals_section",
			{"fieldtype": "Column Break", "insert_after": "net_total", "label": "Totals"},
			update_modified=False,
		)
	if frappe.db.exists("Custom Field", "Sales Invoice-custom_retail_totals_summary"):
		frappe.db.set_value(
			"Custom Field",
			"Sales Invoice-custom_retail_totals_summary",
			"label",
			"Totals Summary",
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
	_hide_standard_total_fields("Sales Invoice")

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


def _update_transaction_totals_field_layout(doctype):
	if frappe.db.exists("Custom Field", f"{doctype}-custom_retail_totals_section"):
		frappe.db.set_value(
			"Custom Field",
			f"{doctype}-custom_retail_totals_section",
			{"fieldtype": "Column Break", "insert_after": "net_total", "label": "Totals"},
			update_modified=False,
		)
	if frappe.db.exists("Custom Field", f"{doctype}-custom_retail_totals_summary"):
		frappe.db.set_value(
			"Custom Field",
			f"{doctype}-custom_retail_totals_summary",
			{"insert_after": "custom_retail_totals_section", "label": "Totals Summary"},
			update_modified=False,
		)

	for fieldname in ("total", "net_total"):
		make_property_setter(
			doctype,
			fieldname,
			"hidden",
			1,
			"Check",
			validate_fields_for_doctype=False,
		)
	_hide_standard_total_fields(doctype)

	field_order = _get_doctype_field_order(doctype)
	field_order = _place_after(
		field_order,
		"net_total",
		["custom_retail_totals_section", "custom_retail_totals_summary"],
	)

	make_property_setter(
		doctype,
		None,
		"field_order",
		json.dumps(field_order),
		"JSON",
		validate_fields_for_doctype=False,
	)


def _get_sales_invoice_field_order():
	return _get_doctype_field_order("Sales Invoice")


def _get_doctype_field_order(doctype):
	property_value = frappe.db.get_value(
		"Property Setter",
		{"doc_type": doctype, "property": "field_order", "field_name": ["is", "not set"]},
		"value",
	)
	if property_value:
		return json.loads(property_value)

	return [field.fieldname for field in frappe.get_meta(doctype).fields if field.fieldname]


def ensure_all_transaction_totals_fields():
	remove_custom_transaction_totals_fields()


def remove_custom_transaction_totals_fields():
	"""Restore ERPNext totals as the only totals UI/calculation surface."""
	for doctype in ALL_TOTALS_DOCTYPES:
		fields_to_remove = (
			SALES_INVOICE_TOTALS_FIELDS if doctype == "Sales Invoice" else CUSTOM_TOTALS_FIELDS
		)
		for fieldname in fields_to_remove:
			custom_field = f"{doctype}-{fieldname}"
			if frappe.db.exists("Custom Field", custom_field):
				frappe.delete_doc(
					"Custom Field",
					custom_field,
					ignore_permissions=True,
					force=True,
				)

		_apply_standard_totals_layout(doctype)
		_remove_fields_from_field_order(doctype, fields_to_remove)
		frappe.db.updatedb(doctype)
		frappe.clear_cache(doctype=doctype)


def _hide_standard_total_fields(doctype):
	meta = frappe.get_meta(doctype)
	for fieldname in (*STANDARD_TAX_FIELDS_TO_HIDE, *STANDARD_TOTAL_FIELDS_TO_HIDE):
		if not meta.has_field(fieldname):
			continue

		make_property_setter(
			doctype,
			fieldname,
			"hidden",
			1,
			"Check",
			validate_fields_for_doctype=False,
		)


def _apply_standard_totals_layout(doctype):
	meta = frappe.get_meta(doctype)
	for fieldname in (*STANDARD_TAX_FIELDS_TO_HIDE, *STANDARD_TOTAL_FIELDS_TO_HIDE):
		if not meta.has_field(fieldname):
			continue

		make_property_setter(
			doctype,
			fieldname,
			"hidden",
			1,
			"Check",
			validate_fields_for_doctype=False,
		)

	for fieldname in STANDARD_TOTAL_FIELDS_TO_SHOW:
		if not meta.has_field(fieldname):
			continue

		make_property_setter(
			doctype,
			fieldname,
			"hidden",
			0,
			"Check",
			validate_fields_for_doctype=False,
		)

	if meta.has_field("total_taxes_and_charges"):
		make_property_setter(
			doctype,
			"total_taxes_and_charges",
			"label",
			"VAT",
			"Data",
			validate_fields_for_doctype=False,
		)
		_place_total_taxes_before_grand_total(doctype)

	if meta.has_field("disable_rounded_total"):
		make_property_setter(
			doctype,
			"disable_rounded_total",
			"default",
			1,
			"Check",
			validate_fields_for_doctype=False,
		)


def _place_total_taxes_before_grand_total(doctype):
	field_order = _get_doctype_field_order(doctype)
	field_order = [field for field in field_order if field != "total_taxes_and_charges"]
	anchor = "grand_total"
	if anchor in field_order:
		field_order.insert(field_order.index(anchor), "total_taxes_and_charges")
	else:
		field_order.append("total_taxes_and_charges")

	make_property_setter(
		doctype,
		None,
		"field_order",
		json.dumps(field_order),
		"JSON",
		validate_fields_for_doctype=False,
	)


def _remove_fields_from_field_order(doctype, fieldnames):
	property_setter = frappe.db.get_value(
		"Property Setter",
		{"doc_type": doctype, "property": "field_order", "field_name": ["is", "not set"]},
		"name",
	)
	if not property_setter:
		return

	field_order = _get_doctype_field_order(doctype)
	cleaned = [field for field in field_order if field not in fieldnames]
	if cleaned == field_order:
		return

	frappe.db.set_value(
		"Property Setter",
		property_setter,
		"value",
		json.dumps(cleaned),
		update_modified=False,
	)


def _place_after(field_order, anchor, fieldnames):
	ordered = [field for field in field_order if field not in fieldnames]
	if anchor not in ordered:
		ordered.extend(field for field in fieldnames if field not in ordered)
		return ordered

	insert_at = ordered.index(anchor) + 1
	return ordered[:insert_at] + list(fieldnames) + ordered[insert_at:]


def apply_retail_shipping_charges(doc, method=None):
	"""Apply the legacy shipping row only when the old custom field exists."""
	has_shipping_field = doc.meta.has_field("custom_retail_shipping_charges")
	if not has_shipping_field:
		return

	doc.set(
		"taxes",
		[
			row
			for row in (doc.get("taxes") or [])
			if not _is_shipping_row(row)
		],
	)

	_append_shipping_row(doc)
	_disable_rounded_total(doc)
	doc.calculate_taxes_and_totals()
	_refresh_total_in_words(doc)


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


def _disable_rounded_total(doc):
	if doc.meta.has_field("disable_rounded_total"):
		doc.disable_rounded_total = 1


def _refresh_total_in_words(doc):
	if hasattr(doc, "set_total_in_words"):
		doc.set_total_in_words()
