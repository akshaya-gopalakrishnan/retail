import frappe
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
		)
	elif doc.doctype in SELLING_DOCTYPES:
		_recalculate_side_item_prices(
			doc,
			SELLING_HISTORY,
			"Standard Selling",
			doc.get("selling_price_list"),
			_get_item_master_selling_rate,
		)


def _recalculate_side_item_prices(doc, history, standard_price_list, document_price_list, fallback_getter):
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

		rate = _get_transaction_row_rate(row)
		if flt(rate) <= 0:
			continue

		for price_list in price_lists:
			sync_item_price(row, price_list, rate, uom=row.get("uom"))


def sync_packing_item_prices(doc):
	for row in doc.get("custom_retail_packing_detail") or []:
		if not row.get("uom"):
			continue

		sync_item_price(
			doc, "Standard Selling", row.get("selling_net_rate") or row.get("selling_rate"), uom=row.uom
		)
		sync_item_price(
			doc, "Standard Buying", row.get("purchase_net_rate") or row.get("purchase_rate"), uom=row.uom
		)


def sync_item_price(doc, price_list, rate, uom=None):
	rate = flt(rate)
	if rate <= 0:
		return

	item_code = doc.get("item_code") or doc.name
	uom = uom or doc.get("stock_uom") or "Nos"

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
				"price_list_rate",
				rate,
				update_modified=False,
			)
		return

	frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": item_code,
			"price_list": price_list,
			"price_list_rate": rate,
			"uom": uom,
		}
	).insert(ignore_permissions=True)


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


def _get_transaction_row_rate(row):
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


def _get_latest_submitted_transaction_rate(history, item_code, uom, price_list=None):
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
	return _get_transaction_row_rate(latest)


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
