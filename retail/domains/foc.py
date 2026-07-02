from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


FOC_ITEM_DOCTYPES = (
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
	"Sales Order Item",
	"Delivery Note Item",
	"Sales Invoice Item",
	"POS Invoice Item",
	"Stock Entry Detail",
)

FOC_PARENT_DOCTYPES = (
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
	"POS Invoice",
	"Stock Entry",
)

FOC_STOCK_DOCTYPES = (
	"Purchase Receipt",
	"Purchase Invoice",
	"Delivery Note",
	"Sales Invoice",
	"POS Invoice",
	"Stock Entry",
)


def ensure_foc_fields():
	"""Add FOC quantity fields to retail buying/selling item rows."""
	create_custom_fields(
		{
			doctype: [
				{
					"fieldname": "custom_foc_qty",
					"label": "FOC Qty",
					"fieldtype": "Float",
					"insert_after": "qty",
					"in_list_view": 1,
					"columns": 1,
				},
				{
					"fieldname": "custom_total_stock_qty",
					"label": "Total Stock Qty",
					"fieldtype": "Float",
					"insert_after": "custom_foc_qty",
					"read_only": 1,
					"in_list_view": 1,
					"columns": 1,
				},
			]
			for doctype in FOC_ITEM_DOCTYPES
		}
		| {
				"Stock Ledger Entry": [
					{
						"fieldname": "custom_is_foc_stock_entry",
						"label": "FOC Stock Entry",
						"fieldtype": "Check",
						"insert_after": "actual_qty",
						"read_only": 1,
						"no_copy": 1,
					}
				]
		},
		ignore_validate=True,
	)

	for doctype in FOC_ITEM_DOCTYPES:
		frappe.clear_cache(doctype=doctype)
	frappe.clear_cache(doctype="Stock Ledger Entry")


def apply_foc_quantities(doc, method=None):
	"""Keep paid qty for amounts and show paid+FOC as the row total."""
	if doc.doctype not in FOC_PARENT_DOCTYPES:
		return

	for row in doc.get("items") or []:
		if not row.meta.has_field("custom_foc_qty"):
			continue

		foc_qty = flt(row.get("custom_foc_qty"))
		paid_qty = flt(row.get("qty"))
		total_qty = paid_qty + foc_qty

		row.set("custom_total_stock_qty", total_qty)

		_set_paid_amounts(doc, row, paid_qty)


def _set_paid_amounts(doc, row, paid_qty):
	rate = flt(row.get("rate"))
	net_rate = flt(row.get("net_rate") or rate)
	base_rate = flt(row.get("base_rate") or rate)
	base_net_rate = flt(row.get("base_net_rate") or net_rate or base_rate)
	conversion_rate = flt(doc.get("conversion_rate") or 1)

	if row.meta.has_field("amount"):
		row.set("amount", flt(paid_qty * rate, row.precision("amount")))
	if row.meta.has_field("net_amount"):
		row.set("net_amount", flt(paid_qty * net_rate, row.precision("net_amount")))
	if row.meta.has_field("base_rate"):
		row.set("base_rate", flt(base_rate or rate * conversion_rate, row.precision("base_rate")))
	if row.meta.has_field("base_amount"):
		row.set("base_amount", flt(paid_qty * flt(row.get("base_rate")), row.precision("base_amount")))
	if row.meta.has_field("base_net_rate"):
		row.set(
			"base_net_rate",
			flt(base_net_rate or net_rate * conversion_rate, row.precision("base_net_rate")),
		)
	if row.meta.has_field("base_net_amount"):
		row.set("base_net_amount", flt(paid_qty * flt(row.get("base_net_rate")), row.precision("base_net_amount")))


