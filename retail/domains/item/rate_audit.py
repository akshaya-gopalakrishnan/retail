from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, now

from retail.domains.item.vat_pricing import get_item_tax_rate


PRICE_MANAGER_ROLE = "Retail Price Manager"
PURCHASE_DOCTYPES = {"Purchase Receipt", "Purchase Invoice"}
PURCHASE_ITEM_DOCTYPES = {
	"Purchase Receipt": "Purchase Receipt Item",
	"Purchase Invoice": "Purchase Invoice Item",
}


def ensure_rate_audit_setup():
	"""Create the role used to guard Item Master rate changes."""
	if not frappe.db.exists("Role", PRICE_MANAGER_ROLE):
		role = frappe.new_doc("Role")
		role.role_name = PRICE_MANAGER_ROLE
		role.desk_access = 1
		role.insert(ignore_permissions=True)


def audit_item_master_rate_change(doc, method=None):
	"""Audit direct Item form rate edits, including packing-row reverse updates."""
	if frappe.flags.in_install or frappe.flags.retail_rate_audit_in_progress:
		return
	before = doc.get_doc_before_save()
	if not before:
		return

	for direction in ("Purchase", "Selling"):
		old = _get_item_rate_state(before, direction)
		new = _get_item_rate_state(doc, direction)
		if abs(old["net"] - new["net"]) < 0.0001 and abs(old["gross"] - new["gross"]) < 0.0001:
			continue
		_insert_audit_log(
			item=doc.name,
			action="Update",
			direction=direction,
			old=old,
			new=new,
			vat_basis="Including VAT" if _item_direction_includes_vat(doc, direction) else "Excluding VAT",
			vat_rate=_get_item_direction_vat_rate(doc, direction),
			source_doctype="Item",
			source_name=doc.name,
			uom=doc.stock_uom,
			conversion_factor=1,
			remarks=_("Direct Item Master rate edit"),
		)


@frappe.whitelist()
def user_can_manage_item_rates():
	return _has_price_manager_role()


@frappe.whitelist()
def get_purchase_document_rate_preview(source_doctype, source_name):
	if source_doctype not in PURCHASE_DOCTYPES:
		frappe.throw(_("Unsupported source document."))

	doc = frappe.get_doc(source_doctype, source_name)
	if doc.docstatus != 1:
		frappe.throw(_("Submit the document before updating Item Master rates."))

	rows = []
	for row in doc.get("items") or []:
		if not row.get("item_code"):
			continue
		preview = _build_rate_preview(
			item_code=row.item_code,
			direction="Purchase",
			new_net_rate=_get_row_net_rate(row),
			new_gross_rate=_get_row_gross_rate(row),
			source_doctype=source_doctype,
			source_name=source_name,
			source_row=row.name,
			supplier=doc.get("supplier"),
			uom=row.get("uom"),
			conversion_factor=_get_row_conversion_factor(row),
			vat_basis=_get_row_vat_basis(row),
		)
		if preview and preview["changed"]:
			rows.append(preview)
	return rows


@frappe.whitelist()
def apply_purchase_document_rate_updates(source_doctype, source_name, source_rows=None):
	_require_price_manager()
	if isinstance(source_rows, str):
		source_rows = frappe.parse_json(source_rows or "[]")
	source_rows = set(source_rows or [])
	previews = get_purchase_document_rate_preview(source_doctype, source_name)
	if source_rows:
		previews = [row for row in previews if row.get("source_row") in source_rows]
	if not previews:
		return []

	return [_apply_item_rate_update(**_preview_to_apply_args(row)) for row in previews]


