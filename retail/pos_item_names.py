"""Display identity for items sold by the external offline POS."""
import frappe
from frappe.utils import flt
from retail.retail_app.doctype.retail_packing_detail.retail_packing_detail import make_packing_name


def resolve_item_name(item, row):
	barcode = str(row.get("barcode") or "").strip()
	if barcode:
		packings = [packing for packing in item.get("custom_retail_packing_detail") or []
			if str(packing.get("barcode") or "").strip() == barcode]
		if len(packings) == 1 and packings[0].get("packing_name"):
			return packings[0].packing_name
		# Never guess another packing when a supplied barcode cannot be resolved.
		return row.get("item_name") or item.item_name
	uom = row.get("uom")
	factor = flt(row.get("conversion_factor"))
	if uom and factor > 0 and (uom != item.stock_uom or factor != 1):
		return make_packing_name(item.item_name, uom, factor)
	return item.item_name


def restore_item_names(doc, payload):
	for line, row in zip(doc.items, payload.get("items") or []):
		item = frappe.get_cached_doc("Item", line.item_code)
		line.item_name = resolve_item_name(item, row)
		line.barcode = row.get("barcode")
