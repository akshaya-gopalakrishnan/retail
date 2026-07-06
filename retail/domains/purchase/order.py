"""Purchase Order helpers used by the Retail customisations."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


def set_balance_qty(doc, method=None):
	"""Keep each PO line's balance in sync when the order itself is saved."""
	for item in doc.get("items", []):
		if not item.meta.has_field("balance_qty"):
			continue
		item.balance_qty = flt(item.qty) - flt(item.received_qty)


def set_vat_rates(doc, method=None):
	"""Keep PO row VAT-inclusive/exclusive helper rates in sync before save."""
	for item in doc.get("items", []):
		if not item.get("item_code"):
			continue
		if not item.meta.has_field("custom_rate_exclusive_vat"):
			continue

		vat_rate = get_purchase_item_vat_rate(item.item_code, throw=True)
		exclusive_rate = flt(item.get("custom_rate_exclusive_vat"))
		inclusive_rate = flt(item.get("custom_rate_including_vat"))

		if inclusive_rate and not exclusive_rate:
			exclusive_rate = inclusive_rate / (1 + (vat_rate / 100))

		if exclusive_rate:
			inclusive_rate = exclusive_rate * (1 + (vat_rate / 100))
			item.custom_rate_exclusive_vat = flt(exclusive_rate, item.precision("rate"))
			item.custom_rate_including_vat = flt(inclusive_rate, item.precision("rate"))
			item.rate = item.custom_rate_exclusive_vat
		elif item.get("rate"):
			item.custom_rate_exclusive_vat = flt(item.rate, item.precision("rate"))
			item.custom_rate_including_vat = flt(
				item.custom_rate_exclusive_vat * (1 + (vat_rate / 100)),
				item.precision("rate"),
			)


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
	"""Add VAT helper rate fields to Purchase Order Item rows."""
	create_custom_fields(
		{
			"Purchase Order Item": [
				{
					"fieldname": "custom_rate_exclusive_vat",
					"label": "Rate Exclusive VAT",
					"fieldtype": "Currency",
					"options": "currency",
					"insert_after": "rate",
					"in_list_view": 1,
					"columns": 2,
				},
				{
					"fieldname": "custom_rate_including_vat",
					"label": "Rate Including VAT",
					"fieldtype": "Currency",
					"options": "currency",
					"insert_after": "custom_rate_exclusive_vat",
					"in_list_view": 1,
					"columns": 2,
				},
			]
		},
		ignore_validate=True,
	)
	frappe.db.updatedb("Purchase Order Item")
	frappe.clear_cache(doctype="Purchase Order Item")


@frappe.whitelist()
def get_purchase_item_vat_rate(item_code, throw=False):
	template = frappe.db.get_value("Item", item_code, "custom_purchase_tax_template")
	if not template:
		if throw:
			frappe.throw(
				frappe._("Set Purchase VAT Template in Item Master for item {0}.").format(item_code)
			)
		return 0.0

	from retail.domains.item.vat_pricing import get_item_tax_rate

	return flt(get_item_tax_rate(template))
