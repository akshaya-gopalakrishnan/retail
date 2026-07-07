"""Purchase Order helpers used by the Retail customisations."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.utils import flt

PURCHASE_ITEM_DOCTYPES = {
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
	"Supplier Quotation Item",
	"Material Request Item",
	"Subcontracting Order Item",
	"Subcontracting Receipt Item",
}

SALES_ITEM_DOCTYPES = {
	"Sales Order Item",
	"Delivery Note Item",
	"Sales Invoice Item",
	"POS Invoice Item",
	"Quotation Item",
	"Opportunity Item",
}

MIXED_ITEM_DOCTYPES = {
	"Blanket Order Item",
}

VAT_RATE_ITEM_DOCTYPES = PURCHASE_ITEM_DOCTYPES | SALES_ITEM_DOCTYPES | MIXED_ITEM_DOCTYPES

VAT_TAX_DOCTYPES = {
	"Purchase Order": "Purchase Tax",
	"Purchase Receipt": "Purchase Tax",
	"Purchase Invoice": "Purchase Tax",
	"Sales Order": "Sales Tax",
}


def set_balance_qty(doc, method=None):
	"""Keep each PO line's balance in sync when the order itself is saved."""
	for item in doc.get("items", []):
		if not item.meta.has_field("balance_qty"):
			continue
		item.balance_qty = flt(item.qty) - flt(item.received_qty)


def set_vat_rates(doc, method=None):
	"""Keep row VAT-inclusive/exclusive helper rates in sync before save."""
	for item in doc.get("items", []):
		if not item.get("item_code"):
			continue
		if not item.meta.has_field("custom_rate_including_vat"):
			continue

		vat_rate = get_transaction_item_vat_rate(
			item.item_code,
			child_doctype=item.doctype,
			parent_doctype=doc.doctype,
			transaction_type=doc.get("transaction_type"),
			throw=True,
		)
		exclusive_rate = flt(item.get("rate"))
		inclusive_rate = flt(item.get("custom_rate_including_vat"))

		if inclusive_rate and not exclusive_rate:
			exclusive_rate = inclusive_rate / (1 + (vat_rate / 100))

		if exclusive_rate:
			inclusive_rate = exclusive_rate * (1 + (vat_rate / 100))
			item.custom_rate_including_vat = flt(inclusive_rate, item.precision("rate"))
			item.rate = flt(exclusive_rate, item.precision("rate"))

		if item.meta.has_field("custom_amount_including_vat"):
			amount_precision = item.precision("amount") if item.meta.has_field("amount") else item.precision("rate")
			item.custom_amount_including_vat = flt(
				flt(item.get("qty")) * flt(item.get("custom_rate_including_vat")),
				amount_precision,
			)

	apply_transaction_vat_taxes(doc)


def apply_transaction_vat_taxes(doc):
	"""Mirror item VAT templates into the standard Taxes table for ERPNext totals."""
	tax_label = VAT_TAX_DOCTYPES.get(doc.doctype)
	if not tax_label or not doc.meta.has_field("taxes"):
		return

	doc.set(
		"taxes",
		[row for row in (doc.get("taxes") or []) if not _is_managed_vat_row(row, tax_label)],
	)

	for group in _get_transaction_vat_groups(doc, tax_label).values():
		if not group["amount"]:
			continue

		doc.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": group["account_head"],
				"description": group["description"],
				"category": "Total",
				"add_deduct_tax": "Add",
				"included_in_print_rate": 0,
				"rate": group["rate"],
				"tax_amount": flt(group["amount"], 2),
				"cost_center": doc.get("cost_center"),
			},
		)

	_disable_rounded_total(doc)
	doc.calculate_taxes_and_totals()
	_refresh_total_in_words(doc)


@frappe.whitelist()
def recalculate_vat_totals_for_document(doctype, name):
	"""Recalculate VAT rows and totals for one existing transaction document."""
	if doctype not in VAT_TAX_DOCTYPES:
		frappe.throw(frappe._("VAT total recalculation is not enabled for {0}.").format(doctype))

	doc = frappe.get_doc(doctype, name)
	set_vat_rates(doc)

	if doc.docstatus == 1:
		doc.flags.ignore_validate_update_after_submit = True

	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"grand_total": doc.grand_total,
		"total_taxes_and_charges": doc.total_taxes_and_charges,
	}


def _get_transaction_vat_groups(doc, tax_label):
	groups = {}
	for item in doc.get("items") or []:
		if not item.get("item_code"):
			continue

		template = _get_transaction_item_vat_template(
			item.item_code,
			child_doctype=item.doctype,
			parent_doctype=doc.doctype,
			transaction_type=doc.get("transaction_type"),
		)
		if not template:
			continue

		exclusive_amount = _get_item_exclusive_amount(item)
		for tax in _get_item_tax_template_details(template):
			rate = flt(tax.tax_rate)
			if not rate:
				continue

			key = (tax.tax_type, rate, template)
			if key not in groups:
				groups[key] = {
					"account_head": tax.tax_type,
					"rate": rate,
					"amount": 0,
					"description": f"{tax_label} [{template}]",
				}

			groups[key]["amount"] += exclusive_amount * rate / 100

	return groups


def sync_balance_qty_from_transaction(doc, method=None):
	"""Refresh affected PO lines after a receipt or stock-updating invoice."""
	if not frappe.db.has_column("Purchase Order Item", "balance_qty"):
		return

	purchase_orders = {
		item.purchase_order
		for item in doc.get("items", [])
		if item.get("purchase_order") and item.get("purchase_order_item")
	}
	if not purchase_orders:
		return

	placeholders = ", ".join(["%s"] * len(purchase_orders))
	frappe.db.sql(
		f"""
		UPDATE `tabPurchase Order Item`
		SET balance_qty = qty - received_qty
		WHERE parent IN ({placeholders})
		""",
		tuple(purchase_orders),
	)