@frappe.whitelist()
def get_item_price_rate_preview(item_price):
	price = frappe.get_doc("Item Price", item_price)
	if price.price_list not in ("Standard Buying", "Standard Selling"):
		frappe.throw(_("Only Standard Buying and Standard Selling can update Item Master."))

	direction = "Purchase" if price.price_list == "Standard Buying" else "Selling"
	item = frappe.get_cached_doc("Item", price.item_code)
	conversion_factor = 1
	if price.uom and price.uom != item.stock_uom:
		conversion_factor = flt(
			frappe.db.get_value("UOM Conversion Detail", {"parent": item.name, "uom": price.uom}, "conversion_factor")
		)
	if conversion_factor <= 0:
		frappe.throw(_("Missing conversion factor for {0}.").format(price.uom or item.stock_uom))

	net_rate = flt(price.price_list_rate) / conversion_factor
	return _build_rate_preview(
		item_code=price.item_code,
		direction=direction,
		new_net_rate=net_rate,
		source_doctype="Item Price",
		source_name=price.name,
		source_row="",
		uom=price.uom or item.stock_uom,
		conversion_factor=conversion_factor,
		vat_basis="Excluding VAT",
	)


@frappe.whitelist()
def apply_item_price_rate_update(item_price):
	_require_price_manager()
	preview = get_item_price_rate_preview(item_price)
	if not preview or not preview.get("changed"):
		return None
	return _apply_item_rate_update(**_preview_to_apply_args(preview))


@frappe.whitelist()
def apply_manual_item_rate_update(item_code, direction, new_net_rate, source_doctype="Item", source_name=None, remarks=None):
	_require_price_manager()
	preview = _build_rate_preview(
		item_code=item_code,
		direction=direction,
		new_net_rate=flt(new_net_rate),
		source_doctype=source_doctype,
		source_name=source_name or item_code,
		vat_basis="Excluding VAT",
		remarks=remarks,
	)
	if not preview or not preview.get("changed"):
		return None
	return _apply_item_rate_update(**_preview_to_apply_args(preview))


@frappe.whitelist()
def reverse_rate_audit(audit_name):
	_require_price_manager()
	audit = frappe.get_doc("Retail Item Rate Audit", audit_name)
	if audit.status == "Reversed":
		frappe.throw(_("This audit entry is already reversed."))
	if audit.action != "Update":
		frappe.throw(_("Only update entries can be reversed."))

	reversal = _apply_item_rate_update(
		item_code=audit.item,
		direction=audit.direction,
		new_net_rate=flt(audit.old_net_rate),
		new_gross_rate=flt(audit.old_gross_rate),
		vat_rate=flt(audit.vat_rate),
		vat_basis=audit.vat_basis,
		source_doctype="Retail Item Rate Audit",
		source_name=audit.name,
		source_row="",
		supplier=audit.supplier,
		uom=audit.uom,
		conversion_factor=flt(audit.conversion_factor) or 1,
		action="Reverse",
		reversed_audit=audit.name,
		remarks=_("Reversed audit {0}").format(audit.name),
	)
	audit.db_set("status", "Reversed", update_modified=False)
	return reversal


def _apply_item_rate_update(
	item_code,
	direction,
	new_net_rate,
	new_gross_rate=None,
	vat_rate=None,
	vat_basis="Excluding VAT",
	source_doctype=None,
	source_name=None,
	source_row=None,
	supplier=None,
	uom=None,
	conversion_factor=1,
	action="Update",
	reversed_audit=None,
	remarks=None,
):
	item = frappe.get_doc("Item", item_code)
	_validate_item_write(item)
	old = _get_item_rate_state(item, direction)
	vat_rate = flt(vat_rate if vat_rate is not None else _get_item_direction_vat_rate(item, direction))
	new = _make_rate_state(new_net_rate, vat_rate, new_gross_rate)

	values = _get_item_update_values(direction, new)
	try:
		frappe.flags.retail_rate_audit_in_progress = True
		frappe.db.set_value("Item", item.name, values, update_modified=True)
	finally:
		frappe.flags.retail_rate_audit_in_progress = False

	audit = _insert_audit_log(
		item=item.name,
		action=action,
		direction=direction,
		old=old,
		new=new,
		vat_basis=vat_basis,
		vat_rate=vat_rate,
		source_doctype=source_doctype,
		source_name=source_name,
		source_row=source_row,
		supplier=supplier,
		uom=uom or item.stock_uom,
		conversion_factor=flt(conversion_factor) or 1,
		reversed_audit=reversed_audit,
		remarks=remarks,
	)

	from retail.domains.item.average_purchase_rate import sync_item_average_purchase_rate
	from retail.domains.item.item_price_sync import sync_item_master_margin

	if direction == "Purchase":
		sync_item_average_purchase_rate(item.name, fallback_rate=new["net"])
	sync_item_master_margin(item.name)
	return audit.name


