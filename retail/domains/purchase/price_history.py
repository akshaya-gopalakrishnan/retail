"""Transactional selling revisions. The Item Price holds the current revision pointer.

Source fields are Data, deliberately not Dynamic Links: audit records must survive
source cancellation/deletion and restoration of an originally absent Item Price.
No commits here: price, history, packing and Item writes share the source transaction.
"""
import frappe
from frappe.utils import flt, now

from retail.domains.item.item_price_sync import (
	_get_item_master_vat_values, get_item_price_barcode, sync_item_master_margin,
)
from retail.domains.item.vat_pricing import PACKING_VAT_FIELDS, _apply_packing_direction

HISTORY = "Retail Selling Price History"
POINTER = "custom_retail_selling_revision"


def ready():
	return frappe.db.has_column("Item Price", POINTER)


def lock_item(item_code):
	# Serialize missing-price insertion as well as updates. Always lock Item first.
	frappe.db.sql("select name from `tabItem` where name=%s for update", item_code)


def selling_state(item_code, uom):
	item = frappe.get_doc("Item", item_code)
	if uom == item.stock_uom:
		fields = ["standard_rate", "custom_sales_rate_entry", "custom_sales_net_rate",
			"custom_sales_vat_amount", "custom_sales_gross_rate"]
		return {"item": {key: item.get(key) for key in fields}}
	fields = list(PACKING_VAT_FIELDS["selling"].values())
	fields.remove("custom_tax")
	fields.append("packing_margin")
	return {"packing": {row.name: {key: row.get(key) for key in fields}
		for row in item.get("custom_retail_packing_detail") or [] if row.uom == uom}}


def record_change(item_code, uom, old, rate, price_name, source=None):
	"""Write the before image BEFORE the Item Price is changed."""
	if old and flt(old.price_list_rate) == flt(rate):
		return old.get(POINTER)
	from retail.domains.purchase.selling_price import get_item_selling_vat_rate
	vat = get_item_selling_vat_rate(item_code)
	old_rate = flt(old.price_list_rate) if old else 0
	source = source or {}
	state = selling_state(item_code, uom)
	if source.get("doctype") in ("Purchase Receipt", "Purchase Invoice"):
		# Maintained master defaults are separately audited, and are not restored
		# by Item Price cancellation. Packing prices retain their existing rollback.
		state.pop("item", None)
	previous = old.get(POINTER) if old else None
	# An untracked direct DB edit must become a new baseline, not inherit a stale chain.
	if previous:
		previous_rate = frappe.db.get_value(HISTORY, previous, "new_rate")
		if previous_rate is None or flt(previous_rate) != old_rate:
			previous = None
	revision = frappe.get_doc({
		"doctype": HISTORY, "company": source.get("company"), "item_code": item_code,
		"uom": uom, "barcode": get_item_price_barcode(item_code, uom),
		"price_list": "Standard Selling", "item_price": price_name,
		"old_exists": bool(old), "old_rate": old_rate, "new_rate": rate,
		"vat_rate": vat, "old_vat_amount": old_rate * vat / 100,
		"new_vat_amount": rate * vat / 100,
		"old_gross_rate": old_rate * (1 + vat / 100), "new_gross_rate": rate * (1 + vat / 100),
		"old_state": frappe.as_json(state),
		"previous_revision": previous,
		"source_doctype": source.get("doctype") or "Item Price",
		"source_document": source.get("name") or price_name,
		"source_item_row": source.get("row"), "changed_by": frappe.session.user,
		"changed_on": now(), "status": "Active",
	}).insert(ignore_permissions=True)
	return revision.name


def audit_direct_price_edit(doc, method=None):
	"""Capture UI/API Item Price edits so purchase cancellation cannot overwrite them."""
	if doc.flags.get("retail_price_sync") or doc.price_list != "Standard Selling" or not ready():
		return
	lock_item(doc.item_code)
	old = frappe.db.get_value("Item Price", doc.name, ["price_list_rate", POINTER], as_dict=True)
	before = doc.get_doc_before_save()
	if before and (before.item_code, before.price_list, before.uom) != (doc.item_code, doc.price_list, doc.uom):
		old = None
	doc.set(POINTER, record_change(doc.item_code, doc.uom, old, flt(doc.price_list_rate), doc.name))


