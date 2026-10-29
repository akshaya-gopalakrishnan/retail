"""Add product identification to existing POS download rows in place."""
import frappe
from frappe.utils import cint


def with_item_identity(payload, warehouse):
	from retail.pos_serials import apply_master_serials

	rows = []
	def collect(value):
		if isinstance(value, dict):
			code = value.get("item_code") or value.get("item")
			if isinstance(code, str) and code:
				rows.append((value, code))
			elif "item" in value or "item_code" in value:
				rows.append((value, ""))
			for child in value.values():
				collect(child)
		elif isinstance(value, (list, tuple)):
			for child in value:
				collect(child)
	collect(payload)
	codes = sorted({code for _, code in rows if code})
	items = frappe.get_all("Item", filters={"name": ["in", codes]},
		fields=["name as item_code", "item_name", "custom_barcode as barcode", "has_serial_no", "disabled"],
		limit_page_length=0) if codes else []
	apply_master_serials(items, warehouse)
	by_code = {item.item_code: item for item in items}
	for row, code in rows:
		item = by_code.get(code, {})
		row["barcode"] = row.get("barcode") or item.get("barcode") or ""
		row.setdefault("item_name", item.get("item_name") or "")
		row["has_serial_no"] = cint(item.get("has_serial_no"))
		# Transaction serial_no is an actual selection; never overwrite it with availability.
		row.setdefault("serial_no", "")
		row["serial_numbers"] = list(item.get("serial_numbers", []))
	return payload
