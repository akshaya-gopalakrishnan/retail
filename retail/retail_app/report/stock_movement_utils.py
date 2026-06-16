from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate


SALES_VOUCHERS = ("POS Invoice", "Sales Invoice", "Delivery Note")
PURCHASE_VOUCHERS = ("Purchase Receipt", "Purchase Invoice")
DAMAGE_KEYWORDS = ("damage", "wastage", "expired", "expiry", "broken", "spoil", "theft", "loss")
EXPIRY_KEYWORDS = ("expired", "expiry")


def get_default_filters(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", getdate())
	filters.setdefault("to_date", getdate())
	return filters


def get_conditions(filters, alias="sle"):
	conditions = [f"{alias}.docstatus < 2", f"{alias}.is_cancelled = 0"]
	values = {
		"from_date": filters.get("from_date"),
		"to_date": filters.get("to_date"),
	}

	if filters.get("from_date"):
		conditions.append(f"{alias}.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append(f"{alias}.posting_date <= %(to_date)s")
	if filters.get("company"):
		conditions.append(f"{alias}.company = %(company)s")
		values["company"] = filters.company
	if filters.get("warehouse"):
		conditions.append(f"{alias}.warehouse in %(warehouse)s")
		values["warehouse"] = as_tuple(filters.warehouse)
	if filters.get("item_code"):
		conditions.append(f"{alias}.item_code in %(item_code)s")
		values["item_code"] = as_tuple(filters.item_code)
	if filters.get("voucher_type"):
		conditions.append(f"{alias}.voucher_type = %(voucher_type)s")
		values["voucher_type"] = filters.voucher_type
	if filters.get("voucher_no"):
		conditions.append(f"{alias}.voucher_no = %(voucher_no)s")
		values["voucher_no"] = filters.voucher_no
	if filters.get("batch_no"):
		conditions.append(f"{alias}.batch_no = %(batch_no)s")
		values["batch_no"] = filters.batch_no
	if filters.get("item_group"):
		conditions.append("item.item_group = %(item_group)s")
		values["item_group"] = filters.item_group

	return " and ".join(conditions), values


def as_tuple(value):
	if isinstance(value, str):
		value = [value]
	return tuple(value or [])


def get_stock_movements(filters=None):
	filters = get_default_filters(filters)
	conditions, values = get_conditions(filters)

	rows = frappe.db.sql(
		f"""
		select
			sle.name,
			sle.posting_date,
			sle.posting_time,
			sle.posting_datetime,
			sle.company,
			sle.item_code,
			item.item_name,
			item.item_group,
			item.brand,
			item.stock_uom,
			sle.warehouse,
			sle.actual_qty,
			sle.qty_after_transaction,
			sle.stock_value,
			sle.stock_value_difference,
			sle.valuation_rate,
			sle.voucher_type,
			sle.voucher_no,
			sle.voucher_detail_no,
			sle.batch_no,
			batch.expiry_date,
			sle.owner as entry_owner,
			se.stock_entry_type,
			se.purpose as stock_entry_purpose,
			se.owner as stock_entry_owner,
			se.supplier as stock_entry_supplier,
			se.is_return as stock_entry_is_return,
			si.customer as sales_customer,
			si.pos_profile as sales_pos_profile,
			si.is_return as sales_is_return,
			si.owner as sales_owner,
			pos.customer as pos_customer,
			pos.pos_profile as pos_profile,
			pos.is_return as pos_is_return,
			pos.owner as pos_owner,
			dn.customer as delivery_customer,
			dn.is_return as delivery_is_return,
			dn.owner as delivery_owner,
			pr.supplier as purchase_receipt_supplier,
			pr.is_return as purchase_receipt_is_return,
			pr.owner as purchase_receipt_owner,
			pi.supplier as purchase_invoice_supplier,
			pi.is_return as purchase_invoice_is_return,
			pi.owner as purchase_invoice_owner
		from `tabStock Ledger Entry` sle
		inner join `tabItem` item on item.name = sle.item_code
		left join `tabBatch` batch on batch.name = sle.batch_no
		left join `tabStock Entry` se
			on se.name = sle.voucher_no and sle.voucher_type = 'Stock Entry'
		left join `tabSales Invoice` si
			on si.name = sle.voucher_no and sle.voucher_type = 'Sales Invoice'
		left join `tabPOS Invoice` pos
			on pos.name = sle.voucher_no and sle.voucher_type = 'POS Invoice'
		left join `tabDelivery Note` dn
			on dn.name = sle.voucher_no and sle.voucher_type = 'Delivery Note'
		left join `tabPurchase Receipt` pr
			on pr.name = sle.voucher_no and sle.voucher_type = 'Purchase Receipt'
		left join `tabPurchase Invoice` pi
			on pi.name = sle.voucher_no and sle.voucher_type = 'Purchase Invoice'
		where {conditions}
		order by sle.posting_datetime desc, sle.creation desc
		""",
		values,
		as_dict=True,
	)

	movements = []
	for row in rows:
		row = frappe._dict(row)
		row.update(classify_movement(row))
		if filters.get("movement_type") and row.movement_type != filters.movement_type:
			continue
		row.qty_in = max(flt(row.actual_qty), 0)
		row.qty_out = abs(min(flt(row.actual_qty), 0))
		row.net_qty = flt(row.actual_qty)
		row.responsible_user = get_responsible_user(row)
		row.party = get_party(row)
		row.pos_profile_display = row.get("sales_pos_profile") or row.get("pos_profile")
		movements.append(row)

	return movements


def classify_movement(row):
	voucher_type = row.voucher_type
	actual_qty = flt(row.actual_qty)

	if voucher_type in SALES_VOUCHERS:
		is_return = row.get("sales_is_return") or row.get("pos_is_return") or row.get("delivery_is_return")
		return {"movement_type": _("Return") if is_return or actual_qty > 0 else _("Sale")}

	if voucher_type in PURCHASE_VOUCHERS:
		is_return = row.get("purchase_receipt_is_return") or row.get("purchase_invoice_is_return")
		return {"movement_type": _("Purchase Return") if is_return or actual_qty < 0 else _("Purchase")}

	if voucher_type == "Stock Entry":
		return {"movement_type": row.stock_entry_type or row.stock_entry_purpose or _("Stock Entry")}

	if voucher_type == "Stock Reconciliation":
		return {"movement_type": _("Adjustment")}

	return {"movement_type": voucher_type}


def get_party(row):
	return (
		row.get("sales_customer")
		or row.get("pos_customer")
		or row.get("delivery_customer")
		or row.get("purchase_receipt_supplier")
		or row.get("purchase_invoice_supplier")
		or row.get("stock_entry_supplier")
	)


def get_responsible_user(row):
	return (
		row.get("pos_owner")
		or row.get("sales_owner")
		or row.get("delivery_owner")
		or row.get("purchase_receipt_owner")
		or row.get("purchase_invoice_owner")
		or row.get("stock_entry_owner")
		or row.get("entry_owner")
	)


def is_damage_movement(row):
	text = " ".join(
		str(row.get(field) or "")
		for field in ("movement_type", "stock_entry_type", "stock_entry_purpose")
	).lower()
	return any(keyword in text for keyword in DAMAGE_KEYWORDS)


def is_expiry_movement(row):
	text = " ".join(
		str(row.get(field) or "")
		for field in ("movement_type", "stock_entry_type", "stock_entry_purpose")
	).lower()
	return any(keyword in text for keyword in EXPIRY_KEYWORDS)


def get_movement_type_options():
	return [
		"",
		_("Sale"),
		_("Return"),
		_("Purchase"),
		_("Purchase Return"),
		_("Adjustment"),
		_("Transfer"),
	]