def backfill_balance_qty():
	"""Populate the column for PO lines that existed before this feature."""
	# Fixture imports intentionally defer schema updates.  Applying it here keeps a
	# single migration sufficient when this customisation is deployed elsewhere.
	frappe.db.updatedb("Purchase Order Item")
	if frappe.db.has_column("Purchase Order Item", "balance_qty"):
		frappe.db.sql("UPDATE `tabPurchase Order Item` SET balance_qty = qty - received_qty")


def ensure_purchase_order_vat_rate_fields():
	"""Add VAT helper rate fields to transaction item rows."""
	fields = {
		item_doctype: [
			{
				"fieldname": "custom_rate_including_vat",
				"label": "Rate Including VAT",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "rate",
				"in_list_view": 1,
				"columns": 2,
			},
			{
				"fieldname": "custom_amount_including_vat",
				"label": "Amount Including VAT",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "custom_rate_including_vat",
				"in_list_view": 1,
				"read_only": 1,
				"columns": 2,
			},
		]
		for item_doctype in sorted(VAT_RATE_ITEM_DOCTYPES)
	}
	create_custom_fields(
		fields,
		ignore_validate=True,
	)
	for item_doctype in VAT_RATE_ITEM_DOCTYPES:
		_set_item_table_field_property(item_doctype, "rate", "label", "Rate Exclusive VAT", "Data")
		_delete_obsolete_vat_fields(item_doctype)
		frappe.db.updatedb(item_doctype)
		frappe.clear_cache(doctype=item_doctype)


@frappe.whitelist()
def get_purchase_item_vat_rate(item_code, throw=False):
	return get_transaction_item_vat_rate(
		item_code,
		child_doctype="Purchase Order Item",
		throw=throw,
	)


@frappe.whitelist()
def get_transaction_item_vat_rate(
	item_code,
	child_doctype=None,
	parent_doctype=None,
	transaction_type=None,
	throw=False,
):
	template = _get_transaction_item_vat_template(
		item_code,
		child_doctype=child_doctype,
		parent_doctype=parent_doctype,
		transaction_type=transaction_type,
		throw=throw,
	)
	if not template:
		return 0.0

	from retail.domains.item.vat_pricing import get_item_tax_rate

	return flt(get_item_tax_rate(template))


def _get_transaction_item_vat_template(
	item_code,
	child_doctype=None,
	parent_doctype=None,
	transaction_type=None,
	throw=False,
):
	template_field = _get_vat_template_field(child_doctype, parent_doctype, transaction_type)
	if not template_field:
		return None

	template = frappe.db.get_value("Item", item_code, template_field)
	if not template and throw:
		label = "Purchase VAT Template" if template_field == "custom_purchase_tax_template" else "Sales VAT Template"
		frappe.throw(
			frappe._("Set {0} in Item Master for item {1}.").format(label, item_code)
		)

	return template


def _get_vat_template_field(child_doctype=None, parent_doctype=None, transaction_type=None):
	if child_doctype in MIXED_ITEM_DOCTYPES or parent_doctype == "Blanket Order":
		return (
			"custom_purchase_tax_template"
			if transaction_type == "Purchasing"
			else "custom_tax"
		)
	if child_doctype in PURCHASE_ITEM_DOCTYPES or parent_doctype in {
		"Purchase Order",
		"Purchase Receipt",
		"Purchase Invoice",
		"Supplier Quotation",
		"Material Request",
		"Subcontracting Order",
		"Subcontracting Receipt",
	}:
		return "custom_purchase_tax_template"
	if child_doctype in SALES_ITEM_DOCTYPES or parent_doctype in {
		"Sales Order",
		"Delivery Note",
		"Sales Invoice",
		"POS Invoice",
		"Quotation",
		"Opportunity",
	}:
		return "custom_tax"
	return None


def _set_item_table_field_property(doctype, fieldname, property_name, value, property_type):
	property_setter_name = f"{doctype}-{fieldname}-{property_name}"
	if frappe.db.exists("Property Setter", property_setter_name):
		frappe.db.set_value("Property Setter", property_setter_name, "value", value, update_modified=False)
		return

	make_property_setter(
		doctype,
		fieldname,
		property_name,
		value,
		property_type,
		validate_fields_for_doctype=False,
	)


def _delete_obsolete_vat_fields(doctype):
	field_name = f"{doctype}-custom_rate_exclusive_vat"
	if frappe.db.exists("Custom Field", field_name):
		frappe.delete_doc(
			"Custom Field",
			field_name,
			ignore_permissions=True,
			force=True,
		)


def _get_item_tax_template_details(template):
	return frappe.get_all(
		"Item Tax Template Detail",
		filters={"parent": template},
		fields=["tax_type", "tax_rate"],
		limit_page_length=0,
	)


def _get_item_exclusive_amount(item):
	if item.get("rate") not in (None, ""):
		return flt(item.get("qty")) * flt(item.get("rate"))

	return flt(item.get("amount"))


def _is_managed_vat_row(row, tax_label):
	description = (row.get("description") or "").strip()
	return description.startswith(f"{tax_label} [")


def _disable_rounded_total(doc):
	if doc.meta.has_field("disable_rounded_total"):
		doc.disable_rounded_total = 1


def _refresh_total_in_words(doc):
	if hasattr(doc, "set_total_in_words"):
		doc.set_total_in_words()