def _insert_audit_log(
	item,
	action,
	direction,
	old,
	new,
	vat_basis,
	vat_rate,
	source_doctype=None,
	source_name=None,
	source_row=None,
	supplier=None,
	uom=None,
	conversion_factor=1,
	reversed_audit=None,
	remarks=None,
):
	return frappe.get_doc(
		{
			"doctype": "Retail Item Rate Audit",
			"item": item,
			"action": action,
			"direction": direction,
			"status": "Applied",
			"old_net_rate": old["net"],
			"new_net_rate": new["net"],
			"old_vat_amount": old["vat"],
			"new_vat_amount": new["vat"],
			"old_gross_rate": old["gross"],
			"new_gross_rate": new["gross"],
			"vat_basis": vat_basis,
			"vat_rate": vat_rate,
			"uom": uom,
			"conversion_factor": conversion_factor,
			"source_doctype": source_doctype,
			"source_name": source_name,
			"source_row": source_row,
			"supplier": supplier,
			"updated_by": frappe.session.user,
			"updated_on": now(),
			"reversed_audit": reversed_audit,
			"remarks": remarks,
		}
	).insert(ignore_permissions=True)


def _build_rate_preview(
	item_code,
	direction,
	new_net_rate,
	new_gross_rate=None,
	source_doctype=None,
	source_name=None,
	source_row=None,
	supplier=None,
	uom=None,
	conversion_factor=1,
	vat_basis="Excluding VAT",
	remarks=None,
):
	new_net_rate = flt(new_net_rate)
	if new_net_rate <= 0:
		return None

	item = frappe.get_cached_doc("Item", item_code)
	vat_rate = _get_item_direction_vat_rate(item, direction)
	old = _get_item_rate_state(item, direction)
	new = _make_rate_state(new_net_rate, vat_rate, new_gross_rate)
	return {
		"item_code": item.name,
		"item_name": item.item_name,
		"direction": direction,
		"old_net_rate": old["net"],
		"new_net_rate": new["net"],
		"old_gross_rate": old["gross"],
		"new_gross_rate": new["gross"],
		"old_vat_amount": old["vat"],
		"new_vat_amount": new["vat"],
		"vat_rate": vat_rate,
		"vat_basis": vat_basis,
		"source_doctype": source_doctype,
		"source_name": source_name,
		"source_row": source_row,
		"supplier": supplier,
		"uom": uom or item.stock_uom,
		"conversion_factor": flt(conversion_factor) or 1,
		"remarks": remarks,
		"changed": abs(old["net"] - new["net"]) >= 0.0001,
	}


def _preview_to_apply_args(row):
	return {
		"item_code": row["item_code"],
		"direction": row["direction"],
		"new_net_rate": row["new_net_rate"],
		"new_gross_rate": row["new_gross_rate"],
		"vat_rate": row["vat_rate"],
		"vat_basis": row["vat_basis"],
		"source_doctype": row["source_doctype"],
		"source_name": row["source_name"],
		"source_row": row.get("source_row"),
		"supplier": row.get("supplier"),
		"uom": row.get("uom"),
		"conversion_factor": row.get("conversion_factor") or 1,
		"remarks": row.get("remarks"),
	}


