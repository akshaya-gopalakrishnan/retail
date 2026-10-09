"""Read-only purchase comparisons. Never change prices, stock or accounting.

History uses permission-aware parent queries (including child-field permissions).
A receipt and its bills form one chain; returns are separate, never baselines.
All rates are net of transaction taxes/discounts, in company currency per stock UOM.
"""

from html import escape

import frappe
from frappe import _
from frappe.model import get_permitted_fields
from frappe.utils import cint, flt, get_datetime, getdate


PURCHASE_DOCTYPES = ("Purchase Order", "Purchase Receipt", "Purchase Invoice")
HISTORY_DOCTYPES = ("Purchase Receipt", "Purchase Invoice")


def _context(document):
	data = frappe.parse_json(document) if isinstance(document, str) else document
	if not isinstance(data, dict) or data.get("doctype") not in PURCHASE_DOCTYPES:
		frappe.throw(_("A purchase document is required."))
	doc = frappe.get_doc(data)
	if doc.name and not doc.get("__islocal") and frappe.db.exists(doc.doctype, doc.name):
		frappe.get_doc(doc.doctype, doc.name).check_permission("read")
	elif not frappe.has_permission(doc.doctype, "create"):
		frappe.throw(_("Not permitted to view purchase comparisons."), frappe.PermissionError)
	if not doc.company or not doc.supplier:
		frappe.throw(_("Select a company and supplier first."))
	frappe.get_doc("Company", doc.company).check_permission("read")
	frappe.get_doc("Supplier", doc.supplier).check_permission("read")
	return doc


def _cutoff(doc):
	date = doc.get("posting_date") or doc.get("transaction_date") or getdate()
	# Purchase Orders have no posting time. An unset time means the whole day.
	return get_datetime(f"{getdate(date)} {doc.get('posting_time') or '23:59:59.999999'}")


def _timestamp(row):
	return get_datetime(f"{row.posting_date} {row.get('posting_time') or '00:00:00'}")


def _read_rows(doctype, company, item_code, cutoff, supplier=None, other_suppliers=False):
	"""Read only visible rows; do not bypass role, company, owner or sharing rules."""
	if not frappe.has_permission(doctype, "read"):
		return [], False
	child = f"{doctype} Item"
	allowed = set(get_permitted_fields(child, parenttype=doctype, permission_type="read"))
	parent_allowed = set(get_permitted_fields(doctype, permission_type="read"))
	if not {"base_net_amount", "qty", "conversion_factor", "item_code"}.issubset(allowed):
		return [], False
	if not {"company", "supplier", "currency", "posting_date", "is_return"}.issubset(parent_allowed):
		return [], False
	parent_fields = [
		"name", "posting_date", "posting_time", "supplier", "supplier_name", "currency",
		"conversion_rate", "is_return", "return_against", "per_billed",
	]
	child_fields = [
		"name", "item_code", "item_name", "qty", "uom", "stock_uom", "conversion_factor",
		"rate", "net_rate", "net_amount", "base_net_amount", "discount_percentage",
		"discount_amount", "custom_foc_qty", "purchase_receipt", "pr_detail", "purchase_order",
	]
	fields = [f"`tab{doctype}`.`{key}`" for key in parent_fields
		if key in parent_allowed and (frappe.get_meta(doctype).has_field(key) or key == "name")]
	fields += [f"`tab{child}`.`{key}` as `{('row_name' if key == 'name' else key)}`"
		for key in child_fields if key in allowed and (key == "name" or frappe.get_meta(child).has_field(key))]
	filters = [[doctype, "company", "=", company], [doctype, "docstatus", "=", 1],
		[doctype, "posting_date", "<=", cutoff.date()], [child, "item_code", "=", item_code]]
	if supplier:
		filters.append([doctype, "supplier", "!=" if other_suppliers else "=", supplier])
	rows = frappe.get_list(
		doctype,
		fields=fields,
		filters=filters,
		order_by=f"`tab{doctype}`.posting_date desc, `tab{doctype}`.posting_time desc, `tab{child}`.idx desc",
		limit_page_length=0,
	)
	result = []
	for row in rows:
		if _timestamp(row) > cutoff:
			continue
		row.doctype = doctype
		row.timestamp = str(_timestamp(row))
		row.stock_qty = flt(row.qty) * flt(row.conversion_factor)
		row.effective_qty = (flt(row.qty) + flt(row.get("custom_foc_qty"))) * flt(row.conversion_factor)
		row.comparable_rate = (
			flt(row.base_net_amount) / row.effective_qty if row.effective_qty else None
		)
		result.append(row)
	return result, True


