import frappe
from frappe import _
from frappe.utils import flt


REPORT_NAME = "Item Family List"
WORKSPACE_NAME = "Item Family List"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def ensure_setup():
	ensure_report()
	ensure_page()
	ensure_workspace()


def ensure_report():
	if frappe.db.exists("Report", REPORT_NAME):
		frappe.db.set_value(
			"Report",
			REPORT_NAME,
			{
				"report_name": REPORT_NAME,
				"report_type": "Script Report",
				"ref_doctype": "Item",
				"module": "Retail-app",
				"is_standard": "Yes",
			},
			update_modified=False,
		)
		return

	frappe.get_doc(
		{
			"doctype": "Report",
			"name": REPORT_NAME,
			"report_name": REPORT_NAME,
			"module": "Retail-app",
			"ref_doctype": "Item",
			"report_type": "Script Report",
			"is_standard": "Yes",
			"add_total_row": 0,
			"roles": [{"role": "Stock User"}, {"role": "Stock Manager"}, {"role": "Sales User"}],
		}
	).insert(ignore_permissions=True)


def ensure_page():
	if frappe.db.exists("Page", "retail-item-family-l"):
		frappe.db.set_value(
			"Page",
			"retail-item-family-l",
			{
				"title": REPORT_NAME,
				"page_name": "retail-item-family-l",
				"module": "Retail-app",
				"standard": "Yes",
			},
			update_modified=False,
		)
		return

	frappe.get_doc(
		{
			"doctype": "Page",
			"name": "retail-item-family-l",
			"page_name": "retail-item-family-l",
			"title": REPORT_NAME,
			"module": "Retail-app",
			"standard": "Yes",
			"icon": "fa fa-sitemap",
			"roles": [{"role": "Stock User"}, {"role": "Stock Manager"}, {"role": "Sales User"}],
		}
	).insert(ignore_permissions=True)


def ensure_workspace():
	if frappe.db.exists("Workspace", WORKSPACE_NAME):
		frappe.db.set_value(
			"Workspace",
			WORKSPACE_NAME,
			{
				"label": WORKSPACE_NAME,
				"title": WORKSPACE_NAME,
				"parent_page": "Items",
				"module": "Retail-app",
				"public": 1,
				"is_hidden": 0,
				"sequence_id": 3.5,
			},
			update_modified=False,
		)
		return

	frappe.get_doc(
		{
			"doctype": "Workspace",
			"name": WORKSPACE_NAME,
			"label": WORKSPACE_NAME,
			"title": WORKSPACE_NAME,
			"module": "Retail-app",
			"parent_page": "Items",
			"public": 1,
			"is_hidden": 0,
			"sequence_id": 3.5,
			"indicator_color": "green",
			"content": "[]",
			"shortcuts": [],
			"links": [],
			"quick_lists": [],
			"number_cards": [],
			"charts": [],
		}
	).insert(ignore_permissions=True)


def get_data(filters):
	conditions, values = get_conditions(filters)
	rows = frappe.db.sql(
		f"""
		select
			item.name as item_code,
			item.item_name,
			item.item_group,
			item.brand,
			item.stock_uom,
			item.disabled,
			coalesce(
				item.custom_barcode,
				(
					select item_barcode.barcode
					from `tabItem Barcode` item_barcode
					where item_barcode.parent = item.name
					order by if(item_barcode.uom = item.stock_uom, 0, 1), item_barcode.idx
					limit 1
				)
			) as item_barcode,
			item.custom_purchase_net_rate as item_purchase_net_rate,
			item.custom_purchase_vat_amount as item_purchase_vat_amount,
			item.custom_purchase_gross_rate as item_purchase_gross_rate,
			item.custom_sales_net_rate as item_selling_net_rate,
			item.custom_sales_vat_amount as item_selling_vat_amount,
			item.custom_sales_gross_rate as item_selling_gross_rate,
			item.custom_margin as item_margin,
			coalesce(stock_balance.real_stock_qty, 0) as real_stock_qty,
			coalesce(stock_movement.in_qty, 0) as in_qty,
			coalesce(stock_movement.out_qty, 0) as out_qty,
			packing.idx,
			packing.barcode,
			packing.uom,
			packing.conversion_factor,
			packing.purchase_rate,
			packing.selling_rate,
			packing.purchase_net_rate,
			packing.purchase_vat_amount,
			packing.purchase_gross_rate,
			packing.selling_net_rate,
			packing.selling_vat_amount,
			packing.selling_gross_rate,
			packing.packing_margin
		from `tabItem` item
		left join `tabRetail Packing Detail` packing on item.name = packing.parent
			and packing.parenttype = 'Item'
			and packing.parentfield = 'custom_retail_packing_detail'
		left join (
			select item_code, sum(actual_qty) as real_stock_qty
			from `tabBin`
			group by item_code
		) stock_balance on stock_balance.item_code = item.name
		left join (
			select
				item_code,
				sum(case when actual_qty > 0 then actual_qty else 0 end) as in_qty,
				sum(case when actual_qty < 0 then abs(actual_qty) else 0 end) as out_qty
			from `tabStock Ledger Entry`
			where is_cancelled = 0
			group by item_code
		) stock_movement on stock_movement.item_code = item.name
		where item.name is not null
			{conditions}
		order by item.item_name, item.name, ifnull(packing.idx, 0)
		""",
		values,
		as_dict=True,
	)

	for row in rows:
		normalize_rates(row)
	return rows


