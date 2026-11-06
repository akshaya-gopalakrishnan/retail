"""Expired batch stock, valued from the posted stock ledger (no stock writes)."""

import frappe
from frappe import _
from frappe.desk.query_report import get_report_doc
from frappe.desk.reportview import get_match_cond
from frappe.utils import add_days, cint, date_diff, flt, getdate, today

from retail.retail_app.report.low_stock_reorder_report.low_stock_reorder_report import get_barcodes


REPORT_NAME = "Expired Items"
SALES = "m.voucher_type in ('Sales Invoice', 'POS Invoice', 'Delivery Note')"
PURCHASES = "m.voucher_type in ('Purchase Receipt', 'Purchase Invoice')"
EXPIRY_ISSUE = """m.voucher_type = 'Stock Entry' and se.purpose = 'Material Issue'
    and (m.posting_date > b.expiry_date
        or lower(se.stock_entry_type) like '%%expir%%')"""


def execute(filters=None):
	filters = prepare_filters(filters)
	data = get_data(filters) if filters.company else []
	return get_columns(), data, None, None, get_summary(data, filters)


def prepare_filters(filters=None):
	get_report_doc(REPORT_NAME)
	frappe.has_permission("Stock Ledger Entry", "read", throw=True)
	filters = frappe._dict(filters or {})
	filters.as_of_date = getdate(filters.get("as_of_date") or today())
	filters.cutoff = add_days(filters.as_of_date, 1)
	filters.qty_precision = cint(frappe.db.get_default("float_precision")) or 3
	if not filters.get("company"):
		default = frappe.defaults.get_user_default("Company") or frappe.defaults.get_global_default("company")
		companies = frappe.get_list("Company", pluck="name", order_by="name")
		filters.company = default if default in companies else next(iter(companies), None)
	elif not frappe.get_list("Company", filters={"name": filters.company}, pluck="name"):
		frappe.throw(_("You do not have access to this company."), frappe.PermissionError)
	return filters


def movement_query(filters, *, all_warehouses=False):
	"""Prefer bundle entries; legacy batch_no must never count the same SLE twice.

	Bundle quantity and value use the same source as Batch-Wise Balance History.
	Match conditions also restrict origin lookups, not only the displayed balances.
	"""
	conditions = [
		"sle.docstatus < 2", "sle.is_cancelled = 0",
		"sle.posting_datetime < %(cutoff)s", "sle.company = %(company)s",
		"b.expiry_date < %(as_of_date)s", "b.item = sle.item_code",
	]
	for field, column in (
		("item_code", "sle.item_code"), ("batch_no", "b.name"),
		("item_group", "i.item_group"), ("brand", "i.brand"),
	):
		if filters.get(field):
			conditions.append(f"{column} = %({field})s")
	if filters.get("warehouse") and not all_warehouses:
		conditions.append("""sle.warehouse in (
			select w.name from `tabWarehouse` w inner join `tabWarehouse` root
				on root.name = %(warehouse)s
			where w.lft >= root.lft and w.rgt <= root.rgt)""")
	match = get_match_cond("Stock Ledger Entry").replace("`tabStock Ledger Entry`", "sle")
	where = " and ".join(conditions) + match
	common = """sle.company, sle.item_code, sle.warehouse, b.name as batch_no,
		sle.posting_date, sle.posting_datetime, sle.creation, sle.name as ledger_entry,
		sle.voucher_type, sle.voucher_no"""
	return f"""
		select {common}, e.qty, e.stock_value_difference as value
		from `tabStock Ledger Entry` sle
		inner join `tabSerial and Batch Entry` e on e.parent = sle.serial_and_batch_bundle
		inner join `tabBatch` b on b.name = e.batch_no
		inner join `tabItem` i on i.name = sle.item_code
		where {where}
		union all
		select {common}, sle.actual_qty as qty, sle.stock_value_difference as value
		from `tabStock Ledger Entry` sle
		inner join `tabBatch` b on b.name = sle.batch_no
		inner join `tabItem` i on i.name = sle.item_code
		where {where} and coalesce(sle.serial_and_batch_bundle, '') = ''
	"""


@frappe.whitelist()
@frappe.read_only()
def get_expired_items_count():
	filters = prepare_filters()
	count = 0
	if filters.company:
		# Match the default report population without receipt/supplier/cost enrichment.
		count = frappe.db.sql(f"""
			select count(distinct stock.item_code) from (
				select m.item_code from ({movement_query(filters)}) m
				group by m.item_code, m.warehouse, m.batch_no
				having round(sum(m.qty), %(qty_precision)s) > 0
			) stock
		""", filters)[0][0]
	return {
		"value": count, "fieldtype": "Int", "route": ["query-report", REPORT_NAME],
		"route_options": {"company": filters.company, "as_of_date": str(filters.as_of_date), "include_depleted": 0},
	}