def sync_selling_state(item_code, uom, rate):
	"""Explicit sync after DB writes; never saves Item or invokes recursive price hooks."""
	item = frappe.get_doc("Item", item_code)
	if uom == item.stock_uom:
		frappe.db.set_value("Item", item_code, _get_item_master_vat_values(item_code, "sales", rate))
		sync_item_master_margin(item_code)
	else:
		for row in item.get("custom_retail_packing_detail") or []:
			if row.uom != uom:
				continue
			vat = flt(row.selling_vat_rate)
			row.selling_rate = rate * (1 + vat / 100) if row.selling_vat_mode == "Including VAT" else rate
			_apply_packing_direction(item, row, "selling")
			row.packing_margin = flt(rate - flt(row.purchase_net_rate), 2)
			fields = PACKING_VAT_FIELDS["selling"]
			values = {row_field: row.get(row_field) for key, row_field in fields.items() if key != "template"}
			values["packing_margin"] = row.packing_margin
			frappe.db.set_value("Retail Packing Detail", row.name, values)
		# POS delta sync reads the parent modified time.
		frappe.db.set_value("Item", item_code, "modified", now())
	frappe.clear_document_cache("Item", item_code)


def rollback_selling_prices(doc, method=None):
	if doc.get("is_return") or doc.doctype not in ("Purchase Receipt", "Purchase Invoice"):
		return
	revisions = frappe.get_all(HISTORY, filters={"source_doctype": doc.doctype,
		"source_document": doc.name, "status": "Active"}, fields=["name", "item_code", "uom"])
	for item_code in sorted({row.item_code for row in revisions}):
		lock_item(item_code)
	for row in revisions:
		frappe.db.set_value(HISTORY, row.name, {"status": "Reverted", "reverted_by": frappe.session.user,
			"reverted_on": now(), "reverted_reason": "Source document cancelled"})
	for item_code, uom in sorted({(row.item_code, row.uom) for row in revisions}):
		price = frappe.db.get_value("Item Price", {"item_code": item_code,
			"price_list": "Standard Selling", "uom": uom}, ["name", "price_list_rate", POINTER], as_dict=True)
		if not price or not price.get(POINTER):
			continue
		head = frappe.get_doc(HISTORY, price.get(POINTER))
		restore_master = bool((frappe.parse_json(head.old_state) or {}).get("item"))
		stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
		if head.status != "Reverted" or flt(price.price_list_rate) != flt(head.new_rate):
			continue
		# Skip cancelled predecessors, including cancellations performed out of order.
		while head.previous_revision:
			previous = frappe.get_doc(HISTORY, head.previous_revision)
			if previous.status == "Active":
				frappe.db.set_value("Item Price", price.name,
					{"price_list_rate": previous.new_rate, POINTER: previous.name})
				if uom != stock_uom or restore_master:
					sync_selling_state(item_code, uom, previous.new_rate)
				break
			head = previous
		else:
			if head.old_exists:
				frappe.db.set_value("Item Price", price.name,
					{"price_list_rate": head.old_rate, POINTER: None})
				if uom != stock_uom or restore_master:
					sync_selling_state(item_code, uom, head.old_rate)
			else:
				frappe.delete_doc("Item Price", price.name, ignore_permissions=True)
				state = frappe.parse_json(head.old_state) or {}
				if state.get("item") and restore_master:
					frappe.db.set_value("Item", item_code, state["item"])
					sync_item_master_margin(item_code)
				for name, values in state.get("packing", {}).items():
					if frappe.db.exists("Retail Packing Detail", {"name": name, "parent": item_code, "uom": uom}):
						frappe.db.set_value("Retail Packing Detail", name, values)
				frappe.db.set_value("Item", item_code, "modified", now())
				frappe.clear_document_cache("Item", item_code)
