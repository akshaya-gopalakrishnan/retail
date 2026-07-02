"""Purchase Order quantity helpers used by the Retail customisations."""

import frappe
from frappe.utils import flt


def set_balance_qty(doc, method=None):
	"""Keep each PO line's balance in sync when the order itself is saved."""
	for item in doc.get("items", []):
		if not item.meta.has_field("balance_qty"):
			continue
		item.balance_qty = flt(item.qty) - flt(item.received_qty)


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
