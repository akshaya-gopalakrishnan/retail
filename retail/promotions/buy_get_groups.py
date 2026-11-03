"""Grouped Buy/Get rows on the existing promotion and POS products array."""
from collections import defaultdict
import math

import frappe
from frappe import _
from frappe.utils import cint, flt


def row_values(promotion, row):
	quantity = row.get("qty")
	if quantity is None or quantity == "":
		quantity = promotion.get("buy_qty" if row.get("add_to") == "Buy Item" else "free_qty")
	return {"group_no": cint(row.get("group_no") or 1), "qty": flt(quantity)}


def group_rows(promotion):
	groups = defaultdict(lambda: {"buy": [], "get": []})
	for row in promotion.get("products") or []:
		values = row_values(promotion, row)
		row.group_no = values["group_no"]
		row.qty = values["qty"]
		groups[row.group_no]["buy" if row.add_to == "Buy Item" else "get"].append(row)
	return dict(groups)


def validate_groups(promotion):
	for row in promotion.products:
		group = row.get("group_no")
		if group not in (None, "") and (not math.isfinite(flt(group)) or flt(group) != cint(group) or cint(group) <= 0):
			frappe.throw(_("Row #{0}: Group No must be a positive whole number.").format(row.idx))
		quantity = row_values(promotion, row)["qty"]
		if not math.isfinite(quantity) or quantity <= 0:
			frappe.throw(_("Row #{0}: Qty must be greater than zero.").format(row.idx))
	groups = group_rows(promotion)
	for number, rows in groups.items():
		if not rows["buy"]:
			frappe.throw(_("Group {0}: Add at least one Buy Item.").format(number))
		if not promotion.same_product_only and not rows["get"]:
			frappe.throw(_("Group {0}: Add at least one Free Item.").format(number))
		for side in ("buy", "get"):
			seen = set()
			for row in rows[side]:
				key = row.item or row.item_group or row.get("brand")
				if key in seen:
					frappe.throw(_("Group {0}: Combine duplicate {1} rows for {2} into one quantity.").format(number, side, key))
				seen.add(key)
	return groups
