import frappe

from retail.retail_app.doctype.retail_packing_detail.retail_packing_detail import (
	is_auto_packing_name,
	make_packing_name,
)


def execute():
	if not frappe.db.exists("DocType", "Retail Packing Detail"):
		return
	if not frappe.db.has_column("Retail Packing Detail", "packing_name"):
		return

	rows = frappe.db.sql(
		"""
		select
			packing.name,
				packing.parent,
				packing.packing_name,
				packing.uom,
			packing.conversion_factor,
			item.item_name
		from `tabRetail Packing Detail` packing
		left join `tabItem` item on item.name = packing.parent
		""",
		as_dict=True,
	)
	for row in rows:
		if row.packing_name and not is_auto_packing_name(row.packing_name, row.item_name or row.parent, row.uom):
			continue
		frappe.db.set_value(
			"Retail Packing Detail",
			row.name,
			"packing_name",
			make_packing_name(row.item_name or row.parent, row.uom, row.conversion_factor),
			update_modified=False,
		)
