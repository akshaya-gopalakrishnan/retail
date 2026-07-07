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
}

SALES_ITEM_DOCTYPES = {
	"Sales Order Item",
	"Delivery Note Item",
	"Sales Invoice Item",
	"POS Invoice Item",
	"Quotation Item",
}

VAT_RATE_ITEM_DOCTYPES = PURCHASE_ITEM_DOCTYPES | SALES_ITEM_DOCTYPES


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
def get_transaction_item_vat_rate(item_code, child_doctype=None, parent_doctype=None, throw=False):
	template_field = _get_vat_template_field(child_doctype, parent_doctype)
	if not template_field:
		return 0.0

	template = frappe.db.get_value("Item", item_code, template_field)
	if not template:
		if throw:
			label = "Purchase VAT Template" if template_field == "custom_purchase_tax_template" else "Sales VAT Template"
			frappe.throw(
				frappe._("Set {0} in Item Master for item {1}.").format(label, item_code)
			)
		return 0.0

	from retail.domains.item.vat_pricing import get_item_tax_rate

	return flt(get_item_tax_rate(template))


def _get_vat_template_field(child_doctype=None, parent_doctype=None):
	if child_doctype in PURCHASE_ITEM_DOCTYPES or parent_doctype in {
		"Purchase Order",
		"Purchase Receipt",
		"Purchase Invoice",
		"Supplier Quotation",
	}:
		return "custom_purchase_tax_template"
	if child_doctype in SALES_ITEM_DOCTYPES or parent_doctype in {
		"Sales Order",
		"Delivery Note",
		"Sales Invoice",
		"POS Invoice",
		"Quotation",
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