def _get_item_rate_state(item, direction):
	if direction == "Purchase":
		net = flt(item.get("custom_purchase_net_rate") or item.get("custom_default_purchase_rate") or item.get("last_purchase_rate"))
		gross = flt(item.get("custom_purchase_gross_rate"))
		vat = flt(item.get("custom_purchase_vat_amount"))
	else:
		net = flt(item.get("custom_sales_net_rate") or item.get("standard_rate"))
		gross = flt(item.get("custom_sales_gross_rate"))
		vat = flt(item.get("custom_sales_vat_amount"))

	if not gross:
		vat_rate = _get_item_direction_vat_rate(item, direction)
		vat = net * vat_rate / 100
		gross = net + vat
	return {"net": flt(net, 2), "vat": flt(vat, 2), "gross": flt(gross, 2)}


def _make_rate_state(net_rate, vat_rate, gross_rate=None):
	net = flt(net_rate, 2)
	if gross_rate is not None and flt(gross_rate) > 0:
		gross = flt(gross_rate, 2)
		vat = max(gross - net, 0)
	else:
		vat = net * flt(vat_rate) / 100
		gross = net + vat
	return {"net": flt(net, 2), "vat": flt(vat, 2), "gross": flt(gross, 2)}


def _get_item_update_values(direction, state):
	if direction == "Purchase":
		values = {
			"last_purchase_rate": state["net"],
			"custom_default_purchase_rate": state["net"],
			"custom_purchase_rate_entry": state["gross"],
			"custom_purchase_rate_includes_vat": 1,
			"custom_purchase_net_rate": state["net"],
			"custom_purchase_vat_amount": state["vat"],
			"custom_purchase_gross_rate": state["gross"],
		}
	else:
		values = {
			"standard_rate": state["net"],
			"custom_sales_rate_entry": state["gross"],
			"custom_sales_rate_includes_vat": 1,
			"custom_sales_net_rate": state["net"],
			"custom_sales_vat_amount": state["vat"],
			"custom_sales_gross_rate": state["gross"],
		}
	return {field: value for field, value in values.items() if frappe.db.has_column("Item", field)}


def _get_item_direction_vat_rate(item, direction):
	template = item.get("custom_purchase_tax_template") if direction == "Purchase" else item.get("custom_tax")
	return flt(get_item_tax_rate(template)) if template else 0


def _item_direction_includes_vat(item, direction):
	fieldname = "custom_purchase_rate_includes_vat" if direction == "Purchase" else "custom_sales_rate_includes_vat"
	return bool(flt(item.get(fieldname)))


def _get_row_net_rate(row):
	conversion_factor = _get_row_conversion_factor(row)
	rate = flt(row.get("net_rate") or row.get("base_net_rate") or row.get("rate"))
	return rate / conversion_factor if conversion_factor else rate


def _get_row_gross_rate(row):
	conversion_factor = _get_row_conversion_factor(row)
	gross = flt(row.get("custom_rate_including_vat") or row.get("rate") or row.get("net_rate"))
	return gross / conversion_factor if conversion_factor else gross


def _get_row_conversion_factor(row):
	if flt(row.get("conversion_factor")):
		return flt(row.get("conversion_factor"))
	if flt(row.get("qty")):
		return flt(row.get("stock_qty")) / flt(row.get("qty"))
	return 1


def _get_row_vat_basis(row):
	if flt(row.get("custom_rate_including_vat")) and flt(row.get("custom_rate_including_vat")) == flt(row.get("rate")):
		return "Including VAT"
	return "Excluding VAT"


def _require_price_manager():
	if not _has_price_manager_role():
		frappe.throw(_("Only users with the {0} role can update Item Master rates.").format(PRICE_MANAGER_ROLE))


def _has_price_manager_role():
	return PRICE_MANAGER_ROLE in frappe.get_roles(frappe.session.user) or "System Manager" in frappe.get_roles(frappe.session.user)


def _validate_item_write(item):
	if not frappe.has_permission("Item", "write", item):
		frappe.throw(_("You do not have write permission for Item {0}.").format(item.name))
