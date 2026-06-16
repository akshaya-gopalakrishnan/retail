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
		filters.from_date = frappe.utils.add_days(filters.to_date, -90)


def get_data(filters=None):
	filters = frappe._dict(filters or {})
	set_default_dates(filters)

	stock_rows = get_stock_rows(filters)
	item_codes = [row.item_code for row in stock_rows]
	sales = get_sales_map(filters, item_codes)
	last_sold_dates = get_last_sold_dates(item_codes, filters)
	barcodes = get_barcodes(item_codes)
	suppliers = get_suppliers(item_codes)
	purchase_suppliers = get_purchase_suppliers(item_codes)

	days = max(date_diff(getdate(filters.to_date), getdate(filters.from_date)) + 1, 1)
	max_net_qty = flt(filters.get("max_net_qty"))
	data = []

	for row in stock_rows:
		sale = sales.get((row.item_code, row.warehouse), frappe._dict())
		row.barcode = row.custom_barcode or barcodes.get(row.item_code) or ""
		row.supplier = suppliers.get(row.item_code) or purchase_suppliers.get(row.item_code) or ""
		row.sold_qty = flt(sale.get("sold_qty"))
		row.return_qty = flt(sale.get("return_qty"))
		row.net_qty = flt(sale.get("net_qty"))
		row.net_sales = flt(sale.get("net_sales"))
		row.gross_profit = row.net_sales - flt(sale.get("cost_amount"))
		row.profit_percent = (row.gross_profit / row.net_sales * 100) if row.net_sales else 0
		row.avg_daily_qty = row.net_qty / days
		row.last_sold_date = sale.get("last_sold_date") or last_sold_dates.get(row.item_code)
		row.days_since_sold = date_diff(getdate(filters.to_date), getdate(row.last_sold_date)) if row.last_sold_date else None
		row.stock_value = flt(row.current_stock) * flt(row.last_purchase_rate)
		row.movement_status = get_movement_status(row)

		if filters.get("supplier") and row.supplier != filters.supplier:
			continue
		if cint(filters.get("only_with_stock")) and row.current_stock <= 0:
			continue
		if cint(filters.get("only_no_sales")) and row.net_qty != 0:
			continue
		if not cint(filters.get("only_no_sales")) and max_net_qty > 0 and row.net_qty > max_net_qty:
			continue

		data.append(row)

	data.sort(
		key=lambda row: (
			flt(row.net_qty),
			-flt(row.stock_value),
			-(row.days_since_sold if row.days_since_sold is not None else 999999),
			row.item_name or "",
		)
	)

	limit = cint(filters.get("limit"))
	if limit > 0:
		data = data[:limit]

	for index, row in enumerate(data, start=1):
		row.rank = index

	return data


def get_stock_rows(filters):
	conditions = ["i.disabled = 0", "i.is_stock_item = 1"]
	values = {}

	if filters.get("warehouse"):
		conditions.append("b.warehouse = %(warehouse)s")
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
			coalesce(b.warehouse, '') as warehouse,
			coalesce(sum(b.actual_qty), 0) as current_stock,
			i.last_purchase_rate
		from `tabItem` i
		left join `tabBin` b on b.item_code = i.name
		where {" and ".join(conditions)}
		group by i.name, coalesce(b.warehouse, '')
		""",
		values,
		as_dict=True,
	)


def get_sales_map(filters, item_codes):
	if not item_codes:
		return {}

	conditions = [
		"si.docstatus = 1",
		"si.posting_date between %(from_date)s and %(to_date)s",
		"sii.item_code in %(item_codes)s",
	]
	values = {
		"from_date": filters.from_date,
		"to_date": filters.to_date,
		"item_codes": tuple(item_codes),
	}

	if filters.get("warehouse"):
		conditions.append("sii.warehouse = %(warehouse)s")
		values["warehouse"] = filters.warehouse

	rows = frappe.db.sql(
		f"""
		select
			sii.item_code,
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
			max(si.posting_date) as last_sold_date
		from `tabSales Invoice Item` sii
		inner join `tabSales Invoice` si on si.name = sii.parent
		where {" and ".join(conditions)}
		group by sii.item_code, coalesce(sii.warehouse, '')
		""",
		values,
		as_dict=True,
	)

	return {(row.item_code, row.warehouse): row for row in rows}


def get_last_sold_dates(item_codes, filters):
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
			and si.posting_date <= %(to_date)s
		group by sii.item_code
		""",
		{"item_codes": tuple(item_codes), "to_date": filters.to_date},
		as_dict=True,
	)

	return {row.item_code: row.last_sold_date for row in rows}


def get_movement_status(row):
	if row.net_qty == 0:
		return _("No Sales")
	if row.avg_daily_qty <= 0.1:
		return _("Very Slow")
	return _("Slow Moving")


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
		{"label": _("Current Stock"), "fieldname": "current_stock", "fieldtype": "Float", "width": 120},
		{"label": _("Stock Value"), "fieldname": "stock_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Sold Qty"), "fieldname": "sold_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Return Qty"), "fieldname": "return_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Net Qty"), "fieldname": "net_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Net Sales"), "fieldname": "net_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 120},
		{"label": _("Profit %"), "fieldname": "profit_percent", "fieldtype": "Percent", "width": 90},
		{"label": _("Avg Daily Qty"), "fieldname": "avg_daily_qty", "fieldtype": "Float", "width": 110},
		{"label": _("Last Sold Date"), "fieldname": "last_sold_date", "fieldtype": "Date", "width": 120},
		{"label": _("Days Since Sold"), "fieldname": "days_since_sold", "fieldtype": "Int", "width": 120},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
		{"label": _("Last Purchase Rate"), "fieldname": "last_purchase_rate", "fieldtype": "Currency", "width": 140},
		{"label": _("Status"), "fieldname": "movement_status", "fieldtype": "Data", "width": 110},
	]
