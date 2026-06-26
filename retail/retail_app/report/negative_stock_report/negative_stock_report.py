import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = ["bin.actual_qty < 0", "warehouse.is_group = 0"]
	values = {}

	if filters.company:
		conditions.append("warehouse.company = %(company)s")
		values["company"] = filters.company
	if filters.warehouse:
		conditions.append("bin.warehouse = %(warehouse)s")
		values["warehouse"] = filters.warehouse
	if filters.item_code:
		conditions.append("bin.item_code = %(item_code)s")
		values["item_code"] = filters.item_code

	data = frappe.db.sql(
		f"""
		select bin.item_code, item.item_name, bin.warehouse, bin.actual_qty,
			item.stock_uom, bin.valuation_rate, bin.stock_value,
			'Receive stock or correct the source transaction' as action_needed
		from `tabBin` bin
		inner join `tabItem` item on item.name = bin.item_code
		inner join `tabWarehouse` warehouse on warehouse.name = bin.warehouse
		where {' and '.join(conditions)}
		order by bin.actual_qty asc, bin.warehouse asc, bin.item_code asc
		""", values, as_dict=True,
	)
	return get_columns(), data


def ensure_report():
	if frappe.db.exists("Report", "Negative Stock Report"):
		return
	frappe.get_doc({
		"doctype": "Report", "name": "Negative Stock Report", "report_name": "Negative Stock Report",
		"module": "Retail-app", "ref_doctype": "Bin", "report_type": "Script Report",
		"is_standard": "Yes", "add_total_row": 1,
		"roles": [{"role": "Stock User"}, {"role": "Stock Manager"}],
	}).insert(ignore_permissions=True)


def get_columns():
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": _("Actual Qty"), "fieldname": "actual_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Stock UOM"), "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 90},
		{"label": _("Valuation Rate"), "fieldname": "valuation_rate", "fieldtype": "Currency", "width": 120},
		{"label": _("Stock Value"), "fieldname": "stock_value", "fieldtype": "Currency", "width": 120},
		{"label": _("Action Needed"), "fieldname": "action_needed", "fieldtype": "Data", "width": 260},
	]
