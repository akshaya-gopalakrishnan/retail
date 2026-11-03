import frappe

from frappe.utils import cint

from retail.retail_app.report.item_family_list.item_family_list import get_conditions, get_data


@frappe.whitelist()
def get_rows(filters=None, start=0, page_length=None):
	frappe.has_permission("Item", "read", throw=True)
	filters = frappe._dict(frappe.parse_json(filters) or {})
	paginated = page_length is not None
	if paginated:
		start = max(0, cint(start))
		page_length = min(100, max(1, cint(page_length) or 50))
		conditions, values = get_conditions(filters)
		values.update(start=start, limit=page_length + 1)
		# Page by parent Item, so a family's packing rows are never split.
		items = frappe.db.sql(
			f"""select distinct item.name, item.item_name
			from `tabItem` item
			left join `tabRetail Packing Detail` packing on item.name = packing.parent
				and packing.parenttype = 'Item'
				and packing.parentfield = 'custom_retail_packing_detail'
			where item.name is not null {conditions}
			order by item.item_name, item.name
			limit %(limit)s offset %(start)s""",
			values, as_dict=True,
		)
		has_more = len(items) > page_length
		rows = get_data(filters, item_codes=[item.name for item in items[:page_length]])
	else:
		# Retain the existing list response for callers that do not request paging.
		rows = get_data(filters)
	families = {}

	for row in rows:
		family = families.setdefault(
			row.item_code,
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"item_group": row.item_group,
				"brand": row.brand,
				"disabled": row.disabled,
				"stock_uom": row.stock_uom,
				"item_barcode": row.get("item_barcode"),
				"purchase_net_rate": row.get("item_purchase_net_rate"),
				"purchase_vat_amount": row.get("item_purchase_vat_amount"),
				"purchase_gross_rate": row.get("item_purchase_gross_rate"),
				"selling_net_rate": row.get("item_selling_net_rate"),
				"selling_vat_amount": row.get("item_selling_vat_amount"),
				"selling_gross_rate": row.get("item_selling_gross_rate"),
				"packing_margin": row.get("item_margin"),
				"real_stock_qty": row.get("real_stock_qty"),
				"in_qty": row.get("in_qty"),
				"out_qty": row.get("out_qty"),
				"packings": [],
			},
		)
		if row.get("idx") or row.get("barcode") or row.get("uom"):
			family["packings"].append(row)

	result = list(families.values())
	if paginated:
		return {"families": result, "has_more": has_more, "start": start}
	return result
