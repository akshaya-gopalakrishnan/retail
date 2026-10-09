import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from retail.van_permissions import validate_van_document_access


@frappe.whitelist()
def get_van_warehouse_stock(warehouse):
	_validate_van_stock_view_permission()
	from retail.van_assignment import assigned_sessions, is_operator
	if is_operator() and warehouse not in {row.van_warehouse for row in assigned_sessions(active=True)}:
		frappe.throw(_("This warehouse is not assigned to your open session."), frappe.PermissionError)
	if not warehouse:
		frappe.throw(_("Please select Van Warehouse first."))

	if not frappe.db.exists("Warehouse", warehouse):
		frappe.throw(_("Warehouse {0} does not exist.").format(frappe.bold(warehouse)))
	frappe.get_doc("Warehouse", warehouse).check_permission("read")

	rows = frappe.db.sql(
		"""
		select
			bin.item_code,
			item.item_name,
			item.stock_uom,
			bin.warehouse,
			bin.actual_qty,
			bin.valuation_rate
		from `tabBin` bin
		inner join `tabItem` item on item.name = bin.item_code
		where bin.warehouse = %(warehouse)s
			and bin.actual_qty > 0
			and ifnull(item.disabled, 0) = 0
		order by item.item_name, bin.item_code
		""",
		{"warehouse": warehouse},
		as_dict=True,
	)

	return [
		{
			"item_code": row.item_code,
			"item_name": row.item_name,
			"stock_uom": row.stock_uom,
			"warehouse": row.warehouse,
			"actual_qty": flt(row.actual_qty),
			"valuation_rate": flt(row.valuation_rate),
		}
		for row in rows
	]


@frappe.whitelist()
def get_van_stock_view(company=None, posting_date=None, van=None, warehouse=None, item_code=None):
	_validate_van_stock_view_permission()

	posting_date = getdate(posting_date or nowdate())
	vans = _get_van_stock_view_vans(van=van, warehouse=warehouse)
	if not vans:
		return {"summary": _empty_stock_view_summary(), "rows": []}

	warehouse_by_van = {row.van_warehouse: row for row in vans if row.van_warehouse}
	warehouses = sorted(warehouse_by_van)
	if not warehouses:
		return {"summary": _empty_stock_view_summary(), "rows": []}

	values = {
		"company": company,
		"posting_date": posting_date,
		"warehouses": warehouses,
		"item_code": item_code,
	}

	stock_rows = frappe.db.sql(
		"""
		select
			sle.warehouse,
			sle.item_code,
			item.item_name,
			item.stock_uom,
			sum(sle.actual_qty) as qty,
			max(concat(sle.posting_date, ' ', sle.posting_time)) as last_movement
		from `tabStock Ledger Entry` sle
		inner join `tabItem` item on item.name = sle.item_code
		where sle.is_cancelled = 0
			and sle.docstatus < 2
			and sle.posting_date <= %(posting_date)s
			and sle.warehouse in %(warehouses)s
			and (%(company)s is null or sle.company = %(company)s)
			and (%(item_code)s is null or sle.item_code = %(item_code)s)
		group by sle.warehouse, sle.item_code, item.item_name, item.stock_uom
		having abs(qty) > 0.000001
		order by sle.warehouse, item.item_name, sle.item_code
		""",
		values,
		as_dict=True,
	)

	valuation_rates = _get_current_valuation_rates(
		[(row.warehouse, row.item_code) for row in stock_rows]
	)

	rows = []
	for row in stock_rows:
		van_row = warehouse_by_van.get(row.warehouse) or frappe._dict()
		rows.append(
			{
				"van": van_row.get("name"),
				"vehicle_name": van_row.get("vehicle_name"),
				"warehouse": row.warehouse,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"stock_uom": row.stock_uom,
				"qty": flt(row.qty),
				"valuation_rate": flt(valuation_rates.get((row.warehouse, row.item_code))),
				"last_movement": row.last_movement,
			}
		)

	return {
		"summary": {
			"vans": len({row["van"] for row in rows if row.get("van")}),
			"warehouses": len({row["warehouse"] for row in rows if row.get("warehouse")}),
			"items": len({row["item_code"] for row in rows if row.get("item_code")}),
			"total_qty": sum(flt(row.get("qty")) for row in rows),
		},
		"rows": rows,
	}


def _validate_van_stock_view_permission():
	from retail.module_access import require
	require("Van Sales")
	roles = set(frappe.get_roles())
	if roles.intersection({"System Manager", "Van Sales User", "Van Sales Manager", "Stock User", "Stock Manager"}):
		return
	frappe.throw(_("Not permitted to view Van Stock View."), frappe.PermissionError)