def get_conditions(filters):
	conditions = []
	values = {}

	if filters.get("item_code"):
		conditions.append("item.name = %(item_code)s")
		values["item_code"] = filters.item_code
	if filters.get("item_name"):
		conditions.append("(item.item_name like %(item_name)s or item.name like %(item_name)s)")
		values["item_name"] = f"%{filters.item_name}%"
	if filters.get("item_group"):
		conditions.append("item.item_group = %(item_group)s")
		values["item_group"] = filters.item_group
	if filters.get("brand"):
		conditions.append("item.brand = %(brand)s")
		values["brand"] = filters.brand
	if filters.get("barcode"):
		conditions.append("packing.barcode like %(barcode)s")
		values["barcode"] = f"%{filters.barcode}%"
	if filters.get("disabled") in (0, 1, "0", "1"):
		conditions.append("item.disabled = %(disabled)s")
		values["disabled"] = int(filters.disabled)

	return (" and " + " and ".join(conditions)) if conditions else "", values


def normalize_rates(row):
	row.item_purchase_net_rate = flt(row.item_purchase_net_rate)
	row.item_purchase_gross_rate = flt(row.item_purchase_gross_rate or row.item_purchase_net_rate)
	row.item_purchase_vat_amount = flt(
		row.item_purchase_vat_amount or row.item_purchase_gross_rate - row.item_purchase_net_rate
	)
	row.item_selling_net_rate = flt(row.item_selling_net_rate)
	row.item_selling_gross_rate = flt(row.item_selling_gross_rate or row.item_selling_net_rate)
	row.item_selling_vat_amount = flt(
		row.item_selling_vat_amount or row.item_selling_gross_rate - row.item_selling_net_rate
	)
	row.item_margin = flt(row.item_margin or row.item_selling_net_rate - row.item_purchase_net_rate)
	row.real_stock_qty = flt(row.real_stock_qty)
	row.in_qty = flt(row.in_qty)
	row.out_qty = flt(row.out_qty)
	row.purchase_net_rate = flt(row.purchase_net_rate or row.purchase_rate)
	row.purchase_gross_rate = flt(row.purchase_gross_rate or row.purchase_rate)
	row.purchase_vat_amount = flt(row.purchase_vat_amount or row.purchase_gross_rate - row.purchase_net_rate)
	row.selling_net_rate = flt(row.selling_net_rate or row.selling_rate)
	row.selling_gross_rate = flt(row.selling_gross_rate or row.selling_rate)
	row.selling_vat_amount = flt(row.selling_vat_amount or row.selling_gross_rate - row.selling_net_rate)
	row.packing_margin = flt(row.packing_margin or row.selling_net_rate - row.purchase_net_rate)


def get_columns():
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 160},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 220},
		{"label": _("Item Group"), "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 140},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 120},
		{"label": _("Barcode"), "fieldname": "barcode", "fieldtype": "Data", "width": 140},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 90},
		{"label": _("Conversion"), "fieldname": "conversion_factor", "fieldtype": "Float", "width": 100},
		{"label": _("Real Stock"), "fieldname": "real_stock_qty", "fieldtype": "Float", "width": 100},
		{"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Purchase Excl. VAT"), "fieldname": "purchase_net_rate", "fieldtype": "Currency", "width": 135},
		{"label": _("Purchase VAT"), "fieldname": "purchase_vat_amount", "fieldtype": "Currency", "width": 115},
		{"label": _("Purchase Incl. VAT"), "fieldname": "purchase_gross_rate", "fieldtype": "Currency", "width": 135},
		{"label": _("Selling Excl. VAT"), "fieldname": "selling_net_rate", "fieldtype": "Currency", "width": 130},
		{"label": _("Selling VAT"), "fieldname": "selling_vat_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Selling Incl. VAT"), "fieldname": "selling_gross_rate", "fieldtype": "Currency", "width": 130},
		{"label": _("Margin Excl. VAT"), "fieldname": "packing_margin", "fieldtype": "Currency", "width": 130},
		{"label": _("Disabled"), "fieldname": "disabled", "fieldtype": "Check", "width": 80},
	]
