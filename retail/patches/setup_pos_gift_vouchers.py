"""Install only the voucher integration schema; preserve existing retail setup."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	# Fail explicitly before schema changes if old data needs reconciliation.
	duplicates = frappe.db.sql("""select external_pos_reference, count(*) as n
		from `tabPOS Invoice` where coalesce(external_pos_reference, '') != ''
		group by external_pos_reference having count(*) > 1 limit 10""", as_dict=True)
	if duplicates:
		frappe.throw("Duplicate POS references require reconciliation before voucher setup: " + frappe.as_json(duplicates))
	for doctype in ("gift_voucher_ledger", "pos_sync_log"):
		frappe.reload_doc("retail_app", "doctype", doctype, force=True)
	create_custom_fields({"POS Invoice": [{
		"fieldname": "custom_pos_completed_payload", "label": "Completed POS Payload",
		"fieldtype": "Code", "options": "JSON", "read_only": 1, "hidden": 1, "no_copy": 1,
		"insert_after": "external_pos_reference",
	}]}, update=True)
	from retail.promotions.gift_voucher import ensure_gift_voucher_invoice_fields
	ensure_gift_voucher_invoice_fields()
	frappe.db.sql("update `tabPOS Invoice` set external_pos_reference = NULL where external_pos_reference = ''")
	frappe.db.set_value("Custom Field", "POS Invoice-external_pos_reference", {"unique": 1, "allow_on_submit": 0})
	frappe.db.add_unique("POS Invoice", ["external_pos_reference"], "unique_external_pos_reference")
	_backfill_redemption_receipts()
	frappe.clear_cache()


def _backfill_redemption_receipts():
	"""Allow cancellation of pre-upgrade invoices without touching balances."""
	from retail import pos_operations
	for doctype in ("Sales Invoice", "POS Invoice"):
		filters = {"docstatus": 1, "custom_gift_voucher_amount": [">", 0], "is_return": 0}
		if doctype == "Sales Invoice":
			filters["is_consolidated"] = 0
		for row in frappe.get_all(doctype, filters=filters,
			fields=["name", "company", "custom_gift_voucher_code", "custom_gift_voucher_amount",
				"custom_gift_voucher_redemption_reference"]):
			code = row.custom_gift_voucher_code
			if not code or not frappe.db.exists("Gift Voucher Ledger", code):
				continue
			reference = row.custom_gift_voucher_redemption_reference or f"ERP:{doctype}:{row.name}"
			if pos_operations.find("Voucher Redemption", reference):
				continue
			request = {"voucher_code": code, "amount": row.custom_gift_voucher_amount,
				"company": row.company, "invoice_type": doctype, "invoice": row.name}
			pos_operations.execute("Voucher Redemption", reference, request, lambda: {
				"status": "Success", "approved": True, "legacy_receipt": True,
				"voucher_code": code, "amount": row.custom_gift_voucher_amount,
				"balance_after": None}, code)
			receipt = pos_operations.find("Voucher Redemption", reference)
			frappe.db.set_value("POS Sync Log", receipt.name,
				{"linked_invoice": row.name, "linked_invoice_type": doctype}, update_modified=False)
