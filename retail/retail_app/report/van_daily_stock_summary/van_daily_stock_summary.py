from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from retail.retail_app.report.van_sales_report_utils import (
	filter_values,
	get_van_sales_items,
	get_van_stock_items,
	normalize_filters,
	signed_qty,
)


def execute(filters=None):
	filters = normalize_filters(filters)
	return get_columns(), get_data(filters), None, None, None, 1


def get_data(filters):
	rows = defaultdict(new_row)
	for stock in get_van_stock_items(filters):
		key = get_key(stock)
		row = rows[key]
		set_identity(row, stock)
		qty = flt(stock.transfer_qty or stock.qty)
		amount = flt(stock.basic_amount or stock.amount)
		if stock.van_stock_entry_type == "Loading":
			row.loaded_qty += qty
			row.loaded_amount += amount
		elif stock.van_stock_entry_type == "Reloading":
			row.reloaded_qty += qty
			row.reloaded_amount += amount
		elif stock.van_stock_entry_type == "Offloading":
			row.offloaded_qty += qty
			row.offloaded_amount += amount
		elif stock.van_stock_entry_type == "Wastage":
			row.wastage_qty += qty
			row.wastage_amount += amount

	for item in get_van_sales_items(filters):
		key = get_key(item)
		row = rows[key]
		row.posting_date = item.posting_date
		row.van_session = item.van_session
		row.van = item.van
		row.driver = item.driver
		row.driver_name = item.driver_name
		row.item_code = item.item_code
		row.item_name = item.item_name
		row.uom = item.stock_uom or item.uom
		row.sales_qty += signed_qty(item)

	apply_opening_qty(rows, filters)

	data = []
	for row in rows.values():
		row.closing_qty = (
			flt(row.opening_qty)
			+ flt(row.loaded_qty)
			+ flt(row.reloaded_qty)
			- flt(row.sales_qty)
			- flt(row.offloaded_qty)
			- flt(row.wastage_qty)
		)
		data.append(row)

	data.sort(key=lambda row: (row.posting_date, row.van or "", row.item_code or ""), reverse=True)
	add_daily_stock_total_row(data)
	return data


def new_row():
	return frappe._dict({
		"posting_date": None,
		"van_session": None,
		"van": None,
		"driver": None,
		"driver_name": None,
		"item_code": None,
		"item_name": None,
		"uom": None,
		"opening_qty": 0,
		"loaded_qty": 0,
		"reloaded_qty": 0,
		"sales_qty": 0,
		"offloaded_qty": 0,
		"wastage_qty": 0,
		"closing_qty": 0,
		"loaded_amount": 0,
		"reloaded_amount": 0,
		"offloaded_amount": 0,
		"wastage_amount": 0,
	})


def set_identity(row, stock):
	row.posting_date = stock.posting_date
	row.van_session = stock.van_session
	row.van = stock.van
	row.driver = stock.driver
	row.driver_name = stock.driver_name
	row.item_code = stock.item_code
	row.item_name = stock.item_name
	row.uom = stock.stock_uom or stock.uom


def get_key(row):
	return (row.posting_date, row.van_session, row.van, row.item_code)


def apply_opening_qty(rows, filters):
	if not rows:
		return

	warehouse_item_dates = defaultdict(set)
	for row in rows.values():
		if row.van and row.item_code and row.posting_date:
			warehouse_item_dates[row.van].add((row.item_code, row.posting_date))

	if not warehouse_item_dates:
		return

	van_warehouses = frappe._dict(
		frappe.get_all(
			"Van Fleet",
			filters={"name": ["in", list(warehouse_item_dates)]},
			fields=["name", "van_warehouse"],
			as_list=True,
		)
	)
	opening_qty = get_opening_qty(filters, van_warehouses, warehouse_item_dates)

	for row in rows.values():
		warehouse = van_warehouses.get(row.van)
		row.opening_qty = opening_qty.get((warehouse, row.item_code, row.posting_date), 0)


def get_opening_qty(filters, van_warehouses, warehouse_item_dates):
	values = filter_values(filters)
	values["warehouses"] = list(set(van_warehouses.values()))
	values["items"] = sorted({item for items in warehouse_item_dates.values() for item, _posting_date in items})

	if not values["warehouses"] or not values["items"]:
		return {}

	ledger_entries = frappe.db.sql(
		"""
		select
			sle.posting_date,
			sle.warehouse,
			sle.item_code,
			sle.actual_qty
		from `tabStock Ledger Entry` sle
		where sle.docstatus < 2
			and sle.is_cancelled = 0
			and (%(company)s is null or sle.company = %(company)s)
			and sle.posting_date < %(to_date)s
			and sle.warehouse in %(warehouses)s
			and sle.item_code in %(items)s
		order by sle.posting_date, sle.posting_time, sle.creation, sle.name
		""",
		values,
		as_dict=True,
	)

	required_dates = defaultdict(set)
	for van, item_dates in warehouse_item_dates.items():
		warehouse = van_warehouses.get(van)
		if not warehouse:
			continue
		for item_code, posting_date in item_dates:
			required_dates[(warehouse, item_code)].add(posting_date)

	opening_qty = defaultdict(float)
	for entry in ledger_entries:
		key = (entry.warehouse, entry.item_code)
		for posting_date in required_dates.get(key, ()):
			if entry.posting_date < posting_date:
				opening_qty[(entry.warehouse, entry.item_code, posting_date)] += flt(entry.actual_qty)

	return opening_qty


def add_daily_stock_total_row(data):
	if not data:
		return

	total = frappe._dict({"posting_date": _("Total"), "item_name": _("Total"), "is_total_row": 1})
	movement_fields = (
		"loaded_qty",
		"reloaded_qty",
		"sales_qty",
		"offloaded_qty",
		"wastage_qty",
		"loaded_amount",
		"reloaded_amount",
		"offloaded_amount",
		"wastage_amount",
	)

	for row in data:
		for field in movement_fields:
			total[field] = flt(total.get(field)) + flt(row.get(field))

	latest_closing_by_item = {}
	for row in data:
		key = (row.van, row.item_code)
		if key not in latest_closing_by_item:
			latest_closing_by_item[key] = flt(row.closing_qty)

	total.opening_qty = None
	total.closing_qty = sum(latest_closing_by_item.values())
	data.append(total)


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Van Session"), "fieldname": "van_session", "fieldtype": "Link", "options": "Van Session", "width": 160},
		{"label": _("Van"), "fieldname": "van", "fieldtype": "Link", "options": "Van Fleet", "width": 120},
		{"label": _("Driver"), "fieldname": "driver", "fieldtype": "Link", "options": "Driver", "width": 150},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("Opening Qty"), "fieldname": "opening_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Loaded Qty"), "fieldname": "loaded_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Reloaded Qty"), "fieldname": "reloaded_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Sales Qty"), "fieldname": "sales_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Offloaded Qty"), "fieldname": "offloaded_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Wastage Qty"), "fieldname": "wastage_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Closing Qty"), "fieldname": "closing_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Wastage Amount"), "fieldname": "wastage_amount", "fieldtype": "Currency", "width": 130},
	]
