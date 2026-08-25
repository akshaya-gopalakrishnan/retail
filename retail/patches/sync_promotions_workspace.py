import json
from pathlib import Path

import frappe


DOCS = (
	("workspace", "promotions", "Workspace", "Promotions"),
	("print_format", "promo_price_sheet", "Print Format", "Promo Price Sheet"),
	("print_format", "buy_x_get_y_promotion_sheet", "Print Format", "Buy X Get Y Promotion Sheet"),
	("print_format", "gift_voucher_promotion_sheet", "Print Format", "Gift Voucher Promotion Sheet"),
	("print_format", "gift_voucher_ledger_sheet", "Print Format", "Gift Voucher Ledger Sheet"),
	("print_format", "sales_order___retail", "Print Format", "Sales Order - Retail"),
	("print_format", "supplier_quotation___retail", "Print Format", "Supplier Quotation - Retail"),
	("print_format", "purchase_order___retail", "Print Format", "Purchase Order - Retail"),
	("print_format", "purchase_receipt___retail", "Print Format", "Purchase Receipt - Retail"),
	("print_format", "purchase_invoice___retail", "Print Format", "Purchase Invoice - Retail"),
	("print_format", "material_request___retail", "Print Format", "Material Request - Retail"),
	("dashboard_chart", "promo_price_status", "Dashboard Chart", "Promo Price Status"),
	("dashboard_chart", "gift_voucher_promotion_status", "Dashboard Chart", "Gift Voucher Promotion Status"),
	("dashboard_chart", "gift_voucher_ledger_status", "Dashboard Chart", "Gift Voucher Ledger Status"),
)


def execute():
	base_path = Path(__file__).resolve().parents[1] / "retail_app"
	for folder, doc_folder, doctype, name in DOCS:
		path = base_path / folder / doc_folder / f"{doc_folder}.json"
		data = json.loads(path.read_text())
		for fieldname in ("creation", "modified", "modified_by", "owner"):
			data.pop(fieldname, None)
		if doctype == "Dashboard Chart" and not frappe.db.exists("DocType", data.get("document_type")):
			continue
		existing_name = frappe.db.exists(doctype, name)
		doc = frappe.get_doc(doctype, existing_name) if existing_name else frappe.new_doc(doctype)
		doc.update(data)
		doc.flags.ignore_permissions = True
		doc.flags.ignore_links = True
		doc.save()

	frappe.clear_cache()