def _get_van_stock_view_vans(van=None, warehouse=None):
	filters = {}
	from retail.van_assignment import assigned_sessions, is_operator
	if is_operator():
		allowed_vans = {row.van for row in assigned_sessions(active=True)}
		if van and van not in allowed_vans:
			frappe.throw(_("This van is not assigned to you."), frappe.PermissionError)
		filters["name"] = ["in", list(allowed_vans)]
	if van:
		filters["name"] = van
	if warehouse:
		filters["van_warehouse"] = warehouse

	return frappe.get_all(
		"Van Fleet",
		filters=filters,
		fields=["name", "vehicle_name", "van_warehouse"],
		order_by="vehicle_name asc, name asc",
	)


def _get_current_valuation_rates(keys):
	if not keys:
		return {}

	conditions = []
	values = {}
	for index, (warehouse, item_code) in enumerate(keys):
		warehouse_key = f"warehouse_{index}"
		item_key = f"item_{index}"
		values[warehouse_key] = warehouse
		values[item_key] = item_code
		conditions.append(f"(warehouse = %({warehouse_key})s and item_code = %({item_key})s)")

	rows = frappe.db.sql(
		f"""
		select warehouse, item_code, valuation_rate
		from `tabBin`
		where {" or ".join(conditions)}
		""",
		values,
		as_dict=True,
	)
	return {(row.warehouse, row.item_code): flt(row.valuation_rate) for row in rows}


def _empty_stock_view_summary():
	return {"vans": 0, "warehouses": 0, "items": 0, "total_qty": 0}


def merge_duplicate_van_stock_rows(doc, method=None):
	if not getattr(doc, "custom_is_van_stock_entry", 0):
		return

	validate_van_document_access(
		doc,
		"Stock Entry",
		_("You are not allowed to create or update Van Stock Entries."),
	)
	apply_van_stock_entry_warehouse_defaults(doc)

	seen = {}
	duplicates = []

	for row in doc.get("items") or []:
		if not row.item_code:
			continue
		if row.get("custom_foc_parent") or row.get("custom_foc_key"):
			continue  # Native FOC rows must retain their separate valuation identity.
		if row.serial_and_batch_bundle or row.serial_no or row.batch_no:
			continue

		key = (
			row.item_code,
			row.s_warehouse or "",
			row.t_warehouse or "",
			row.uom or "",
		)
		existing = seen.get(key)
		if not existing:
			seen[key] = row
			continue

		existing.qty = flt(existing.qty) + flt(row.qty)
		if hasattr(existing, "custom_foc_qty"):
			existing.custom_foc_qty = flt(existing.custom_foc_qty) + flt(row.custom_foc_qty)
		duplicates.append(row)

	if not duplicates:
		return

	doc.items = [row for row in doc.items if row not in duplicates]
	for index, row in enumerate(doc.items, start=1):
		row.idx = index


def apply_van_stock_entry_warehouse_defaults(doc):
	if not doc.get("custom_van_warehouse"):
		return

	van_entry_type = doc.get("custom_van_stock_entry_type")
	for row in doc.get("items") or []:
		if not row.get("item_code"):
			continue

		if not row.get("conversion_factor"):
			row.conversion_factor = 1
		if not row.get("transfer_qty"):
			row.transfer_qty = flt(row.get("qty")) * flt(row.get("conversion_factor") or 1)

		if van_entry_type in {"Offloading", "Wastage"} and not row.get("s_warehouse"):
			row.s_warehouse = doc.custom_van_warehouse
		elif van_entry_type in {"Loading", "Reloading"} and not row.get("t_warehouse"):
			row.t_warehouse = doc.custom_van_warehouse

	validate_van_stock_entry_warehouses(doc)


def validate_van_stock_entry_warehouses(doc):
	van_warehouse = doc.get("custom_van_warehouse")
	van_entry_type = doc.get("custom_van_stock_entry_type")
	if not van_warehouse or not van_entry_type:
		return

	for row in doc.get("items") or []:
		if not row.get("item_code"):
			continue

		if van_entry_type in {"Offloading", "Wastage"} and row.get("s_warehouse") != van_warehouse:
			frappe.throw(
				_(
					"Row #{0}: Source Warehouse must be the selected Van Warehouse {1} for {2}."
				).format(row.idx, frappe.bold(van_warehouse), frappe.bold(van_entry_type))
			)

		if van_entry_type in {"Loading", "Reloading"} and row.get("t_warehouse") != van_warehouse:
			frappe.throw(
				_(
					"Row #{0}: Target Warehouse must be the selected Van Warehouse {1} for {2}."
				).format(row.idx, frappe.bold(van_warehouse), frappe.bold(van_entry_type))
			)
