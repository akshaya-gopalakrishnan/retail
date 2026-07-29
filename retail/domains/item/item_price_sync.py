import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


BUYING_DOCTYPES = {"Purchase Order", "Purchase Receipt", "Purchase Invoice"}
SELLING_DOCTYPES = {"Sales Order", "Delivery Note", "Sales Invoice", "POS Invoice"}
BUYING_HISTORY = (
	("Purchase Order", "Purchase Order Item", "buying_price_list"),
	("Purchase Receipt", "Purchase Receipt Item", "buying_price_list"),
	("Purchase Invoice", "Purchase Invoice Item", "buying_price_list"),
)
SELLING_HISTORY = (
	("Sales Order", "Sales Order Item", "selling_price_list"),
	("Delivery Note", "Delivery Note Item", "selling_price_list"),
	("Sales Invoice", "Sales Invoice Item", "selling_price_list"),
	("POS Invoice", "POS Invoice Item", "selling_price_list"),
)

LEGACY_ITEM_PRICE_SCRIPTS = (
	"for unique row unique price",
	"purchase rate submit",
	"UOM&Barcode table sync Retail Packing detail after save",
)
LEGACY_ITEM_RATE_CLIENT_SCRIPTS = (
	"Item fetch last purchase rate from same name",
)


def sync_simple_item_prices(doc, method=None):
	if isinstance(doc, str):
		doc = frappe.get_doc("Item", doc)

	sync_item_price(doc, "Standard Selling", _get_item_master_selling_rate(doc))
	sync_item_price(doc, "Standard Buying", _get_item_master_buying_rate(doc))
	sync_packing_item_prices(doc)


def sync_latest_transaction_item_prices(doc, method=None):
	"""Keep Item Price in step with the latest submitted buying/selling rows."""
	if isinstance(doc, str):
		doc = frappe.get_doc(doc)

	if doc.doctype in BUYING_DOCTYPES:
		sync_transaction_item_prices(doc, "Standard Buying", doc.get("buying_price_list"))
	elif doc.doctype in SELLING_DOCTYPES:
		sync_transaction_item_prices(doc, "Standard Selling", doc.get("selling_price_list"))


def recalculate_transaction_item_prices(doc, method=None):
	"""On cancellation, restore the previous latest submitted rate."""
	if isinstance(doc, str):
		doc = frappe.get_doc(doc)

	if doc.doctype in BUYING_DOCTYPES:
		_recalculate_side_item_prices(
			doc,
			BUYING_HISTORY,
			"Standard Buying",
			doc.get("buying_price_list"),
			_get_item_master_buying_rate,
			prefer_net_rate=True,
		)
	elif doc.doctype in SELLING_DOCTYPES:
		_recalculate_side_item_prices(
			doc,
			SELLING_HISTORY,
			"Standard Selling",
			doc.get("selling_price_list"),
			_get_item_master_selling_rate,
			prefer_net_rate=False,
		)


def _recalculate_side_item_prices(
	doc, history, standard_price_list, document_price_list, fallback_getter, prefer_net_rate=True
):
	for item_code, uom in _get_document_item_uoms(doc):
		price_lists = [standard_price_list]
		if document_price_list and document_price_list not in price_lists:
			price_lists.append(document_price_list)

		for price_list in price_lists:
			rate = _get_latest_submitted_transaction_rate(
				history,
				item_code,
				uom,
				price_list=None if price_list == standard_price_list else price_list,
				prefer_net_rate=prefer_net_rate,
			)
			if not rate and price_list == standard_price_list:
				item = frappe.get_cached_doc("Item", item_code)
				rate = fallback_getter(item)
			sync_item_price({"item_code": item_code}, price_list, rate, uom=uom)



def sync_transaction_item_prices(doc, standard_price_list, document_price_list=None):
	price_lists = [standard_price_list]
	if document_price_list and document_price_list not in price_lists:
		price_lists.append(document_price_list)

	for row in doc.get("items") or []:
		if not row.get("item_code"):
			continue

		rate = _get_transaction_row_rate(row, prefer_net_rate=doc.doctype in BUYING_DOCTYPES)
		if flt(rate) <= 0:
			continue

		for price_list in price_lists:
			sync_item_price(row, price_list, rate, uom=row.get("uom"))



