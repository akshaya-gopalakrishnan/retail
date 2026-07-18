import frappe

from retail.retail_app.report.item_family_list.item_family_list import get_data


@frappe.whitelist()
def get_rows(filters=None):
	filters = frappe._dict(frappe.parse_json(filters) or {})
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

	return list(families.values())
