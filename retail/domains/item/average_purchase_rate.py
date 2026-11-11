"""Derive last and weighted-average purchase rates from submitted stock purchases."""

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
	"""Refresh purchase history without using maintained prices as a fallback."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Item", doc)
	rates = sync_item_purchase_history_rates(doc.name)
	for field, value in rates.items():
		doc.set(field, value)


def _purchase_rows(condition):
	# Invoice rows linked to receipts must not count the same stock twice.
	# Zero-cost receipt quantities belong in the weighted-average denominator.
	return f"""
		select pri.base_net_amount as amount, pri.stock_qty,
			pr.posting_date, pr.posting_time, pr.creation, pr.name, pri.idx, pri.is_free_item,
			'Purchase Receipt' as source
		from `tabPurchase Receipt Item` pri
		join `tabPurchase Receipt` pr on pr.name = pri.parent
		join `tabItem` item on item.name = pri.item_code
		where pr.docstatus = 1 and ifnull(pr.is_return, 0) = 0
			and pri.stock_qty > 0 and pri.base_net_amount >= 0 and {condition}
		union all
		select pii.base_net_amount as amount, pii.stock_qty,
			pi.posting_date, pi.posting_time, pi.creation, pi.name, pii.idx, pii.is_free_item,
			'Purchase Invoice' as source
		from `tabPurchase Invoice Item` pii
		join `tabPurchase Invoice` pi on pi.name = pii.parent
		join `tabItem` item on item.name = pii.item_code
		where pi.docstatus = 1 and ifnull(pi.is_return, 0) = 0
			and ifnull(pi.update_stock, 0) = 1
			and ifnull(pii.purchase_receipt, '') = ''
			and pii.stock_qty > 0 and pii.base_net_amount >= 0 and {condition}
	"""


def get_purchase_history_rates(item_code):
	"""Actual stock purchases in company currency per stock unit, ordered by posting time.

	Returns are not new purchases. Cancelled/draft documents, orders and non-stock
	invoices do not contribute. No history means zero, regardless of Item prices.
	"""
	rows = _purchase_rows("item.name = %(item_code)s")
	params = {"item_code": item_code}
	totals = frappe.db.sql(f"""
		select sum(amount) as total_amount, sum(stock_qty) as total_qty
		from ({rows}) purchases
	""", params, as_dict=True)[0]
	latest = frappe.db.sql(f"""
		select amount / stock_qty as rate
		from ({rows}) purchases
		where ifnull(is_free_item, 0) = 0
		order by posting_date desc, posting_time desc, creation desc, name desc, source desc, idx desc
		limit 1
	""", params, as_dict=True)
	qty = flt(totals.total_qty)
	return {
		"last_purchase_rate": flt(latest[0].rate) if latest else 0,
		"custom_average_purchase_rate": flt(totals.total_amount) / qty if qty else 0,
	}


def sync_item_purchase_history_rates(item_code):
	rates = get_purchase_history_rates(item_code)
	values = {key: value for key, value in rates.items() if frappe.db.has_column("Item", key)}
	if values:
		frappe.db.set_value("Item", item_code, values, update_modified=False)
	if frappe.db.has_column("Item Price", "custom_average_purchase_rate"):
		for name in frappe.get_all("Item Price", filters={"item_code": item_code}, pluck="name"):
			frappe.db.set_value("Item Price", name, "custom_average_purchase_rate",
				rates["custom_average_purchase_rate"], update_modified=False)
	frappe.clear_document_cache("Item", item_code)
	return rates


def sync_item_average_purchase_rate(item_code, fallback_rate=None):
	"""Compatibility entrypoint; maintained-price fallbacks are intentionally ignored."""
	return sync_item_purchase_history_rates(item_code)["custom_average_purchase_rate"]


def get_average_purchase_rate(item_code, fallback_rate=None):
	return get_purchase_history_rates(item_code)["custom_average_purchase_rate"]


def get_average_purchase_rate_for_item_name(item_name, fallback_rate=None):
	"""Historical same-name lookup; never treat maintained prices as purchases."""
	rows = _purchase_rows("item.item_name = %(item_name)s")
	totals = frappe.db.sql(f"""
		select sum(amount) as total_amount, sum(stock_qty) as total_qty
		from ({rows}) purchases
	""", {"item_name": item_name}, as_dict=True)[0]
	qty = flt(totals.total_qty)
	return flt(totals.total_amount) / qty if qty else 0


def backfill_average_purchase_rates():
	"""Repair Item history summaries and Item Price averages after migration."""
	if not frappe.db.has_column("Item", "custom_average_purchase_rate") and not frappe.db.has_column(
		"Item Price", "custom_average_purchase_rate"
	):
		return

	item_codes = set(frappe.get_all("Item Price", pluck="item_code", distinct=True))
	item_codes.update(frappe.get_all("Item", pluck="name"))
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
