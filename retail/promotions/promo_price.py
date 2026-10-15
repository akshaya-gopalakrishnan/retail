import frappe
from frappe.utils import flt
from retail.promotions.schedule import is_active

from retail.domains.item.vat_pricing import get_item_tax_rate
from retail.domains.transactions.vat import apply_transaction_vat_taxes, get_transaction_item_vat_rate


SALES_DOCTYPES = {"Sales Invoice", "POS Invoice"}


@frappe.whitelist()
def get_item_for_promo_price(barcode=None, price_list=None, item_code=None, uom=None):
	"""Return item and current selling VAT prices for a barcode or item code."""
	barcode = (barcode or "").strip()
	item_uom = uom
	if not item_code:
		if not barcode:
			frappe.throw("Scan or select an item.")
		barcode_data = frappe.db.get_value(
			"Item Barcode", {"barcode": barcode}, ["parent as item_code", "uom"], as_dict=True
		)
		item_code = barcode_data.item_code if barcode_data else None
		item_uom = barcode_data.uom if barcode_data else None
		if not item_code:
			item_code = frappe.db.get_value("Item", {"custom_barcode": barcode}, "name")
		if not item_code and frappe.db.has_column("Item Price", "custom_barcode"):
			item_code = frappe.db.get_value("Item Price", {"custom_barcode": barcode}, "item_code")
	if not item_code:
		frappe.throw("No item found for barcode {0}".format(barcode))

	item = frappe.db.get_value(
		"Item",
		item_code,
		["item_group", "stock_uom", "custom_barcode", "custom_sales_net_rate", "custom_sales_gross_rate", "custom_sales_vat_amount", "custom_tax"],
		as_dict=True,
	)
	if not item:
		frappe.throw("No item found for {0}".format(item_code))
	item_price = frappe.db.get_value(
		"Item Price",
		{"item_code": item_code, "price_list": price_list or "Standard Selling", "uom": item_uom or item.stock_uom},
		"price_list_rate",
	)
	current_price = flt(item_price) or flt(item.custom_sales_net_rate)
	vat_rate = _get_vat_rate_from_prices(item) or get_item_tax_rate(item.custom_tax)
	current_price_including_tax = flt(item.custom_sales_gross_rate) or current_price * (1 + vat_rate / 100)
	return {
		"item": item_code,
		"barcode": barcode or item.custom_barcode or "",
		"uom": item_uom or item.stock_uom,
		"current_price": current_price,
		"current_price_including_tax": current_price_including_tax,
		"vat_rate": vat_rate,
		"price_list": price_list or "Standard Selling",
		"qty": 1,
		**get_purchase_prices(item_code, item_uom or item.stock_uom),
	}


def get_purchase_prices(item_code, uom=None):
	"""Current Item purchase reference rates in the selected UOM, not stock valuation."""
	item = frappe.db.get_value(
		"Item", item_code,
		["stock_uom", "custom_purchase_net_rate", "custom_purchase_gross_rate",
		 "custom_default_purchase_rate", "last_purchase_rate", "custom_purchase_tax_template"],
		as_dict=True,
	)
	if not item:
		frappe.throw("No item found for {0}".format(item_code))
	net = flt(item.custom_purchase_net_rate or item.custom_default_purchase_rate or item.last_purchase_rate)
	gross = flt(item.custom_purchase_gross_rate) or net * (1 + get_item_tax_rate(item.custom_purchase_tax_template) / 100)
	if uom and uom != item.stock_uom:
		packing = frappe.db.get_value(
			"Retail Packing Detail", {"parent": item_code, "parenttype": "Item",
			"parentfield": "custom_retail_packing_detail", "uom": uom},
			["purchase_net_rate", "purchase_gross_rate", "conversion_factor"], as_dict=True,
		)
		factor = flt(packing.conversion_factor) if packing else flt(frappe.db.get_value(
			"UOM Conversion Detail", {"parent": item_code, "uom": uom}, "conversion_factor"
		))
		if not factor:
			frappe.throw("No purchase UOM conversion found for {0}: {1}".format(item_code, uom))
		net = flt(packing.purchase_net_rate) if packing and packing.purchase_net_rate is not None else net * factor
		gross = flt(packing.purchase_gross_rate) if packing and packing.purchase_gross_rate is not None else gross * factor
	return {"purchase_price": flt(net, 2), "purchase_price_including_tax": flt(gross, 2)}


def synchronize_discount(row):
	"""Keep one entered discount and a derived counterpart; percentage remains the POS contract."""
	base = flt(row.current_price_including_tax)
	amount = flt(row.get("discount_amount"))
	percent = flt(row.discount_percent)
	source = row.get("discount_input") or ("Percent" if percent else "Amount" if amount else "")
	if source not in ("", "Percent", "Amount"):
		frappe.throw("Row #{0}: Invalid discount input method.".format(row.idx))
	if percent < 0 or percent > 100 or amount < 0:
		frappe.throw("Row #{0}: Discount must be between 0% and 100%, with a non-negative amount.".format(row.idx))
	if source == "Amount" and amount:
		if not row.item or base <= 0:
			frappe.throw("Row #{0}: Discount Amount requires an Item with a positive selling price including VAT.".format(row.idx))
		if amount > base:
			frappe.throw("Row #{0}: Discount Amount cannot exceed the selling price including VAT.".format(row.idx))
		row.discount_percent = flt(amount / base * 100, 6)
	elif source == "Percent" and percent:
		row.discount_amount = flt(base * percent / 100, 2) if row.item else 0
	else:
		row.discount_amount = row.discount_percent = 0
		source = ""
	row.discount_input = source


def _get_vat_rate_from_prices(item):
	net = flt(item.custom_sales_net_rate)
	vat = flt(item.custom_sales_vat_amount)
	return flt(vat * 100 / net) if net else 0


def apply_inclusive_promo_prices(doc, method=None):
	"""Apply fixed promo prices that are stored as customer-facing VAT-inclusive prices."""
	if doc.doctype not in SALES_DOCTYPES or doc.get("is_return") or doc.get("is_consolidated"):
		return
	if doc.doctype == "POS Invoice" and doc.get("pos_sync_source"):
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
	}
	if doc.get("company"):
		filters["company"] = ["in", ("", doc.company)]

	names = frappe.get_all("Promo Price", filters=filters, pluck="name", order_by="priority desc, modified desc")
	promotions = [frappe.get_doc("Promo Price", name) for name in names]
	return [promotion for promotion in promotions if is_active(promotion, doc) and promotion_matches_doc(promotion, doc)]


def promotion_matches_doc(promotion, doc):
	if promotion.company and doc.get("company") and promotion.company != doc.company:
		return False
	if not promotion.warehouse:
		return True

	warehouses = {row.warehouse for row in doc.get("items") or [] if row.get("warehouse")}
	return promotion.warehouse in warehouses


def get_matching_inclusive_promo_row(doc, item, promotions):
	if item.get("custom_foc_parent"):
		return None  # The linked free goods retain their zero commercial price.
	matches = []
	for promotion in promotions:
		for row in promotion.get("products") or []:
			if not flt(row.promo_price_including_tax):
				continue
			if promotion.get("promotion_scope") != "WHOLE BILL" and not row_matches_item(row, item):
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
	if row.get("brand"):
		return row.brand == (item.get("brand") or frappe.db.get_value("Item", item.item_code, "brand"))
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
