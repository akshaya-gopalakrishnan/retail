import frappe
from frappe import _
from frappe.utils import cint, flt, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	set_default_dates(filters)
	return get_columns(), get_data(filters)


def set_default_dates(filters):
	if not filters.get("to_date"):
		filters.to_date = today()
	if not filters.get("from_date"):
		filters.from_date = frappe.utils.add_days(filters.to_date, -30)


def get_data(filters=None):
	filters = frappe._dict(filters or {})
	set_default_dates(filters)

	data = []
	if filters.get("adjustment_source") != "Stock Reconciliation":
		data.extend(get_stock_entry_rows(filters))
	if filters.get("adjustment_source") != "Stock Entry":
		data.extend(get_stock_reconciliation_rows(filters))

	data.sort(key=lambda row: (row.posting_date, row.posting_time or "", row.document_no, row.item_code), reverse=True)
	return data


def get_stock_entry_rows(filters):
	conditions = [
		"se.posting_date between %(from_date)s and %(to_date)s",
		"se.docstatus in %(docstatus)s",
		"sed.item_code is not null",
	]
	values = get_common_values(filters)

	if filters.get("company"):
		conditions.append("se.company = %(company)s")
	if filters.get("item_code"):
		conditions.append("sed.item_code = %(item_code)s")
	if filters.get("item_group"):
		conditions.append("i.item_group = %(item_group)s")
	if filters.get("stock_entry_type"):
		conditions.append("se.stock_entry_type = %(stock_entry_type)s")
	if filters.get("user"):
		conditions.append("se.owner = %(user)s")

	warehouse_condition = ""
	if filters.get("warehouse"):
		warehouse_condition = "and (sed.s_warehouse = %(warehouse)s or sed.t_warehouse = %(warehouse)s)"

	rows = frappe.db.sql(
		f"""
		select
			se.name as document_no,
			se.posting_date,
			se.posting_time,
			se.company,
			se.docstatus,
			se.purpose,
			se.stock_entry_type,
			se.owner,
			se.modified_by,
			se.modified,
			se.remarks,
			sed.item_code,
			sed.item_name,
			i.item_group,
			sed.stock_uom,
			sed.s_warehouse,
			sed.t_warehouse,
			coalesce(sed.transfer_qty, sed.qty, 0) as qty,
			coalesce(sed.basic_amount, sed.amount, 0) as amount
		from `tabStock Entry Detail` sed
		inner join `tabStock Entry` se on se.name = sed.parent
		left join `tabItem` i on i.name = sed.item_code
		where {" and ".join(conditions)}
			{warehouse_condition}
		""",
		values,
		as_dict=True,
	)

	data = []
	for row in rows:
		if row.s_warehouse and (not filters.get("warehouse") or row.s_warehouse == filters.warehouse):
			data.append(make_stock_entry_row(row, row.s_warehouse, -abs(flt(row.qty))))
		if row.t_warehouse and (not filters.get("warehouse") or row.t_warehouse == filters.warehouse):
			data.append(make_stock_entry_row(row, row.t_warehouse, abs(flt(row.qty))))

	return data


def make_stock_entry_row(row, warehouse, net_qty):
	qty_in = net_qty if net_qty > 0 else 0
	qty_out = abs(net_qty) if net_qty < 0 else 0
	value_change = abs(flt(row.amount)) if net_qty > 0 else -abs(flt(row.amount))

	return frappe._dict(
		{
			"posting_date": row.posting_date,
			"posting_time": row.posting_time,
			"source": _("Stock Entry"),
			"document_type": "Stock Entry",
			"document_no": row.document_no,
			"status": _("Cancelled") if row.docstatus == 2 else _("Submitted"),
			"adjustment_type": get_stock_entry_adjustment_type(row, net_qty),
			"stock_entry_type": row.stock_entry_type,
			"item_code": row.item_code,
			"item_name": row.item_name,
			"item_group": row.item_group,
			"warehouse": warehouse,
			"qty_before": None,
			"qty_after": None,
			"qty_in": qty_in,
			"qty_out": qty_out,
			"net_qty": net_qty,
			"stock_uom": row.stock_uom,
			"value_change": value_change,
			"created_by": row.owner,
			"cancelled_by": row.modified_by if row.docstatus == 2 else "",
			"cancelled_on": row.modified if row.docstatus == 2 else None,
			"company": row.company,
			"remarks": row.remarks,
		}
	)


def get_stock_entry_adjustment_type(row, net_qty):
	if row.purpose == "Material Transfer":
		return _("Transfer In") if net_qty > 0 else _("Transfer Out")
	if net_qty > 0:
		return _("Stock Increase")
	if net_qty < 0:
		return _("Stock Decrease")
	return row.purpose or row.stock_entry_type or _("Adjustment")


