from retail.retail_app.report.profitability import profit_values, profitability_total
import frappe
from frappe import _
from frappe.utils import flt

from retail.retail_app.report.stock_movement_utils import get_stock_movements


def execute(filters=None):
    from retail.retail_app.report.profitability import report_result
    return report_result(get_data(filters), get_columns())

def get_data(filters=None):
	filters = frappe._dict(filters or {})
	data = []
	amount_cache = {}

	grouped = {}
	for row in get_stock_movements(filters):
		key = (row.voucher_type, row.voucher_no, row.voucher_detail_no)
		if key in grouped:
			grouped[key].stock_value_difference += flt(row.stock_value_difference)
			grouped[key].qty_in += row.qty_in
			grouped[key].qty_out += row.qty_out
		else:
			grouped[key] = row

	for row in grouped.values():
		if row.movement_type not in (_("Sale"), _("Return")):
			continue

		from retail.retail_app.report.profitability import invoice_rows, aggregate_profitability, VALUE_FIELDS
		key = (row.voucher_type, row.voucher_no)
		if key not in amount_cache:
			matched = []
			if row.voucher_type in ("Sales Invoice", "POS Invoice"):
				doc = frappe.get_doc(row.voucher_type, row.voucher_no)
				if doc.docstatus == 1:
					matched = invoice_rows(doc)
			elif row.voucher_type == "Delivery Note":
				links = frappe.get_all("Sales Invoice Item", filters={"delivery_note":row.voucher_no, "docstatus":1}, fields=["parent", "name", "dn_detail"])
				for name in {link.parent for link in links}:
					for item in invoice_rows(frappe.get_doc("Sales Invoice", name)):
						link = next((link for link in links if link.name == item.invoice_item), None)
						if link:
							item.invoice_item = link.dn_detail
							matched.append(item)
			amount_cache[key] = matched
		matched = [item for item in amount_cache[key] if item.invoice_item == row.voucher_detail_no]
		if matched:
			matched = [item for item in matched if all(not filters.get(k) or item.get(k) == filters[k]
				for k in ("customer", "branch", "counter", "cashier", "pos_profile"))]
			if not matched:
				continue
			values = aggregate_profitability(matched, ["invoice_item"])[0]
			row.update({field: values.get(field) for field in VALUE_FIELDS + ("gross_profit", "profit_percent", "source_status")})
			if row.cost_amount is not None and abs(row.cost_amount + flt(row.stock_value_difference)) > 0.011:
				row.source_status += "; Invoiced quantity differs from stock movement; COGS is invoice allocated"
		else:
			if any(filters.get(k) for k in ("customer", "branch", "counter", "cashier", "pos_profile")):
				continue
			row.update({field: None for field in VALUE_FIELDS + ("gross_profit", "profit_percent")})
			row.cost_amount = -flt(row.stock_value_difference)
			row.source_status = "Posted cost; no verified submitted invoice allocation"
		row.qty = row.qty_out or row.qty_in
		data.append(row)

	return data


def get_sales_amount(row, amount_cache):
	if row.voucher_type not in ("Sales Invoice", "POS Invoice"):
		return None

	key = (row.voucher_type, row.voucher_detail_no)
	if key in amount_cache:
		return amount_cache[key]

	table = "Sales Invoice Item" if row.voucher_type == "Sales Invoice" else "POS Invoice Item"
	amount = frappe.db.get_value(table, {"name": row.voucher_detail_no,
		"parent": row.voucher_no, "docstatus": 1}, "base_net_amount")
	amount_cache[key] = flt(amount) if amount is not None else None
	return amount_cache[key]


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Movement Type"), "fieldname": "movement_type", "fieldtype": "Data", "width": 120},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": _("Net Sales"), "fieldname": "sales_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("COGS"), "fieldname": "cost_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit"), "fieldname": "gross_profit", "fieldtype": "Currency", "width": 120},
		{"label": _("Gross Profit Margin %"), "fieldname": "margin_percent", "fieldtype": "Percent", "width": 120},
		{"label": _("Cost Status"), "fieldname": "cost_status", "fieldtype": "Data", "width": 260},
		{"label": _("Customer"), "fieldname": "party", "fieldtype": "Data", "width": 160},
		{"label": _("POS Profile"), "fieldname": "pos_profile_display", "fieldtype": "Link", "options": "POS Profile", "width": 140},
		{"label": _("Cashier / User"), "fieldname": "responsible_user", "fieldtype": "Data", "width": 160},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 130},
		{"label": _("Voucher"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 150},
	]