def sync_packing_item_prices(doc):
	for row in doc.get("custom_retail_packing_detail") or []:
		if not row.get("uom"):
			continue

		sync_item_price(
			doc,
			"Standard Selling",
			row.get("selling_net_rate") or row.get("selling_rate"),
			uom=row.uom,
			barcode=row.get("barcode"),
		)
		sync_item_price(
			doc,
			"Standard Buying",
			row.get("purchase_net_rate") or row.get("purchase_rate"),
			uom=row.uom,
			barcode=row.get("barcode"),
		)


def sync_item_price(doc, price_list, rate, uom=None, barcode=None):
	rate = flt(rate)
	if rate <= 0:
		return

	item_code = doc.get("item_code") or doc.name
	uom = uom or doc.get("stock_uom") or "Nos"
	barcode = barcode if barcode is not None else get_item_price_barcode(item_code, uom)
	values = {"price_list_rate": rate}
	if frappe.db.has_column("Item Price", "custom_barcode"):
		values["custom_barcode"] = barcode or ""

	price_name = frappe.db.get_value(
		"Item Price",
		{
			"item_code": item_code,
			"price_list": price_list,
			"uom": uom,
		},
	)

	if price_name:
		for duplicate in frappe.get_all(
			"Item Price",
			filters={"item_code": item_code, "price_list": price_list, "uom": uom},
			pluck="name",
		):
			frappe.db.set_value(
				"Item Price",
				duplicate,
				values,
			)
		return

	doc_values = {
		"doctype": "Item Price",
		"item_code": item_code,
		"price_list": price_list,
		"price_list_rate": rate,
		"uom": uom,
	}
	if frappe.db.has_column("Item Price", "custom_barcode"):
		doc_values["custom_barcode"] = barcode or ""
	frappe.get_doc(doc_values).insert(ignore_permissions=True)
	return


def sync_item_master_purchase_rate_from_price_list(doc, method=None, uom=None):
	"""Copy the maintained Standard Buying price back to the Item Master cost fields."""
	if isinstance(doc, str):
		item_code = doc
		stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
	else:
		item_code = doc.get("item_code") or doc.name
		stock_uom = doc.get("stock_uom") or frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"

	uom = uom or stock_uom
	if uom != stock_uom:
		return

	rate = frappe.db.get_value(
		"Item Price",
		{
			"item_code": item_code,
			"price_list": "Standard Buying",
			"uom": stock_uom,
		},
		"price_list_rate",
	)
	rate = flt(rate)
	if rate <= 0:
		return

	values = {"last_purchase_rate": rate}
	values.update(_get_item_master_vat_values(item_code, "purchase", rate))

	if not frappe.flags.in_install:
		frappe.db.set_value("Item", item_code, values, update_modified=False)
		sync_item_master_margin(item_code)


def sync_item_master_selling_rate_from_price_list(doc, method=None, uom=None):
	"""Copy the maintained Standard Selling price back to the Item Master selling fields."""
	if isinstance(doc, str):
		item_code = doc
		stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
	else:
		item_code = doc.get("item_code") or doc.name
		stock_uom = doc.get("stock_uom") or frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"

	uom = uom or stock_uom
	if uom != stock_uom:
		return

	rate = frappe.db.get_value(
		"Item Price",
		{
			"item_code": item_code,
			"price_list": "Standard Selling",
			"uom": stock_uom,
		},
		"price_list_rate",
	)
	rate = flt(rate)
	if rate <= 0 or frappe.flags.in_install:
		return

	values = {"standard_rate": rate}
	values.update(_get_item_master_vat_values(item_code, "sales", rate))

	frappe.db.set_value("Item", item_code, values, update_modified=False)
	sync_item_master_margin(item_code)


def sync_item_master_margin(item_code):
	"""Recalculate margin from current Item Master selling and buying rates."""
	if frappe.flags.in_install:
		return

	item = frappe.db.get_value(
		"Item",
		item_code,
		[
			"standard_rate",
			"custom_sales_net_rate",
			"custom_default_purchase_rate",
			"last_purchase_rate",
			"valuation_rate",
		],
		as_dict=True,
	)
	if not item:
		return

	selling_rate = flt(item.get("custom_sales_net_rate") or item.get("standard_rate"))
	purchase_rate = flt(
		item.get("custom_default_purchase_rate")
		or item.get("last_purchase_rate")
		or item.get("valuation_rate")
	)
	margin = selling_rate - purchase_rate if selling_rate else 0
	margin_percent = (margin / selling_rate * 100) if selling_rate else 0

	values = {}
	if frappe.db.has_column("Item", "custom_margin"):
		values["custom_margin"] = flt(margin, 2)
	if frappe.db.has_column("Item", "custom_margin_"):
		values["custom_margin_"] = flt(margin_percent, 3)
	if values:
		frappe.db.set_value("Item", item_code, values, update_modified=False)


