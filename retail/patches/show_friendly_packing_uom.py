"""Show the selected packing unit without exposing the internal ERPNext UOM."""

from decimal import Decimal

import frappe

from retail.grid_view_settings import _get_user_settings, _save_user_settings


def execute():
	frappe.reload_doc("retail_app", "doctype", "retail_packing_detail")
	# Recover display values for rows saved before the friendly field was installed.
	# Do not save Items or touch conversions, barcodes, rates, or Item Prices.
	for row in frappe.get_all("Retail Packing Detail",
		fields=["name", "uom", "packing_uom", "conversion_factor"]):
		if row.packing_uom or not row.uom:
			continue
		factor = format(Decimal(str(row.conversion_factor or 0)), "f")
		if "." in factor:
			factor = factor.rstrip("0").rstrip(".")
		suffix = "-" + factor
		friendly = row.uom[:-len(suffix)] if row.uom.endswith(suffix) else row.uom
		frappe.db.set_value("Retail Packing Detail", row.name, "packing_uom",
			friendly, update_modified=False)

	for user in frappe.get_all("User", pluck="name"):
		settings = _get_user_settings(user, "Item")
		columns = (settings.get("GridView") or {}).get("Retail Packing Detail") or []
		changed = False
		for column in columns:
			if column.get("fieldname") == "uom":
				column["fieldname"] = "packing_uom"
				changed = True
		if changed:
			seen = set()
			settings["GridView"]["Retail Packing Detail"] = [
				column for column in columns
				if column["fieldname"] not in seen and not seen.add(column["fieldname"])
			]
			_save_user_settings(user, "Item", settings)
	frappe.clear_cache(doctype="Retail Packing Detail")
	frappe.clear_cache(doctype="Item")
