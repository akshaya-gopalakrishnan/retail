import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, today


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

	rows = get_sales_rows(filters)
	item_codes = [row.item_code for row in rows]
	stock = get_current_stock(item_codes, filters)
	barcodes = get_barcodes(item_codes)
	suppliers = get_suppliers(item_codes)
	purchase_suppliers = get_purchase_suppliers(item_codes)

	days = max(date_diff(getdate(filters.to_date), getdate(filters.from_date)) + 1, 1)
	data = []

	for index, row in enumerate(rows, start=1):
		row.rank = index
		row.barcode = row.custom_barcode or barcodes.get(row.item_code) or ""
		row.supplier = suppliers.get(row.item_code) or purchase_suppliers.get(row.item_code) or ""
		row.avg_daily_qty = flt(row.net_qty) / days
		row.current_stock = flt(stock.get((row.item_code, row.warehouse), 0))
		row.days_cover = row.current_stock / row.avg_daily_qty if row.avg_daily_qty and row.current_stock > 0 else 0
		row.gross_profit = flt(row.net_sales) - flt(row.cost_amount)
		row.profit_percent = (row.gross_profit / row.net_sales * 100) if row.net_sales else 0
		row.movement_status = get_movement_status(row)

		if filters.get("supplier") and row.supplier != filters.supplier:
			continue
		if cint(filters.get("hide_zero_stock")) and row.current_stock <= 0:
			continue

		data.append(row)

	limit = cint(filters.get("limit"))
	if limit > 0:
		data = data[:limit]
		for index, row in enumerate(data, start=1):
			row.rank = index

	return data


def get_sales_rows(filters):
	conditions = [
		"si.docstatus = 1",
		"si.posting_date between %(from_date)s and %(to_date)s",
		"i.is_stock_item = 1",
	]
	values = {
		"from_date": filters.from_date,
		"to_date": filters.to_date,
	}

	if filters.get("warehouse"):
		conditions.append("sii.warehouse = %(warehouse)s")
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
			sii.item_code,
			sii.item_name,
			i.custom_barcode,
			i.item_group,
			i.brand,
			coalesce(sii.warehouse, '') as warehouse,
			sum(case when si.is_return = 1 then 0 else abs(sii.stock_qty) end) as sold_qty,
			sum(case when si.is_return = 1 then abs(sii.stock_qty) else 0 end) as return_qty,
			sum(case when si.is_return = 1 then -abs(sii.stock_qty) else abs(sii.stock_qty) end) as net_qty,
			sum(case when si.is_return = 1 then -abs(sii.base_net_amount) else abs(sii.base_net_amount) end) as net_sales,
			sum(
				case
					when si.is_return = 1 then -abs(sii.stock_qty) * coalesce(sii.incoming_rate, 0)
					else abs(sii.stock_qty) * coalesce(sii.incoming_rate, 0)
				end
			) as cost_amount,
			count(distinct si.name) as invoice_count,
			max(si.posting_date) as last_sold_date,
			i.last_purchase_rate
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		inner join `tabItem` i on i.name = sii.item_code
		where {" and ".join(conditions)}
		group by sii.item_code, coalesce(sii.warehouse, '')
		having net_qty > 0
		order by net_qty desc, net_sales desc, sii.item_name asc
		""",
		values,
		as_dict=True,
	)


def get_current_stock(item_codes, filters):
	if not item_codes:
		return {}

	conditions = ["item_code in %(item_codes)s"]
	values = {"item_codes": tuple(item_codes)}

	if filters.get("warehouse"):
		conditions.append("warehouse = %(warehouse)s")
		values["warehouse"] = filters.warehouse

	rows = frappe.db.sql(
		f"""
		select item_code, warehouse, sum(actual_qty) as actual_qty
		from `tabBin`
		where {" and ".join(conditions)}
		group by item_code, warehouse
		""",
		values,
		as_dict=True,
	)

	return {(row.item_code, row.warehouse): flt(row.actual_qty) for row in rows}


def get_movement_status(row):
	if row.current_stock <= 0:
		return _("Stock Risk")
	if row.avg_daily_qty and row.days_cover <= 7:
		return _("Stock Risk")
	if row.rank <= 10:
		return _("Fast Moving")
	return _("Moving")


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


def get_purchase_suppliers(item_codes):
	if not item_codes:
		return {}

	rows = frappe.db.sql(
		"""
		select item_code, supplier
		from (
			select
				pii.item_code,
				pi.supplier,
				pi.posting_date,
				pi.creation
			from `tabPurchase Invoice Item` pii
			inner join `tabPurchase Invoice` pi on pi.name = pii.parent
			where pi.docstatus = 1
				and pii.item_code in %(item_codes)s
				and ifnull(pi.supplier, '') != ''

			union all

			select
				pri.item_code,
				pr.supplier,
				pr.posting_date,
				pr.creation
			from `tabPurchase Receipt Item` pri
			inner join `tabPurchase Receipt` pr on pr.name = pri.parent
			where pr.docstatus = 1
				and pri.item_code in %(item_codes)s
				and ifnull(pr.supplier, '') != ''
		) purchases
		order by item_code, posting_date desc, creation desc
		""",
		{"item_codes": tuple(item_codes)},
		as_dict=True,
	)

	suppliers = {}
	for row in rows:
		suppliers.setdefault(row.item_code, row.supplier)

	return suppliers


def get_columns():
	return [
		{"label": _("Rank"), "fieldname": "rank", "fieldtype": "Int", "width": 70},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 190},
		{"label": _("Barcode"), "fieldname": "barcode", "fieldtype": "Data", "width": 140},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 130},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 120},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"label": _("Sold Qty"), "fieldname": "sold_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Return Qty"), "fieldname": "return_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Net Qty"), "fieldname": "net_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 120},
		{"label": _("Profit %"), "fieldname": "profit_percent", "fieldtype": "Percent", "width": 90},
		{"label": _("Avg Daily Qty"), "fieldname": "avg_daily_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Current Stock"), "fieldname": "current_stock", "fieldtype": "Float", "width": 120},
		{"label": _("Days Cover"), "fieldname": "days_cover", "fieldtype": "Float", "width": 100},
		{"label": _("Last Sold Date"), "fieldname": "last_sold_date", "fieldtype": "Date", "width": 120},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
		{"label": _("Last Purchase Rate"), "fieldname": "last_purchase_rate", "fieldtype": "Currency", "width": 140},
		{"label": _("Status"), "fieldname": "movement_status", "fieldtype": "Data", "width": 110},
	]