def _chains(receipts, invoices):
	"""Keep partial bills together, preserve receipt rates, and show returns separately."""
	groups = {}
	for receipt in receipts:
		groups[("receipt", receipt.row_name)] = {"receipt": receipt, "invoices": []}
	for invoice in invoices:
		key = (("receipt", invoice.pr_detail)
			if invoice.get("pr_detail") and not invoice.is_return
			else ("invoice", invoice.row_name))
		groups.setdefault(key, {"receipt": None, "invoices": []})["invoices"].append(invoice)

	chains = []
	for group in groups.values():
		receipt, bills = group["receipt"], group["invoices"]
		# Bills may omit FOC or copy the entire receipt FOC onto every partial bill.
		# Allocate the actually received free stock in proportion to billed paid stock.
		if receipt and receipt.stock_qty > 0:
			for bill in bills:
				bill.effective_qty = bill.stock_qty * receipt.effective_qty / receipt.stock_qty
				bill.comparable_rate = flt(bill.base_net_amount) / bill.effective_qty if bill.effective_qty else None
				bill.receipt_foc_allocated = bool(flt(receipt.get("custom_foc_qty")))
		bills.sort(key=lambda row: (row.timestamp, row.name, row.row_name), reverse=True)
		source = bills[0] if bills else receipt
		quantity = sum(row.effective_qty for row in bills) if bills else receipt.effective_qty
		amount = sum(flt(row.base_net_amount) for row in bills) if bills else flt(receipt.base_net_amount)
		if source.is_return:
			status = "Return — excluded from comparison"
		elif receipt and bills:
			billed_qty = sum(row.stock_qty for row in bills)
			status = "Fully billed" if billed_qty >= receipt.stock_qty - 0.000001 else "Partly billed"
		elif bills:
			status = "Billed" if not source.get("pr_detail") else "Billed — receipt not available"
		elif flt(receipt.get("per_billed")) > 0:
			status = "Receipt rate — bill outside visible history"
		else:
			status = "Bill pending — receipt rate"
		chains.append({
			"supplier": source.supplier, "supplier_name": source.get("supplier_name"),
			"item_code": source.item_code, "stock_uom": source.get("stock_uom"),
			"date": str(source.posting_date), "timestamp": source.timestamp,
			"doctype": source.doctype, "name": source.name, "row_name": source.row_name,
			"is_return": bool(source.is_return), "status": status,
			"rate": amount / quantity if quantity > 0 and not source.is_return else None,
			"rate_basis": ("Billed net cost" if bills else "Receipt reference cost"
				if flt(receipt.get("per_billed")) > 0 else "Unbilled receipt net cost"),
			"receipt": receipt, "invoices": bills,
		})
	return sorted(chains, key=lambda row: (row["timestamp"], row["name"], row["row_name"]), reverse=True)


def _load_history(doc, item_code, other_suppliers=False):
	frappe.get_doc("Item", item_code).check_permission("read")
	cutoff = _cutoff(doc)
	receipts, can_receipt = _read_rows("Purchase Receipt", doc.company, item_code, cutoff, doc.supplier, other_suppliers)
	invoices, can_invoice = _read_rows("Purchase Invoice", doc.company, item_code, cutoff, doc.supplier, other_suppliers)
	# Never compare a document against itself, including while editing an amendment.
	receipts = [r for r in receipts if not (doc.doctype == r.doctype and doc.name == r.name)]
	invoices = [r for r in invoices if not (doc.doctype == r.doctype and doc.name == r.name)]
	return _chains(receipts, invoices), can_receipt and can_invoice


def _current_rate(row, conversion_rate, receipt=None):
	quantity = (flt(row.get("qty")) + flt(row.get("custom_foc_qty"))) * flt(row.get("conversion_factor"))
	if receipt and receipt.stock_qty > 0:
		quantity = flt(row.get("qty")) * flt(row.get("conversion_factor")) * receipt.effective_qty / receipt.stock_qty
	if quantity <= 0 or flt(conversion_rate) <= 0:
		return None
	# net_amount already includes tax-exclusive pricing and distributed invoice discounts.
	if row.get("net_amount") is None:
		return None
	amount = row.get("base_net_amount")
	if amount is None:
		amount = flt(row.net_amount) * flt(conversion_rate)
	return flt(amount) / quantity


def _comparison(doc, row, history, complete_access):
	linked_receipt = next((entry["receipt"] for entry in history
		if entry["receipt"] and entry["receipt"].row_name == row.get("pr_detail")), None)
	receipt_name = row.get("purchase_receipt") or (linked_receipt.name if linked_receipt else None)

	def same_receipt(entry):
		# Other paid/free rows and partial bills of these goods are not earlier purchases.
		receipt = entry["receipt"]
		if receipt and ((receipt_name and receipt.name == receipt_name)
			or (row.get("pr_detail") and receipt.row_name == row.pr_detail)):
			return True
		return any((receipt_name and bill.get("purchase_receipt") == receipt_name)
			or (row.get("pr_detail") and bill.get("pr_detail") == row.pr_detail)
			for bill in entry["invoices"])

	baseline = next((entry for entry in history
		if entry["supplier"] == doc.supplier and not entry["is_return"] and entry["rate"] is not None
		and not same_receipt(entry)), None)
	current = _current_rate(row, doc.get("conversion_rate"), linked_receipt)
	result = {"row_name": row.name, "item_code": row.item_code, "current_rate": current,
		"baseline": baseline, "higher": False, "difference": None, "percent": None,
		"limited_access": not complete_access, "is_return": bool(doc.get("is_return"))}
	result["linked_receipt"] = linked_receipt
	if baseline and current is not None and not doc.get("is_return"):
		difference = current - baseline["rate"]
		result.update(difference=difference, higher=round(difference, 6) > 0,
			percent=difference / baseline["rate"] * 100 if baseline["rate"] else None)
	return result