def sync_item_master_purchase_rates_from_transaction_row(row):
	"""Copy latest stock-UOM purchase rates, excluding and including VAT, to Item Master."""
	item_code = row.get("item_code")
	if not item_code or frappe.flags.in_install:
		return

	stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
	if (row.get("uom") or stock_uom) != stock_uom:
		return

	net_rate = flt(row.get("net_rate") or row.get("base_net_rate") or row.get("rate"))
	gross_rate = flt(row.get("custom_rate_including_vat") or row.get("rate") or net_rate)
	if net_rate <= 0:
		return

	values = {"last_purchase_rate": net_rate}
	for fieldname, value in {
		"custom_default_purchase_rate": net_rate,
		"custom_purchase_net_rate": net_rate,
		"custom_purchase_vat_amount": max(gross_rate - net_rate, 0),
		"custom_purchase_gross_rate": gross_rate or net_rate,
	}.items():
		if frappe.db.has_column("Item", fieldname):
			values[fieldname] = value

	frappe.db.set_value("Item", item_code, values, update_modified=False)
	sync_item_master_margin(item_code)


def sync_item_master_purchase_rates_from_latest_transaction(item_code, uom=None):
	stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
	if (uom or stock_uom) != stock_uom:
		return

	row = _get_latest_submitted_buying_row(item_code, stock_uom)
	if row:
		sync_item_master_purchase_rates_from_transaction_row(row)
	else:
		sync_item_master_purchase_rate_from_price_list(item_code, uom=stock_uom)


def backfill_item_master_purchase_rates_from_latest_transactions():
	for item_code in frappe.get_all("Item", filters={"disabled": 0}, pluck="name"):
		sync_item_master_purchase_rates_from_latest_transaction(item_code)


def backfill_item_master_rates_from_price_lists():
	for item_code in frappe.get_all("Item", filters={"disabled": 0}, pluck="name"):
		sync_item_master_purchase_rates_from_latest_transaction(item_code)
		sync_item_master_selling_rate_from_price_list(item_code)
		sync_item_master_margin(item_code)


def _get_item_master_vat_values(item_code, direction, net_rate):
	prefix = "purchase" if direction == "purchase" else "sales"
	template_field = "custom_purchase_tax_template" if direction == "purchase" else "custom_tax"
	default_field = "custom_default_purchase_rate" if direction == "purchase" else "standard_rate"

	template = frappe.db.get_value("Item", item_code, template_field)
	vat_rate = _get_item_vat_rate(template)
	net_rate = flt(net_rate)
	vat_amount = net_rate * vat_rate / 100
	gross_rate = net_rate + vat_amount

	values = {default_field: net_rate}
	for fieldname, value in {
		f"custom_{prefix}_net_rate": net_rate,
		f"custom_{prefix}_vat_amount": vat_amount,
		f"custom_{prefix}_gross_rate": gross_rate,
	}.items():
		if frappe.db.has_column("Item", fieldname):
			values[fieldname] = flt(value, 2)

	return values


def _get_item_vat_rate(template):
	if not template:
		return 0

	from retail.domains.item.vat_pricing import get_item_tax_rate

	return flt(get_item_tax_rate(template))


def _get_latest_submitted_buying_row(item_code, uom):
	rows = frappe.db.sql(
		"""
		select * from (
			select
				pri.item_code, pri.uom, pri.net_rate, pri.base_net_rate, pri.rate,
				pri.custom_rate_including_vat, pr.modified, pri.idx
			from `tabPurchase Receipt Item` pri
			inner join `tabPurchase Receipt` pr on pr.name = pri.parent
			where pr.docstatus = 1 and pri.item_code = %(item_code)s and pri.uom = %(uom)s

			union all

			select
				pii.item_code, pii.uom, pii.net_rate, pii.base_net_rate, pii.rate,
				pii.custom_rate_including_vat, pi.modified, pii.idx
			from `tabPurchase Invoice Item` pii
			inner join `tabPurchase Invoice` pi on pi.name = pii.parent
			where pi.docstatus = 1 and pii.item_code = %(item_code)s and pii.uom = %(uom)s
		) latest_purchase
		order by modified desc, idx desc
		limit 1
		""",
		{"item_code": item_code, "uom": uom},
		as_dict=True,
	)
	return rows[0] if rows else None