def get_data(filters):
	having = "" if cint(filters.get("include_depleted")) else "having round(sum(m.qty), %(qty_precision)s) > 0"
	rows = frappe.db.sql(f"""
		select m.company, m.item_code, i.item_name, i.item_group, i.brand, i.stock_uom,
			i.custom_barcode as barcode, m.warehouse, m.batch_no, b.expiry_date,
			b.manufacturing_date, b.disabled as batch_disabled, b.supplier as batch_supplier,
			b.reference_doctype, b.reference_name, c.default_currency as currency,
			sum(m.qty) as remaining_qty, sum(m.value) as remaining_value,
			sum(case when m.qty > 0 then m.qty else 0 end) as total_in_qty,
			sum(case when m.qty < 0 then -m.qty else 0 end) as total_out_qty,
			sum(case when {PURCHASES} and m.qty > 0 then m.qty else 0 end) as received_qty,
			sum(case when {PURCHASES} and m.qty < 0 then -m.qty else 0 end) as supplier_return_qty,
			sum(case when {SALES} and m.qty < 0 then -m.qty else 0 end) as sold_qty,
			sum(case when {SALES} and m.qty > 0 then m.qty else 0 end) as sales_return_qty,
			-sum(case when {SALES} then m.value else 0 end) as cogs,
			max(case when {SALES} and m.qty < 0 then m.posting_date end) as last_sold_date,
			sum(case when {EXPIRY_ISSUE} and m.qty < 0 then -m.qty else 0 end) as expiry_issue_qty,
			-sum(case when {EXPIRY_ISSUE} and m.qty < 0 then m.value else 0 end) as expiry_issue_cost
		from ({movement_query(filters)}) m
		inner join `tabItem` i on i.name = m.item_code
		inner join `tabBatch` b on b.name = m.batch_no
		inner join `tabCompany` c on c.name = m.company
		left join `tabStock Entry` se on m.voucher_type = 'Stock Entry' and se.name = m.voucher_no
		group by m.company, m.item_code, m.warehouse, m.batch_no
		{having}
		order by b.expiry_date, m.item_code, m.batch_no, m.warehouse
	""", filters, as_dict=True)
	if not rows:
		return []
	origins = get_receipt_details(filters, [r.batch_no for r in rows])
	supplier_codes = {code for origin in origins.values() for code in (origin.suppliers or "").split("\n") if code}
	supplier_codes.update(row.batch_supplier for row in rows if row.batch_supplier)
	supplier_names = dict(frappe.get_all("Supplier", filters={"name": ["in", sorted(supplier_codes)]},
		fields=["name", "supplier_name"], as_list=True)) if supplier_codes else {}
	barcodes = get_barcodes([row.item_code for row in rows if not row.barcode])
	data = []
	for row in rows:
		origin = origins.get(row.batch_no, {})
		suppliers = (origin.get("suppliers") or "").split("\n")
		suppliers = [supplier for supplier in suppliers if supplier]
		if not suppliers and row.batch_supplier:
			suppliers = [row.batch_supplier]
		if filters.get("supplier") and filters.supplier not in suppliers:
			continue
		row.supplier = ", ".join(suppliers)
		row.supplier_names = ", ".join(supplier_names.get(code) or code for code in suppliers)
		row.barcode = row.barcode or barcodes.get(row.item_code) or ""
		row.received_date = origin.get("received_date")
		row.last_received_date = origin.get("last_received_date")
		row.receipt_type = origin.get("receipt_type")
		row.receipt_no = origin.get("receipt_no")
		row.cost_per_unit = row.remaining_value / row.remaining_qty if row.remaining_qty else None
		row.remaining_qty = flt(row.remaining_qty, filters.qty_precision)
		row.net_sold_qty = flt(row.sold_qty - row.sales_return_qty, filters.qty_precision)
		row.days_expired = date_diff(filters.as_of_date, row.expiry_date)
		row.expired_stock_value = max(flt(row.remaining_value), 0) if row.remaining_qty > 0 else 0
		row.cost_note = _("Recorded batch ledger cost")
		if row.remaining_qty < 0 or row.remaining_value < -0.01:
			row.cost_note = _("Negative balance; review Stock Ledger")
			row.expired_stock_value = None
		data.append(row)
	return data