def add_foc_stock_ledger_entries(doc, method=None):
	"""Post FOC quantities as separate stock ledger rows after the normal movement."""
	if doc.doctype not in FOC_STOCK_DOCTYPES or doc.docstatus != 1:
		return

	if doc.doctype in ("Purchase Invoice", "Sales Invoice", "POS Invoice") and not doc.get("update_stock"):
		return

	if not any(flt(row.get("custom_foc_qty")) for row in doc.get("items") or []):
		return

	if frappe.db.exists(
		"Stock Ledger Entry",
		{
			"voucher_type": doc.doctype,
			"voucher_no": doc.name,
			"custom_is_foc_stock_entry": 1,
			"is_cancelled": 0,
		},
	):
		return

	rows_by_name = {row.name: row for row in doc.get("items") or []}
	normal_entries = frappe.get_all(
		"Stock Ledger Entry",
		filters={
			"voucher_type": doc.doctype,
			"voucher_no": doc.name,
			"is_cancelled": 0,
			"custom_is_foc_stock_entry": ["!=", 1],
		},
		fields=[
			"item_code",
			"warehouse",
			"posting_date",
			"posting_time",
			"fiscal_year",
			"voucher_type",
			"voucher_no",
			"voucher_detail_no",
			"actual_qty",
			"stock_uom",
			"incoming_rate",
			"outgoing_rate",
			"recalculate_rate",
			"company",
			"project",
			"serial_and_batch_bundle",
			"dependant_sle_voucher_detail_no",
		],
		order_by="creation asc",
	)

	foc_entries = []
	for entry in normal_entries:
		row = rows_by_name.get(entry.voucher_detail_no)
		if not row:
			continue

		if _is_rejected_stock_entry(doc, row, entry):
			continue

		foc_qty = flt(row.get("custom_foc_qty"))
		if not foc_qty:
			continue

		conversion_factor = flt(row.get("conversion_factor") or 1)
		foc_stock_qty = flt(foc_qty * conversion_factor, _get_stock_precision(row))
		paid_stock_qty = flt(_get_paid_stock_qty(row), _get_stock_precision(row))

		if not foc_stock_qty:
			continue

		# If a document path already posted paid+FOC in its normal SLE, do not double count it.
		if paid_stock_qty and abs(flt(entry.actual_qty)) > abs(paid_stock_qty):
			continue

		actual_qty = abs(foc_stock_qty) if flt(entry.actual_qty) > 0 else -abs(foc_stock_qty)
		foc_entry = frappe._dict(entry)
		foc_entry.update(
			{
				"actual_qty": actual_qty,
				"custom_is_foc_stock_entry": 1,
				"serial_and_batch_bundle": None,
				"dependant_sle_voucher_detail_no": entry.dependant_sle_voucher_detail_no,
			}
		)

		_set_foc_rates(doc, foc_entry, entry)
		foc_entries.append(foc_entry)

	if foc_entries:
		from erpnext.stock.stock_ledger import make_sl_entries

		make_sl_entries(foc_entries)


@frappe.whitelist()
def post_foc_stock_ledger_for_voucher(doctype, name):
	doc = frappe.get_doc(doctype, name)
	add_foc_stock_ledger_entries(doc)


def _get_paid_stock_qty(row):
	if row.doctype == "Stock Entry Detail":
		return flt(row.get("transfer_qty")) or flt(row.get("qty")) * flt(row.get("conversion_factor") or 1)

	return flt(row.get("qty")) * flt(row.get("conversion_factor") or 1)


def _get_stock_precision(row):
	if row.meta.has_field("stock_qty"):
		return row.precision("stock_qty")
	if row.meta.has_field("transfer_qty"):
		return row.precision("transfer_qty")
	return None


def _is_rejected_stock_entry(doc, row, entry):
	if doc.doctype not in ("Purchase Receipt", "Purchase Invoice"):
		return False

	rejected_warehouse = row.get("rejected_warehouse")
	return rejected_warehouse and entry.warehouse == rejected_warehouse


def _set_foc_rates(doc, foc_entry, normal_entry):
	if flt(foc_entry.actual_qty) > 0:
		foc_entry.outgoing_rate = 0
		foc_entry.incoming_rate = _get_positive_foc_rate(doc, normal_entry)
	else:
		foc_entry.incoming_rate = 0
		if normal_entry.get("outgoing_rate"):
			foc_entry.outgoing_rate = normal_entry.outgoing_rate


def _get_positive_foc_rate(doc, normal_entry):
	if doc.doctype in ("Purchase Receipt", "Purchase Invoice") and not doc.get("is_return"):
		return 0

	return flt(normal_entry.get("incoming_rate"))