def sync_item_master_purchase_rate_from_item_price(doc, method=None):
	"""Item Price edits no longer update Item Master silently.

	Use the controlled Retail button/API in retail.domains.item.rate_audit
	so updates are permission-gated and audited.
	"""
	return


def populate_item_price_barcode(doc, method=None):
	if not frappe.db.has_column("Item Price", "custom_barcode") or not doc.get("item_code"):
		return

	doc.custom_barcode = get_item_price_barcode(doc.item_code, doc.get("uom")) or ""


def sync_item_price_barcodes():
	if not frappe.db.has_column("Item Price", "custom_barcode"):
		return

	for row in frappe.get_all("Item Price", fields=["name", "item_code", "uom"]):
		frappe.db.set_value(
			"Item Price",
			row.name,
			"custom_barcode",
			get_item_price_barcode(row.item_code, row.uom) or "",
			update_modified=False,
		)


def get_item_price_barcode(item_code, uom=None):
	if not item_code:
		return ""

	stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
	uom = uom or stock_uom

	if uom != stock_uom:
		packing_barcode = frappe.db.get_value(
			"Retail Packing Detail",
			{
				"parenttype": "Item",
				"parentfield": "custom_retail_packing_detail",
				"parent": item_code,
				"uom": uom,
			},
			"barcode",
			order_by="idx asc",
		)
		if packing_barcode:
			return packing_barcode

	item_barcode = frappe.db.get_value("Item", item_code, "custom_barcode")
	if item_barcode:
		return item_barcode

	item_barcode_rows = frappe.get_all(
		"Item Barcode",
		filters=[["parent", "=", item_code], ["uom", "in", [uom, stock_uom, ""]]],
		fields=["barcode"],
		order_by="idx asc",
		limit_page_length=1,
	)
	if item_barcode_rows:
		return item_barcode_rows[0].barcode

	return frappe.db.get_value("Item Barcode", {"parent": item_code}, "barcode", order_by="idx asc") or ""


@frappe.whitelist()
def get_latest_item_name_prices(item_name, uom=None):
	"""Return latest buying/selling price-list values for an existing item name."""
	item_name = (item_name or "").strip()
	if not item_name:
		return {}

	item_price = frappe.qb.DocType("Item Price")
	item = frappe.qb.DocType("Item")
	query = (
		frappe.qb.from_(item_price)
		.inner_join(item)
		.on(item.name == item_price.item_code)
		.select(
			item_price.item_code,
			item_price.price_list,
			item_price.price_list_rate,
			item_price.custom_average_purchase_rate,
			item_price.modified,
			item.modified.as_("item_modified"),
		)
		.where(
			(item.item_name == item_name)
			& (item.disabled == 0)
			& (item_price.price_list.isin(["Standard Buying", "Standard Selling"]))
		)
		.orderby(item_price.modified, order=frappe.qb.desc)
		.orderby(item.modified, order=frappe.qb.desc)
		.orderby(item_price.creation, order=frappe.qb.desc)
		.limit(100)
	)
	if uom:
		query = query.where(item_price.uom == uom)

	result = {}
	rows = query.run(as_dict=True)
	buying_rows = sorted(
		[row for row in rows if row.price_list == "Standard Buying"],
		key=lambda row: (max(row.get("modified"), row.get("item_modified")), row.get("modified")),
		reverse=True,
	)
	selling_rows = sorted(
		[row for row in rows if row.price_list == "Standard Selling"],
		key=lambda row: (row.get("modified"), row.get("item_modified")),
		reverse=True,
	)
	for row in buying_rows[:1]:
		from retail.domains.item.average_purchase_rate import get_average_purchase_rate_for_item_name

		buying_rate = flt(row.price_list_rate)
		result.update(
			{
				"source_item": row.item_code,
				"buying_rate": buying_rate,
				"average_purchase_rate": get_average_purchase_rate_for_item_name(
					item_name, fallback_rate=flt(row.custom_average_purchase_rate) or buying_rate
				),
			}
		)
	for row in selling_rows[:1]:
		result.update(
			{
				"selling_source_item": row.item_code,
				"selling_rate": flt(row.price_list_rate),
			}
		)

	return result


