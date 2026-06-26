import frappe
from frappe import _
from frappe.utils import cint, getdate, today


REPORT_NAME = "Near Expiry Report"
LEGACY_REPORT_NAME = "Expired Stock Alert"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("days_to_expire", 30)
	return get_columns(), get_data(filters)


def ensure_report():
	if frappe.db.exists("Report", LEGACY_REPORT_NAME):
		if not frappe.db.exists("Report", REPORT_NAME):
			frappe.rename_doc("Report", LEGACY_REPORT_NAME, REPORT_NAME, force=True, ignore_permissions=True)
		else:
			frappe.delete_doc("Report", LEGACY_REPORT_NAME, force=True, ignore_permissions=True)

	if frappe.db.exists("Report", REPORT_NAME):
		frappe.db.set_value(
			"Report",
			REPORT_NAME,
			{"report_name": REPORT_NAME, "report_type": "Script Report", "ref_doctype": "Stock Ledger Entry"},
			update_modified=False,
		)
		return

	frappe.get_doc(
		{
			"doctype": "Report", "name": REPORT_NAME, "report_name": REPORT_NAME,
			"module": "Retail-app", "ref_doctype": "Stock Ledger Entry",
			"report_type": "Script Report", "is_standard": "Yes", "add_total_row": 1,
			"roles": [{"role": "Stock User"}, {"role": "Stock Manager"}],
		}
	).insert(ignore_permissions=True)


def get_data(filters):
	conditions, values, bundle_conditions = get_conditions(filters)
	data = {}

	# Older transactions store the Batch directly on the Stock Ledger Entry.
	for row in frappe.db.sql(
		f"""
		select sle.item_code, item.item_name, sle.batch_no, batch.expiry_date,
			datediff(batch.expiry_date, %(today)s) as days_to_expire,
			sle.warehouse, sum(sle.actual_qty) as qty,
			sum(sle.stock_value_difference) as value, batch.supplier
		from `tabStock Ledger Entry` sle
		inner join `tabItem` item on item.name = sle.item_code
		inner join `tabBatch` batch on batch.name = sle.batch_no
		where {' and '.join(conditions)}
		group by sle.item_code, sle.batch_no, sle.warehouse
		having sum(sle.actual_qty) > 0
		""", values, as_dict=True,
	):
		data[(row.item_code, row.batch_no, row.warehouse)] = row

	# ERPNext v15 stores new batch transactions in Serial and Batch Bundles.
	for row in frappe.db.sql(
		f"""
		select sle.item_code, item.item_name, entry.batch_no, batch.expiry_date,
			datediff(batch.expiry_date, %(today)s) as days_to_expire,
			entry.warehouse, sum(entry.qty) as qty,
			sum(entry.stock_value_difference) as value, batch.supplier
		from `tabStock Ledger Entry` sle
		inner join `tabSerial and Batch Entry` entry on entry.parent = sle.serial_and_batch_bundle
		inner join `tabItem` item on item.name = sle.item_code
		inner join `tabBatch` batch on batch.name = entry.batch_no
		where {' and '.join(bundle_conditions)}
		group by sle.item_code, entry.batch_no, entry.warehouse
		having sum(entry.qty) > 0
		""", values, as_dict=True,
	):
		key = (row.item_code, row.batch_no, row.warehouse)
		if key in data:
			data[key].qty += row.qty
			data[key].value += row.value
		else:
			data[key] = row

	rows = list(data.values())
	rows.sort(key=lambda row: (row.expiry_date, row.item_code, row.warehouse))
	for row in rows:
		row.action_needed = get_action_needed(row.days_to_expire)
	return rows


def get_conditions(filters):
	conditions = [
		"sle.docstatus < 2", "sle.is_cancelled = 0", "sle.batch_no is not null",
		"batch.expiry_date is not null",
		"batch.expiry_date <= date_add(%(today)s, interval %(days_to_expire)s day)",
	]
	# The bundle query does not use the legacy SLE batch field.
	bundle_conditions = [condition for condition in conditions if condition != "sle.batch_no is not null"]
	values = {"today": getdate(today()), "days_to_expire": cint(filters.days_to_expire)}

	if filters.company:
		conditions.append("sle.company = %(company)s")
		bundle_conditions.append("sle.company = %(company)s")
		values["company"] = filters.company
	if filters.warehouse:
		conditions.append("sle.warehouse in %(warehouse)s")
		bundle_conditions.append("entry.warehouse in %(warehouse)s")
		values["warehouse"] = tuple(filters.warehouse if isinstance(filters.warehouse, list) else [filters.warehouse])
	if filters.item_code:
		conditions.append("sle.item_code = %(item_code)s")
		bundle_conditions.append("sle.item_code = %(item_code)s")
		values["item_code"] = filters.item_code
	if filters.supplier:
		conditions.append("batch.supplier = %(supplier)s")
		bundle_conditions.append("batch.supplier = %(supplier)s")
		values["supplier"] = filters.supplier

	return conditions, values, bundle_conditions


def get_action_needed(days_to_expire):
	if days_to_expire < 0:
		return _("Expired — remove from sale and review for write-off")
	if days_to_expire == 0:
		return _("Expires today — remove from sale")
	if days_to_expire <= 7:
		return _("Urgent — prioritize sale, transfer, or return")
	return _("Near expiry — monitor and plan action")


def get_columns():
	return [
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Batch No"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 140},
		{"label": _("Expiry Date"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 110},
		{"label": _("Days to Expire"), "fieldname": "days_to_expire", "fieldtype": "Int", "width": 110},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": _("Value"), "fieldname": "value", "fieldtype": "Currency", "width": 120},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 150},
		{"label": _("Action Needed"), "fieldname": "action_needed", "fieldtype": "Data", "width": 300},
	]