def get_stock_reconciliation_rows(filters):
	conditions = [
		"sr.posting_date between %(from_date)s and %(to_date)s",
		"sr.docstatus in %(docstatus)s",
	]
	values = get_common_values(filters)

	if filters.get("company"):
		conditions.append("sr.company = %(company)s")
	if filters.get("warehouse"):
		conditions.append("sri.warehouse = %(warehouse)s")
	if filters.get("item_code"):
		conditions.append("sri.item_code = %(item_code)s")
	if filters.get("item_group"):
		conditions.append("sri.item_group = %(item_group)s")
	if filters.get("user"):
		conditions.append("sr.owner = %(user)s")

	rows = frappe.db.sql(
		f"""
		select
			sr.name as document_no,
			sr.posting_date,
			sr.posting_time,
			sr.company,
			sr.docstatus,
			sr.owner,
			sr.modified_by,
			sr.modified,
			sr.purpose,
			sr.expense_account,
			sr.remarks,
			sri.item_code,
			sri.item_name,
			sri.item_group,
			sri.warehouse,
			sri.stock_uom,
			sri.current_qty,
			sri.qty,
			sri.quantity_difference,
			sri.amount_difference
		from `tabStock Reconciliation Item` sri
		inner join `tabStock Reconciliation` sr on sr.name = sri.parent
		where {" and ".join(conditions)}
		""",
		values,
		as_dict=True,
	)

	data = []
	for row in rows:
		net_qty = flt(row.quantity_difference)
		if not net_qty and row.qty is not None and row.current_qty is not None:
			net_qty = flt(row.qty) - flt(row.current_qty)

		data.append(
			frappe._dict(
				{
					"posting_date": row.posting_date,
					"posting_time": row.posting_time,
					"source": _("Stock Reconciliation"),
					"document_type": "Stock Reconciliation",
					"document_no": row.document_no,
					"status": _("Cancelled") if row.docstatus == 2 else _("Submitted"),
					"adjustment_type": _("Stock Increase") if net_qty > 0 else _("Stock Decrease") if net_qty < 0 else _("Value Adjustment"),
					"stock_entry_type": "",
					"item_code": row.item_code,
					"item_name": row.item_name,
					"item_group": row.item_group,
					"warehouse": row.warehouse,
					"qty_before": flt(row.current_qty),
					"qty_after": flt(row.qty),
					"qty_in": net_qty if net_qty > 0 else 0,
					"qty_out": abs(net_qty) if net_qty < 0 else 0,
					"net_qty": net_qty,
					"stock_uom": row.stock_uom,
					"value_change": flt(row.amount_difference),
					"created_by": row.owner,
					"cancelled_by": row.modified_by if row.docstatus == 2 else "",
					"cancelled_on": row.modified if row.docstatus == 2 else None,
					"company": row.company,
					"remarks": row.remarks,
				}
			)
		)

	return data


def get_common_values(filters):
	return {
		"from_date": filters.from_date,
		"to_date": filters.to_date,
		"docstatus": (1, 2) if cint(filters.get("include_cancelled")) else (1,),
		"company": filters.get("company"),
		"warehouse": filters.get("warehouse"),
		"item_code": filters.get("item_code"),
		"item_group": filters.get("item_group"),
		"stock_entry_type": filters.get("stock_entry_type"),
		"user": filters.get("user"),
	}


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Time"), "fieldname": "posting_time", "fieldtype": "Time", "width": 90},
		{"label": _("Source"), "fieldname": "source", "fieldtype": "Data", "width": 150},
		{"label": _("Document"), "fieldname": "document_no", "fieldtype": "Dynamic Link", "options": "document_type", "width": 170},
		{"label": _("Document Type"), "fieldname": "document_type", "fieldtype": "Data", "width": 140},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Adjustment Type"), "fieldname": "adjustment_type", "fieldtype": "Data", "width": 130},
		{"label": _("Stock Entry Type"), "fieldname": "stock_entry_type", "fieldtype": "Link", "options": "Stock Entry Type", "width": 150},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 130},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": _("Qty Before"), "fieldname": "qty_before", "fieldtype": "Float", "width": 100},
		{"label": _("Qty After"), "fieldname": "qty_after", "fieldtype": "Float", "width": 100},
		{"label": _("Qty In"), "fieldname": "qty_in", "fieldtype": "Float", "width": 90},
		{"label": _("Qty Out"), "fieldname": "qty_out", "fieldtype": "Float", "width": 90},
		{"label": _("Net Qty"), "fieldname": "net_qty", "fieldtype": "Float", "width": 90},
		{"label": _("UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": _("Value Change"), "fieldname": "value_change", "fieldtype": "Currency", "width": 120},
		{"label": _("Created By"), "fieldname": "created_by", "fieldtype": "Link", "options": "User", "width": 160},
		{"label": _("Cancelled By"), "fieldname": "cancelled_by", "fieldtype": "Link", "options": "User", "width": 160},
		{"label": _("Cancelled On"), "fieldname": "cancelled_on", "fieldtype": "Datetime", "width": 160},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
	]
