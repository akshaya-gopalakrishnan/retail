import frappe
from frappe.utils import flt, getdate

from retail.domains.transactions.vat import apply_transaction_vat_taxes, get_transaction_item_vat_rate


SALES_DOCTYPES = {"Sales Invoice", "POS Invoice"}


def apply_inclusive_promo_prices(doc, method=None):
	"""Apply fixed promo prices that are stored as customer-facing VAT-inclusive prices."""
	if doc.doctype not in SALES_DOCTYPES or doc.get("is_return"):
		return

	promotions = get_active_promo_prices(doc)
	if not promotions:
		return

	changed = False
	for item in doc.get("items") or []:
		promo_row = get_matching_inclusive_promo_row(doc, item, promotions)
		if not promo_row:
			continue

		vat_rate = get_transaction_item_vat_rate(
			item.item_code,
			child_doctype=item.doctype,
			parent_doctype=doc.doctype,
			transaction_type=doc.get("transaction_type"),
			item_tax_template=item.get("item_tax_template"),
			throw=True,
		)
		inclusive_rate = flt(promo_row.promo_price_including_tax)
		exclusive_rate = inclusive_rate / (1 + (vat_rate / 100))

		item.rate = flt(exclusive_rate, item.precision("rate"))
		item.amount = flt(item.rate * flt(item.qty), item.precision("amount"))
		if item.meta.has_field("custom_rate_including_vat"):
			item.custom_rate_including_vat = flt(inclusive_rate, item.precision("rate"))
		if item.meta.has_field("custom_amount_including_vat"):
			item.custom_amount_including_vat = flt(inclusive_rate * flt(item.qty), item.precision("amount"))

		item.discount_percentage = 0
		item.discount_amount = 0
		changed = True

	if changed:
		apply_transaction_vat_taxes(doc)


def get_active_promo_prices(doc):
	filters = {
		"disabled": 0,
		"active_from": ["<=", getdate(doc.get("posting_date") or doc.get("transaction_date"))],
		"active_to": [">=", getdate(doc.get("posting_date") or doc.get("transaction_date"))],
	}
	if doc.get("company"):
		filters["company"] = ["in", ("", doc.company)]

	names = frappe.get_all("Promo Price", filters=filters, pluck="name", order_by="priority desc, modified desc")
	promotions = [frappe.get_doc("Promo Price", name) for name in names]
	return [promotion for promotion in promotions if promotion_matches_doc(promotion, doc)]


def promotion_matches_doc(promotion, doc):
	if promotion.company and doc.get("company") and promotion.company != doc.company:
		return False
	if not promotion.warehouse:
		return True

	warehouses = {row.warehouse for row in doc.get("items") or [] if row.get("warehouse")}
	return promotion.warehouse in warehouses


def get_matching_inclusive_promo_row(doc, item, promotions):
	matches = []
	for promotion in promotions:
		for row in promotion.get("products") or []:
			if not flt(row.promo_price_including_tax):
				continue
			if not row_matches_item(row, item):
				continue
			if row.price_list and doc.get("selling_price_list") and row.price_list != doc.selling_price_list:
				continue
			if promotion.warehouse and item.get("warehouse") and promotion.warehouse != item.warehouse:
				continue
			if flt(promotion.min_qty) and flt(item.qty) < flt(promotion.min_qty):
				continue
			max_qty = flt(row.max_qty) or flt(promotion.max_qty)
			if max_qty and flt(item.qty) > max_qty:
				continue
			if flt(promotion.min_sales_value) and get_doc_gross_total(doc) < flt(promotion.min_sales_value):
				continue

			matches.append((flt(promotion.priority), promotion.modified, row))

	if not matches:
		return None

	matches.sort(key=lambda match: (match[0], match[1]), reverse=True)
	return matches[0][2]


def row_matches_item(row, item):
	if row.uom and item.get("uom") and row.uom != item.uom:
		return False
	if row.item:
		return row.item == item.item_code
	if row.item_group:
		return row.item_group == item.get("item_group") or item_belongs_to_group(item.item_code, row.item_group)
	return False


def item_belongs_to_group(item_code, item_group):
	if not item_code or not item_group:
		return False

	item_group_name = frappe.db.get_value("Item", item_code, "item_group")
	if not item_group_name:
		return False

	lft, rgt = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"]) or (None, None)
	if not lft or not rgt:
		return item_group_name == item_group

	return bool(
		frappe.db.exists(
			"Item Group",
			{
				"name": item_group_name,
				"lft": [">=", lft],
				"rgt": ["<=", rgt],
			},
		)
	)


def get_doc_gross_total(doc):
	total = 0
	for item in doc.get("items") or []:
		if item.meta.has_field("custom_amount_including_vat") and flt(item.get("custom_amount_including_vat")):
			total += flt(item.custom_amount_including_vat)
		else:
			total += flt(item.amount)
	return total
