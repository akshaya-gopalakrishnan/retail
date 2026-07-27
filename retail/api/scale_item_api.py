import frappe

from retail.domains.item.scale_barcode_parser import parse_scale_barcode
from retail.domains.item.scale_export_service import export_scale_items


@frappe.whitelist()
def parse_barcode(barcode, price_list=None, currency=None):
	result = parse_scale_barcode(barcode, price_list=price_list, currency=currency)
	return result.__dict__ if result else None


@frappe.whitelist()
def export_scale_items_file(template=None, price_list=None):
	content = export_scale_items(template=template, price_list=price_list)
	frappe.local.response.filename = "weighing.txt"
	frappe.local.response.filecontent = content
	frappe.local.response.type = "download"
