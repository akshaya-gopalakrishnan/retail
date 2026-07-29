"""Keep a weighted purchase-cost reference on Item Price records."""

import json

import frappe
from frappe.utils import flt


def sync_average_purchase_rates(doc, method=None):
	"""Refresh the affected items when a stock purchase is submitted or cancelled."""
	if isinstance(doc, str):
		doc = frappe.get_doc(doc)

	item_codes = {row.item_code for row in doc.get("items", []) if row.item_code}
	for item_code in item_codes:
		sync_item_average_purchase_rate(item_code)


def clear_average_purchase_rate_description():
	"""Keep the Item Master cost field free of explanatory form text.

	The description used to be stored in site-level Custom Field metadata, which
	can survive fixture changes.  Clear it during migration as well as on a new
	installation so the Item form stays consistent across every Retail site.
	"""
	field_name = "Item-custom_average_purchase_rate"
	if frappe.db.exists("Custom Field", field_name):
		frappe.db.set_value("Custom Field", field_name, "description", "", update_modified=False)
		frappe.clear_cache(doctype="Item")


def sync_average_purchase_rate_from_item(doc, method=None):
	"""Refresh the fallback cost when an Item Master rate is maintained."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Item", doc)
	sync_item_average_purchase_rate(
		doc.name,
		fallback_rate=doc.get("custom_average_purchase_rate")
		or doc.get("custom_default_purchase_rate")
		or doc.get("last_purchase_rate"),
	)


def sync_item_average_purchase_rate(item_code, fallback_rate=None):
	"""Store the quantity-weighted received cost on every Item Price for an item.

	Purchase Receipts are the normal stock-receipt source. Purchase Invoices are
	included only when they update stock directly, avoiding double counting an
	invoice made against a receipt.
	"""
	average_rate = get_average_purchase_rate(item_code, fallback_rate=fallback_rate)
	if frappe.db.has_column("Item", "custom_average_purchase_rate"):
		frappe.db.set_value(
			"Item", item_code, "custom_average_purchase_rate", average_rate, update_modified=False
		)

	if not frappe.db.has_column("Item Price", "custom_average_purchase_rate"):
		return average_rate

	for price_name in frappe.get_all("Item Price", filters={"item_code": item_code}, pluck="name"):
		frappe.db.set_value(
			"Item Price",
			price_name,
			"custom_average_purchase_rate",
			average_rate,
			update_modified=False,
		)
	return average_rate


def get_average_purchase_rate(item_code, fallback_rate=None):
	"""Return weighted average unit cost from submitted stock purchases."""
	result = frappe.db.sql(
		"""
			select
				sum(base_amount) as total_amount,
				sum(stock_qty) as total_qty
			from (
				select pri.base_net_amount as base_amount, pri.stock_qty
				from `tabPurchase Receipt Item` pri
				inner join `tabPurchase Receipt` pr on pr.name = pri.parent
				where pr.docstatus = 1 and pri.item_code = %(item_code)s
					and pri.stock_qty > 0
					and pri.base_net_amount > 0

				union all

				select pii.base_net_amount as base_amount, pii.stock_qty
				from `tabPurchase Invoice Item` pii
				inner join `tabPurchase Invoice` pi on pi.name = pii.parent
				where pi.docstatus = 1
					and ifnull(pi.update_stock, 0) = 1
					and pii.item_code = %(item_code)s
					and pii.stock_qty > 0
					and pii.base_net_amount > 0
			) purchases
		""",
		{"item_code": item_code},
		as_dict=True,
	)[0]

	total_qty = flt(result.total_qty)
	if total_qty:
		return flt(result.total_amount) / total_qty

	# A manually maintained Item Master purchase rate is an opening/expected
	# cost until real purchase history exists; it is never mixed into the
	# weighted calculation because it has no transaction quantity.
	if fallback_rate is None:
		fields = ["last_purchase_rate"]
		if frappe.db.has_column("Item", "custom_default_purchase_rate"):
			fields.insert(0, "custom_default_purchase_rate")
		fallback = frappe.db.get_value("Item", item_code, fields, as_dict=True)
		fallback_rate = (fallback.get("custom_default_purchase_rate") if fallback else None) or (
			fallback.get("last_purchase_rate") if fallback else None
		)
	return flt(fallback_rate)


def get_average_purchase_rate_for_item_name(item_name, fallback_rate=None):
	"""Return weighted average unit cost across existing items with the same item name."""
	result = frappe.db.sql(
		"""
			select
				sum(base_amount) as total_amount,
				sum(stock_qty) as total_qty
			from (
				select pri.base_net_amount as base_amount, pri.stock_qty
				from `tabPurchase Receipt Item` pri
				inner join `tabPurchase Receipt` pr on pr.name = pri.parent
				inner join `tabItem` item on item.name = pri.item_code
				where pr.docstatus = 1
					and item.item_name = %(item_name)s
					and pri.stock_qty > 0
					and pri.base_net_amount > 0

				union all

				select pii.base_net_amount as base_amount, pii.stock_qty
				from `tabPurchase Invoice Item` pii
				inner join `tabPurchase Invoice` pi on pi.name = pii.parent
				inner join `tabItem` item on item.name = pii.item_code
				where pi.docstatus = 1
					and ifnull(pi.update_stock, 0) = 1
					and item.item_name = %(item_name)s
					and pii.stock_qty > 0
					and pii.base_net_amount > 0
			) purchases
		""",
		{"item_name": item_name},
		as_dict=True,
	)[0]

	total_qty = flt(result.total_qty)
	if total_qty:
		return flt(result.total_amount) / total_qty

	return flt(fallback_rate)


def backfill_average_purchase_rates():
	"""Populate the field for all existing Item Price records after migration."""
	if not frappe.db.has_column("Item", "custom_average_purchase_rate") and not frappe.db.has_column(
		"Item Price", "custom_average_purchase_rate"
	):
		return

	item_codes = set(frappe.get_all("Item Price", pluck="item_code", distinct=True))
	item_codes.update(frappe.get_all("Item", filters={"is_stock_item": 1}, pluck="name"))
	for item_code in item_codes:
		sync_item_average_purchase_rate(item_code)


def ensure_item_price_list_field():
	"""Keep the cost column visible in the default Item Price list layout."""
	fieldnames = [
		"item_code",
		"item_name",
		"brand",
		"price_list",
		"price_list_rate",
		"custom_barcode",
		"custom_average_purchase_rate",
	]

	if frappe.db.exists("List View Settings", "Item Price"):
		settings = frappe.get_doc("List View Settings", "Item Price")
		try:
			saved_fields = [field.get("fieldname") for field in json.loads(settings.fields or "[]")]
			if saved_fields:
				fieldnames = saved_fields
		except (TypeError, json.JSONDecodeError):
			pass
		if "custom_average_purchase_rate" not in fieldnames:
			fieldnames.append("custom_average_purchase_rate")
		if "custom_barcode" not in fieldnames:
			insert_at = fieldnames.index("price_list_rate") + 1 if "price_list_rate" in fieldnames else len(fieldnames)
			fieldnames.insert(insert_at, "custom_barcode")
	else:
		settings = frappe.new_doc("List View Settings")
		settings.name = "Item Price"

	settings.fields = json.dumps([{"fieldname": fieldname} for fieldname in fieldnames])
	settings.total_fields = str(max(6, len(fieldnames)))
	settings.save(ignore_permissions=True)
	frappe.clear_cache(doctype="Item Price")
