import frappe
from frappe import _
from frappe.utils import cint, flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_data(filters=None):
	filters = frappe._dict(filters or {})
	rows = get_reorder_rows(filters)
	item_codes = [row.item_code for row in rows]

	barcodes = get_barcodes(item_codes)
	suppliers = get_suppliers(item_codes)
	last_sold_dates = get_last_sold_dates(item_codes)

	data = []
	for row in rows:
		current_stock = flt(row.current_stock)
		reorder_level = flt(row.reorder_level)
		shortage_qty = max(reorder_level - current_stock, 0)

		row.barcode = row.custom_barcode or barcodes.get(row.item_code) or ""
		row.supplier = suppliers.get(row.item_code) or ""
		row.shortage_qty = shortage_qty
		row.stock_value = flt(row.stock_value)
		row.last_sold_date = last_sold_dates.get(row.item_code)
		row.status = get_status(current_stock, reorder_level)

		if filters.get("supplier") and row.supplier != filters.supplier:
			continue
		if cint(filters.get("only_out_of_stock")) and current_stock > 0:
			continue
		if cint(filters.get("only_low_stock")) and current_stock > reorder_level:
			continue

		data.append(row)

	return data


def get_reorder_rows(filters):
	conditions = [
		"i.disabled = 0",
		"i.is_stock_item = 1",
		"ifnull(ir.warehouse_reorder_level, 0) > 0",
	]
	values = {}

	if filters.get("warehouse"):
		conditions.append("ir.warehouse = %(warehouse)s")
		values["warehouse"] = filters.warehouse
	if filters.get("item_group"):
		conditions.append("i.item_group = %(item_group)s")
		values["item_group"] = filters.item_group
	if filters.get("brand"):
		conditions.append("i.brand = %(brand)s")
		values["brand"] = filters.brand

	return frappe.db.sql(
		f"""
		select
			i.name as item_code,
			i.item_name,
			i.custom_barcode,
			i.item_group,
			i.brand,
			ir.warehouse,
			coalesce(b.actual_qty, 0) as current_stock,
			ir.warehouse_reorder_level as reorder_level,
			ir.warehouse_reorder_qty as reorder_qty,
			i.last_purchase_rate,
			coalesce(b.stock_value, 0) as stock_value
		from `tabItem Reorder` ir
		inner join `tabItem` i on i.name = ir.parent
		left join `tabBin` b on b.item_code = i.name and b.warehouse = ir.warehouse
		where {" and ".join(conditions)}
		order by
			case
				when coalesce(b.actual_qty, 0) <= 0 then 0
				when coalesce(b.actual_qty, 0) < ir.warehouse_reorder_level then 1
				when coalesce(b.actual_qty, 0) <= ir.warehouse_reorder_level * 1.25 then 2
				else 3
			end,
			(ir.warehouse_reorder_level - coalesce(b.actual_qty, 0)) desc,
			i.item_name asc
		""",
		values,
		as_dict=True,
	)


def get_status(current_stock, reorder_level):
	if current_stock <= 0:
		return _("Out of Stock")
	if current_stock < reorder_level:
		return _("Critical")
	if current_stock <= reorder_level * 1.25:
		return _("Low Stock")
	return _("Healthy")


def get_barcodes(item_codes):
	if not item_codes:
		return {}

	rows = frappe.db.sql(
		"""
		select parent, barcode
		from `tabItem Barcode`
		where parent in %(item_codes)s
			and ifnull(barcode, '') != ''
		order by parent, idx
		""",
		{"item_codes": tuple(item_codes)},
		as_dict=True,
	)

	barcodes = {}
	for row in rows:
		barcodes.setdefault(row.parent, row.barcode)

	return barcodes


def get_suppliers(item_codes):
	if not item_codes:
		return {}

	rows = frappe.db.sql(
		"""
		select parent, supplier
		from `tabItem Supplier`
		where parent in %(item_codes)s
			and ifnull(supplier, '') != ''
		order by parent, idx
		""",
		{"item_codes": tuple(item_codes)},
		as_dict=True,
	)

	suppliers = {}
	for row in rows:
		suppliers.setdefault(row.parent, row.supplier)

	return suppliers


def get_last_sold_dates(item_codes):
	if not item_codes:
		return {}

	rows = frappe.db.sql(
		"""
		select sii.item_code, max(si.posting_date) as last_sold_date
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		where si.docstatus = 1
			and ifnull(si.is_return, 0) = 0
			and sii.item_code in %(item_codes)s
		group by sii.item_code
		""",
		{"item_codes": tuple(item_codes)},
		as_dict=True,
	)

	return {row.item_code: row.last_sold_date for row in rows}


@frappe.whitelist()
def get_low_stock_items_count():
	return get_stock_count(only_out_of_stock=False)


@frappe.whitelist()
def get_out_of_stock_items_count():
	return get_stock_count(only_out_of_stock=True)


@frappe.whitelist()
def create_or_update_number_cards():
	cards = [
		{
			"name": "Low Stock Items",
			"label": "Low Stock Items",
			"method": "retail.retail_app.report.low_stock_reorder_report.low_stock_reorder_report.get_low_stock_items_count",
			"color": "#F59E0B",
		},
		{
			"name": "Out of Stock Items",
			"label": "Out of Stock Items",
			"method": "retail.retail_app.report.low_stock_reorder_report.low_stock_reorder_report.get_out_of_stock_items_count",
			"color": "#EF4444",
		},
	]

	for card in cards:
		if frappe.db.exists("Number Card", card["name"]):
			doc = frappe.get_doc("Number Card", card["name"])
		else:
			doc = frappe.new_doc("Number Card")
			doc.name = card["name"]

		doc.update(
			{
				"is_standard": 1,
				"module": "Retail-app",
				"label": card["label"],
				"type": "Custom",
				"document_type": "Item",
				"method": card["method"],
				"is_public": 1,
				"show_full_number": 1,
				"color": card["color"],
			}
		)
		doc.save(ignore_permissions=True)

	frappe.db.commit()
	return [card["name"] for card in cards]


def get_stock_count(only_out_of_stock=False):
	filters = frappe._dict({"only_low_stock": 1, "only_out_of_stock": cint(only_out_of_stock)})
	return {
		"value": len(get_data(filters)),
		"fieldtype": "Int",
		"route": ["query-report", "Low Stock Reorder Report"],
		"route_options": {
			"only_low_stock": 1,
			"only_out_of_stock": cint(only_out_of_stock),
		},
	}


def get_columns():
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 190},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Barcode"), "fieldname": "barcode", "fieldtype": "Data", "width": 140},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 130},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"label": _("Current Stock"), "fieldname": "current_stock", "fieldtype": "Float", "width": 120},
		{"label": _("Reorder Level"), "fieldname": "reorder_level", "fieldtype": "Float", "width": 120},
		{"label": _("Reorder Qty"), "fieldname": "reorder_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Shortage Qty"), "fieldname": "shortage_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Last Purchase Rate"), "fieldname": "last_purchase_rate", "fieldtype": "Currency", "width": 140},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
		{"label": _("Stock Value"), "fieldname": "stock_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Last Sold Date"), "fieldname": "last_sold_date", "fieldtype": "Date", "width": 120},
	]