def get_receipt_details(filters, batches):
	# Ignore the selected warehouse for batch origin, retaining SLE permissions.
	values = dict(filters, batches=tuple(set(batches)))
	query = movement_query(filters, all_warehouses=True)
	rows = frappe.db.sql(f"""
		select m.batch_no,
			group_concat(distinct coalesce(pr.supplier, pi.supplier) order by coalesce(pr.supplier, pi.supplier) separator '\\n') as suppliers,
			coalesce(min(case when {PURCHASES} then m.posting_date end), min(m.posting_date)) as received_date,
			coalesce(max(case when {PURCHASES} then m.posting_date end), max(m.posting_date)) as last_received_date
		from ({query}) m
		left join `tabPurchase Receipt` pr on m.voucher_type = 'Purchase Receipt' and pr.name = m.voucher_no
		left join `tabPurchase Invoice` pi on m.voucher_type = 'Purchase Invoice' and pi.name = m.voucher_no
		where m.qty > 0 and not ({SALES}) and m.batch_no in %(batches)s
		group by m.batch_no
	""", values, as_dict=True)
	origins = {row.batch_no: row for row in rows}
	first_receipts = frappe.db.sql(f"""
		select batch_no, voucher_type as receipt_type, voucher_no as receipt_no from (
			select m.batch_no, m.voucher_type, m.voucher_no,
				row_number() over (partition by m.batch_no order by
					case when {PURCHASES} then 0 else 1 end,
					m.posting_datetime, m.creation, m.ledger_entry) as receipt_rank
			from ({query}) m where m.qty > 0 and not ({SALES}) and m.batch_no in %(batches)s
		) receipts where receipt_rank = 1
	""", values, as_dict=True)
	for row in first_receipts:
		origins[row.batch_no].update(row)
	return origins


def get_summary(data, filters):
	positive = [row for row in data if row.remaining_qty > 0]
	return [
		{"label": _("Expired Items"), "value": len({r.item_code for r in positive}), "datatype": "Int", "indicator": "Red"},
		{"label": _("Expired Batches"), "value": len({r.batch_no for r in positive}), "datatype": "Int", "indicator": "Red"},
		{"label": _("Expired Loss at Cost"), "value": sum(r.expired_stock_value or 0 for r in data),
		 "datatype": "Currency", "currency": frappe.get_cached_value("Company", filters.company, "default_currency") if filters.company else None,
		 "indicator": "Red"},
	]


def get_columns():
	def col(fieldname, label, fieldtype="Data", options=None, width=130):
		return {"fieldname": fieldname, "label": _(label), "fieldtype": fieldtype, "options": options, "width": width}

	return [
		col("item_code", "Item", "Link", "Item"), col("item_name", "Item Name", width=190),
		col("batch_no", "Batch", "Link", "Batch"), col("warehouse", "Warehouse", "Link", "Warehouse", 160),
		col("remaining_qty", "Expired Qty", "Float"), col("stock_uom", "Stock UOM", "Link", "UOM", 100),
		col("expiry_date", "Expiry Date", "Date"), col("days_expired", "Days Expired", "Int", width=110),
		col("supplier_names", "Supplier Name(s)", width=190), col("supplier", "Supplier(s)", width=150),
		col("received_date", "First Received Date", "Date", width=150),
		col("last_received_date", "Last Received Date", "Date", width=150),
		col("cost_per_unit", "Cost per Stock Unit", "Currency", "currency", 155),
		col("expired_stock_value", "Expired Loss at Cost", "Currency", "currency", 160),
		col("sold_qty", "Sold Qty", "Float"), col("sales_return_qty", "Sales Return Qty", "Float"),
		col("net_sold_qty", "Net Sold Qty", "Float"), col("cogs", "COGS (Net Sold)", "Currency", "currency", 150),
		col("received_qty", "Purchased Qty", "Float"), col("supplier_return_qty", "Supplier Return Qty", "Float", width=155),
		col("expiry_issue_qty", "Expiry Issue Qty", "Float"),
		col("expiry_issue_cost", "Expiry Issue Cost", "Currency", "currency", 150),
		col("total_in_qty", "Total In Qty", "Float"), col("total_out_qty", "Total Out Qty", "Float"),
		col("last_sold_date", "Last Sold Date", "Date"), col("manufacturing_date", "Manufacturing Date", "Date", width=155),
		col("barcode", "Barcode", width=140), col("item_group", "Item Group", "Link", "Item Group"),
		col("brand", "Brand", "Link", "Brand"), col("batch_disabled", "Batch Disabled", "Check"),
		col("receipt_type", "First Receipt Type", width=150),
		col("receipt_no", "First Receipt", "Dynamic Link", "receipt_type", 160),
		col("reference_doctype", "Batch Origin Type", width=150),
		col("reference_name", "Batch Origin", "Dynamic Link", "reference_doctype", 160),
		col("cost_note", "Cost Basis / Review", width=240), col("currency", "Currency", "Link", "Currency", 90),
	]
