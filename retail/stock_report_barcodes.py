"""Item barcode display and exact barcode filtering for native stock reports."""

import frappe
from frappe import _


REPORTS = {"Stock Ledger", "Stock Balance"}


def matching_items(barcode):
	items = set(frappe.get_all("Item", filters={"custom_barcode": barcode}, pluck="name"))
	for doctype in ("Item Barcode", "Retail Packing Detail"):
		items.update(frappe.get_all(doctype, filters={
			"barcode": barcode, "parenttype": "Item",
		}, pluck="parent"))
	return items


def execute(report_name, filters, native_execute):
	filters = frappe._dict(filters or {})
	barcode = (filters.get("barcode") or "").strip()
	if barcode:
		items = matching_items(barcode)
		selected = filters.get("item_code")
		if isinstance(selected, str):
			selected = frappe.parse_json(selected) if selected.startswith("[") else [selected]
		if selected:
			items.intersection_update(selected)
		if not items:
			# The native ledger treats an empty item lookup as no restriction.
			# Return its normal columns directly, without querying all movements.
			if report_name == "Stock Ledger":
				from erpnext.stock.report.stock_ledger.stock_ledger import get_columns
				result = (get_columns(filters), [])
			else:
				from erpnext.stock.report.stock_balance.stock_balance import StockBalanceReport
				report = StockBalanceReport(filters)
				report.inventory_dimensions = report.get_inventory_dimension_fields()
				result = (report.get_columns(), [])
			return add_barcodes(result)
		filters.item_code = sorted(items)
	return add_barcodes(native_execute(filters))


def add_barcodes(result):
	columns, rows = result[:2]
	columns = list(columns)
	if not any(isinstance(c, dict) and c.get("fieldname") == "barcode" for c in columns):
		index = next((i + 1 for i, c in enumerate(columns)
			if isinstance(c, dict) and c.get("fieldname") == "item_name"), 1)
		columns.insert(index, {"fieldname": "barcode", "label": _("Barcode"),
			"fieldtype": "Data", "width": 150})
	items = sorted({r.get("item_code") for r in rows if isinstance(r, dict) and r.get("item_code")})
	barcodes = {r.name: r.custom_barcode for r in frappe.get_all("Item",
		filters={"name": ["in", items]}, fields=["name", "custom_barcode"])} if items else {}
	for row in rows:
		if isinstance(row, dict):
			row["barcode"] = barcodes.get(row.get("item_code"), "") or ""
	return (columns, rows, *result[2:])