def _get_item_master_selling_rate(doc):
	return (
		doc.get("standard_rate")
		or doc.get("custom_sales_net_rate")
		or doc.get("custom_b2b")
	)


def _get_item_master_buying_rate(doc):
	return (
		doc.get("custom_default_purchase_rate")
		or doc.get("custom_purchase_net_rate")
		or doc.get("last_purchase_rate")
	)


def _get_transaction_row_rate(row, prefer_net_rate=True):
	if not prefer_net_rate:
		return (
			row.get("rate")
			or row.get("price_list_rate")
			or row.get("base_rate")
			or row.get("base_price_list_rate")
			or row.get("net_rate")
			or row.get("base_net_rate")
		)

	return (
		row.get("net_rate")
		or row.get("rate")
		or row.get("price_list_rate")
		or row.get("base_net_rate")
		or row.get("base_rate")
		or row.get("base_price_list_rate")
	)


def _get_document_item_uoms(doc):
	seen = set()
	for row in doc.get("items") or []:
		item_code = row.get("item_code")
		if not item_code:
			continue
		uom = row.get("uom") or frappe.get_cached_value("Item", item_code, "stock_uom") or "Nos"
		key = (item_code, uom)
		if key in seen:
			continue
		seen.add(key)
		yield key


def _get_latest_submitted_transaction_rate(
	history, item_code, uom, price_list=None, prefer_net_rate=True
):
	candidates = []
	for parent_doctype, child_doctype, price_list_field in history:
		parent = frappe.qb.DocType(parent_doctype)
		child = frappe.qb.DocType(child_doctype)
		query = (
			frappe.qb.from_(child)
			.inner_join(parent)
			.on(parent.name == child.parent)
			.select(
				child.net_rate,
				child.rate,
				child.price_list_rate,
				child.base_net_rate,
				child.base_rate,
				child.base_price_list_rate,
				parent.modified,
				child.idx,
			)
			.where((parent.docstatus == 1) & (child.item_code == item_code) & (child.uom == uom))
			.limit(1)
			.orderby(parent.modified, order=frappe.qb.desc)
			.orderby(child.idx, order=frappe.qb.desc)
		)
		if price_list:
			query = query.where(parent[price_list_field] == price_list)

		candidates.extend(query.run(as_dict=True))
	if not candidates:
		return 0

	latest = max(candidates, key=lambda row: (row.get("modified"), row.get("idx") or 0))
	return _get_transaction_row_rate(latest, prefer_net_rate=prefer_net_rate)


def disable_legacy_item_price_scripts():
	"""Prevent old server scripts from competing with the app's Item Price sync."""
	for script_name in LEGACY_ITEM_PRICE_SCRIPTS:
		if frappe.db.exists("Server Script", script_name):
			frappe.db.set_value("Server Script", script_name, "disabled", 1, update_modified=False)

	for script_name in LEGACY_ITEM_RATE_CLIENT_SCRIPTS:
		if frappe.db.exists("Client Script", script_name):
			frappe.db.set_value("Client Script", script_name, "enabled", 0, update_modified=False)


def disable_legacy_last_purchase_rate_script():
	"""Backward-compatible patch entry point."""
	disable_legacy_item_price_scripts()


def ensure_standard_purchase_rate_field():
	"""Make the maintained buying cost visible on Item Master."""
	field_name = "Item-custom_default_purchase_rate"
	if not frappe.db.exists("Custom Field", field_name):
		return

	frappe.db.set_value(
		"Custom Field",
		field_name,
		{
			"label": "Standard Purchase Rate",
			"description": None,
			"hidden": 0,
		},
		update_modified=False,
	)
	if frappe.db.exists("Property Setter", "Item-custom_default_purchase_rate-hidden"):
		frappe.db.set_value(
			"Property Setter", "Item-custom_default_purchase_rate-hidden", "value", "0", update_modified=False
		)
	frappe.clear_cache(doctype="Item")


def ensure_item_price_barcode_field():
	create_custom_fields(
		{
			"Item Price": [
				{
					"fieldname": "custom_barcode",
					"label": "Barcode",
					"fieldtype": "Data",
					"insert_after": "price_list_rate",
					"read_only": 1,
					"in_list_view": 1,
					"in_standard_filter": 1,
				}
			]
		},
		ignore_validate=True,
		update=True,
	)
	frappe.clear_cache(doctype="Item Price")