@frappe.whitelist()
def get_comparisons(document):
	doc = _context(document)
	rows = [row for row in doc.get("items", []) if row.item_code]
	if len(rows) > 100:
		frappe.throw(_("Request at most 100 item rows at a time."))
	cache = {}
	result = []
	for row in rows:
		if row.item_code not in cache:
			cache[row.item_code] = _load_history(doc, row.item_code)
		result.append(_comparison(doc, row, *cache[row.item_code]))
	return {"currency": frappe.get_cached_value("Company", doc.company, "default_currency"), "rows": result}


@frappe.whitelist()
def get_history(document, item_code, scope="supplier", start=0, page_length=20, from_date=None, to_date=None):
	doc = _context(document)
	if scope not in ("supplier", "others"):
		frappe.throw(_("Invalid history tab."))
	if from_date and to_date and getdate(from_date) > getdate(to_date):
		frappe.throw(_("From date cannot be after To date."))
	history, complete_access = _load_history(doc, item_code, other_suppliers=scope == "others")
	history = [row for row in history if (row["supplier"] == doc.supplier) == (scope == "supplier")]
	if from_date:
		history = [row for row in history if getdate(row["date"]) >= getdate(from_date)]
	if to_date:
		history = [row for row in history if getdate(row["date"]) <= getdate(to_date)]
	start, page_length = max(cint(start), 0), min(max(cint(page_length), 1), 50)
	latest = {}
	for row in history:
		if not row["is_return"] and row["rate"] is not None:
			latest.setdefault(row["supplier"], {"supplier": row["supplier"], "rate": row["rate"],
				"date": row["date"], "basis": row["rate_basis"], "stock_uom": row["stock_uom"]})
	return {"rows": history[start:start + page_length], "total": len(history),
		"start": start, "page_length": page_length, "latest": list(latest.values()),
		"currency": frappe.get_cached_value("Company", doc.company, "default_currency"),
		"limited_access": not complete_access, "as_of": str(_cutoff(doc))}


@frappe.whitelist()
def get_stock_context(document, item_code):
	"""Possible earlier receipts, never an assertion that these are the same goods."""
	doc = _context(document)
	frappe.get_doc("Item", item_code).check_permission("read")
	rows = []
	for doctype, child, qty_field in (
		("Stock Entry", "Stock Entry Detail", "qty"),
		("Stock Reconciliation", "Stock Reconciliation Item", "qty"),
	):
		if not frappe.has_permission(doctype, "read"):
			continue
		filters = [[doctype, "company", "=", doc.company], [doctype, "docstatus", "=", 1],
			[doctype, "posting_date", "<=", _cutoff(doc).date()], [child, "item_code", "=", item_code]]
		if doctype == "Stock Entry":
			filters += [[doctype, "purpose", "=", "Material Receipt"]]
		fields = ["name", "posting_date", "posting_time", f"`tab{child}`.`{qty_field}` as qty"]
		for entry in frappe.get_list(doctype, fields=fields, filters=filters,
			order_by=f"`tab{doctype}`.posting_date desc, `tab{doctype}`.creation desc", limit_page_length=10):
			if _timestamp(entry) > _cutoff(doc):
				continue
			entry.doctype = doctype
			rows.append(entry)
	return rows


def warn_before_submit(doc, method=None):
	"""Advisory recheck for UI/API/import submissions. No mutations or new blocks."""
	if doc.get("is_return"):
		return
	try:
		cache = {}
		warnings = []
		for row in doc.get("items", []):
			if not row.item_code:
				continue
			if row.item_code not in cache:
				cache[row.item_code] = _load_history(doc, row.item_code)
			comparison = _comparison(doc, row, *cache[row.item_code])
			if comparison["higher"]:
				warnings.append(_("Row {0}: {1} — net unit cost {2} exceeds previous {3}.").format(
					row.idx, escape(row.item_code), flt(comparison["current_rate"], 6),
					flt(comparison["baseline"]["rate"], 6)))
		if warnings:
			frappe.msgprint("<br>".join(warnings), title=_("Higher purchase rate"), indicator="red")
	except Exception:
		# Optional information must not interrupt existing purchase posting.
		frappe.log_error(title="Retail purchase comparison unavailable")
		frappe.msgprint(_("Purchase rate comparison is unavailable. Please review purchase history manually."),
			title=_("Purchase history"), indicator="orange")
