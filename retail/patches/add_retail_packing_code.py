import frappe

from retail.retail_app.doctype.retail_packing_detail.retail_packing_detail import make_packing_code


def execute():
	if not frappe.db.exists("DocType", "Retail Packing Detail"):
		return
	if not frappe.db.has_column("Retail Packing Detail", "packing_code"):
		return

	rows = frappe.get_all(
		"Retail Packing Detail",
		filters={"packing_code": ["in", ("", None)]},
		fields=["name", "parent", "uom", "idx"],
		limit_page_length=0,
	)
	for row in rows:
		frappe.db.set_value(
			"Retail Packing Detail",
			row.name,
			"packing_code",
			make_packing_code(row.parent, row.uom, row.idx),
			update_modified=False,
		)
