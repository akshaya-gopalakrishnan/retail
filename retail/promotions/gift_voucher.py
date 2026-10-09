import math

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import add_days, flt, getdate, nowdate


SALES_DOCTYPES = {"Sales Invoice", "POS Invoice"}


def ensure_gift_voucher_invoice_fields():
	fields = [
		{
			"fieldname": "custom_gift_voucher_code",
			"label": "Gift Voucher Code",
			"fieldtype": "Link",
			"options": "Gift Voucher Ledger",
			"insert_after": "discount_amount",
			"allow_on_submit": 0,
		},
		{
			"fieldname": "custom_gift_voucher_amount",
			"label": "Gift Voucher Amount",
			"fieldtype": "Currency",
			"insert_after": "custom_gift_voucher_code",
			"read_only": 1,
			"allow_on_submit": 0,
		},
		{
			"fieldname": "custom_gift_voucher_discount_applied",
			"label": "Gift Voucher Discount Applied",
			"fieldtype": "Currency",
			"insert_after": "custom_gift_voucher_amount",
			"hidden": 1,
			"read_only": 1,
			"allow_on_submit": 0,
		},
	]
	fields.append({"fieldname": "custom_gift_voucher_redemption_reference", "label": "Gift Voucher Redemption Reference",
		"fieldtype": "Data", "read_only": 1, "no_copy": 1, "insert_after": "custom_gift_voucher_amount"})
	create_custom_fields({doctype: fields for doctype in SALES_DOCTYPES}, ignore_validate=True, update=True)


def apply_gift_voucher_redemption(doc, method=None):
	if doc.doctype not in SALES_DOCTYPES or doc.get("is_consolidated"):
		return
	validate_return_safety(doc)
	if doc.get("is_return"):
		return
	if doc.get("pos_sync_source") == "Offline POS":
		from retail.api.gift_vouchers import bind_pos_redemption
		from retail.pos_completed_sale import audit_effect
		audit_effect(doc, "Voucher redemption reconciliation", lambda: bind_pos_redemption(doc))
		return
	# Retail invoice controllers calculate the discount before core validates
	# payment amounts, not after the core validate method has already returned.


def calculate_invoice_totals(doc, calculate):
	if doc.get("is_return") or doc.get("is_consolidated"):
		return calculate()
	code = doc.get("custom_gift_voucher_code")
	previous = flt(doc.get("custom_gift_voucher_discount_applied"))
	# Always remove the previous voucher discount before calculating a fresh base.
	doc.discount_amount = flt(doc.get("discount_amount")) - previous
	doc.custom_gift_voucher_amount = doc.custom_gift_voucher_discount_applied = 0
	if not code and not previous:
		return calculate()
	calculate()
	if code:
		voucher = validate_redeemable_voucher(code, doc)
		amount = min(flt(voucher.balance_amount), max(0, flt(doc.grand_total)))
		doc.discount_amount += amount
		doc.custom_gift_voucher_amount = doc.custom_gift_voucher_discount_applied = amount
		calculate()


def mark_gift_voucher_redeemed(doc, method=None):
	if doc.doctype not in SALES_DOCTYPES or doc.get("is_consolidated"):
		return
	if doc.get("is_return"):
		handle_returned_issued_vouchers(doc)
		return
	from retail.api.gift_vouchers import bind_pos_redemption, debit, invoice_redemption_reference
	from retail import pos_operations
	if doc.get("pos_sync_source") == "Offline POS":
		from retail.pos_completed_sale import audit_effect
		audit_effect(doc, "Voucher redemption reconciliation", lambda: bind_pos_redemption(doc))
		return
	code, amount = doc.get("custom_gift_voucher_code"), flt(doc.get("custom_gift_voucher_amount"))
	if not code or amount <= 0:
		return
	reference = invoice_redemption_reference(doc)
	request = {"voucher_code": code, "amount": amount, "company": doc.company,
		"invoice_type": doc.doctype, "invoice": doc.name}
	pos_operations.execute("Voucher Redemption", reference, request,
		lambda: debit(code, amount, doc.company, doc.currency), code)
	receipt = pos_operations.find("Voucher Redemption", reference)
	frappe.db.set_value("POS Sync Log", receipt.name,
		{"linked_invoice": doc.name, "linked_invoice_type": doc.doctype}, update_modified=False)
	frappe.db.set_value("Gift Voucher Ledger", code,
		{"redeemed_against_type": doc.doctype, "redeemed_against": doc.name})


def restore_redeemed_gift_voucher(doc, method=None):
	if doc.doctype not in SALES_DOCTYPES or doc.get("is_return") or doc.get("is_consolidated"):
		return
	if not doc.get("custom_gift_voucher_code") or flt(doc.get("custom_gift_voucher_amount")) <= 0:
		return
	from retail.api.gift_vouchers import invoice_redemption_reference, reverse
	reference = invoice_redemption_reference(doc)
	reverse(reference, reference, company=doc.company, invoice=doc.name)


def validate_redeemable_voucher(code, doc):
	from retail.api.gift_vouchers import read_voucher, invalid_reason
	# Submission rechecks the chosen amount under debit()'s row lock.
	voucher = read_voucher(code, doc.company)
	reason = invalid_reason(voucher)
	if reason:
		frappe.throw(_("Gift Voucher {0} cannot be redeemed: {1}.").format(code, reason))
	currency = voucher.get("currency") or frappe.get_cached_value("Company", doc.company, "default_currency")
	if doc.get("currency") and doc.currency != currency:
		frappe.throw("Voucher currency does not match invoice currency.")
	return voucher


def validate_return_safety(doc, method=None):
	if doc.doctype not in SALES_DOCTYPES or not doc.get("is_return") or not doc.get("return_against"):
		return

	issued_vouchers = frappe.get_all(
		"Gift Voucher Ledger",
		filters={"issued_against_type": doc.doctype, "issued_against": doc.return_against},
		fields=["name", "status", "voucher_amount", "balance_amount"],
	)
	for row in sorted(issued_vouchers, key=lambda row: row.name):
		voucher = frappe.get_doc("Gift Voucher Ledger", row.name, for_update=True)
		if voucher.status in ("Redeemed", "Partially Used") or flt(voucher.balance_amount) < flt(voucher.voucher_amount):
			frappe.throw(
				_(
					"Return is blocked because Gift Voucher {0} from the original invoice is already used. Manager must adjust the refund manually."
				).format(voucher.name)
			)


def handle_returned_issued_vouchers(doc):
	if doc.doctype not in SALES_DOCTYPES or not doc.get("is_return") or not doc.get("return_against"):
		return
	_cancel_vouchers(doc.doctype, doc.return_against, f"Cancelled by return {doc.name}")


def _cancel_vouchers(doctype, name, reason):
	for code in frappe.get_all("Gift Voucher Ledger", filters={"issued_against_type": doctype,
		"issued_against": name}, pluck="name", order_by="name"):
		voucher = frappe.get_doc("Gift Voucher Ledger", code, for_update=True)
		if voucher.status == "Cancelled":
			continue
		if flt(voucher.balance_amount) != flt(voucher.voucher_amount):
			frappe.throw(f"Voucher {code} has been spent. Reverse its redemptions before cancelling the issuing sale.")
		frappe.db.set_value("Gift Voucher Ledger", code,
			{"status": "Cancelled", "balance_amount": 0, "notes": reason})


def issue_gift_vouchers(doc, method=None):
	if doc.doctype not in SALES_DOCTYPES or doc.get("docstatus") != 1 or doc.get("is_return"):
		return
	if doc.get("is_consolidated"):
		return
	if doc.get("pos_sync_source") == "Offline POS":
		from retail.promotions.pos_gift_voucher import register
		if doc.flags.from_completed_pos_sync:
			from retail.pos_completed_sale import audit_effect
			audit_effect(doc, "Voucher issuance reconciliation", lambda: register(doc))
		return
	if doc.get("custom_gift_voucher_code"):
		return
	frappe.get_doc(doc.doctype, doc.name, for_update=True)
	if frappe.db.get_value("Gift Voucher Ledger", {"issued_against_type": doc.doctype,
		"issued_against": doc.name}, "name", for_update=True):
		return

	promotions = get_active_promotions(doc)
	for promotion in promotions:
		eligible_amount = get_eligible_amount(doc, promotion)
		if eligible_amount < flt(promotion.min_sales_value):
			continue

		voucher_amount = get_voucher_amount(eligible_amount, promotion)
		if voucher_amount <= 0:
			continue

		create_voucher(doc, promotion, voucher_amount)


@frappe.whitelist()
def issue_for_invoice(doctype, name):
	if doctype not in SALES_DOCTYPES:
		frappe.throw(_("Gift vouchers can only be issued for Sales Invoices or POS Invoices."))

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	doc.check_permission("submit")
	if doc.docstatus != 1:
		frappe.throw(_("Gift vouchers can only be issued for submitted invoices."))

	issue_gift_vouchers(doc)
	return frappe.get_all(
		"Gift Voucher Ledger",
		filters={"issued_against_type": doctype, "issued_against": name},
		fields=["voucher_code", "voucher_amount", "balance_amount", "status", "expiry_date"],
	)


def cancel_issued_gift_vouchers(doc, method=None):
	if doc.doctype in SALES_DOCTYPES and not doc.get("is_consolidated"):
		_cancel_vouchers(doc.doctype, doc.name, f"Cancelled with {doc.doctype} {doc.name}")


def get_active_promotions(doc):
	posting_date = getdate(doc.get("posting_date") or nowdate())
	filters = {
		"enabled": 1,
		"active_from": ("<=", posting_date),
		"active_to": (">=", posting_date),
	}
	if doc.get("company"):
		filters["company"] = ("in", ["", doc.company])

	promotions = frappe.get_all(
		"Gift Voucher Promotion",
		filters=filters,
		fields=[
			"name",
			"description",
			"min_sales_value",
			"voucher_amount",
			"multiply_with_sales_amount",
			"expiry_days",
			"company",
			"warehouse",
		],
		order_by="min_sales_value desc, creation asc",
	)

	return [frappe.get_doc("Gift Voucher Promotion", promotion.name) for promotion in promotions if promotion_matches_doc(promotion, doc)]


def promotion_matches_doc(promotion, doc):
	if promotion.company and doc.get("company") and promotion.company != doc.company:
		return False
	if not promotion.warehouse:
		return True

	warehouses = {row.warehouse for row in doc.get("items") or [] if row.get("warehouse")}
	return promotion.warehouse in warehouses


def get_eligible_amount(doc, promotion):
	excluded_groups = {row.item_group for row in promotion.get("excluded_item_groups") or [] if row.item_group}
	if not excluded_groups:
		return flt(doc.get("grand_total")) or flt(doc.get("net_total"))

	amount = 0
	for row in doc.get("items") or []:
		if row.get("is_free_item"):
			continue
		if item_in_excluded_group(row.item_code, excluded_groups):
			continue
		amount += get_row_customer_amount(row)
	return amount


def get_row_customer_amount(row):
	return (
		flt(row.get("custom_amount_including_vat"))
		or flt(row.get("amount_including_vat"))
		or flt(row.get("net_amount"))
		or flt(row.get("amount"))
	)


def item_in_excluded_group(item_code, excluded_groups):
	item_group = frappe.db.get_value("Item", item_code, "item_group")
	while item_group:
		if item_group in excluded_groups:
			return True
		item_group = frappe.db.get_value("Item Group", item_group, "parent_item_group")
	return False


def get_voucher_amount(eligible_amount, promotion):
	if promotion.multiply_with_sales_amount:
		multiplier = math.floor(flt(eligible_amount) / flt(promotion.min_sales_value))
		return flt(promotion.voucher_amount) * multiplier
	return flt(promotion.voucher_amount)


def create_voucher(doc, promotion, voucher_amount, voucher_code=None):
	voucher = frappe.new_doc("Gift Voucher Ledger")
	voucher.voucher_code = voucher_code or make_voucher_code()
	from retail.pos_operations import key
	voucher.issuance_key = key("ERP voucher", f"{doc.doctype}:{doc.name}:{promotion.name}")
	voucher.currency = doc.get("currency")
	voucher.status = "Unused"
	voucher.voucher_amount = voucher_amount
	voucher.balance_amount = voucher_amount
	voucher.issued_date = doc.get("posting_date") or nowdate()
	voucher.expiry_date = add_days(voucher.issued_date, promotion.expiry_days) if promotion.expiry_days else None
	voucher.promotion = promotion.name
	voucher.issued_against_type = doc.doctype
	voucher.issued_against = doc.name
	voucher.customer = doc.get("customer")
	voucher.customer_name = doc.get("customer_name")
	voucher.mobile_no = doc.get("contact_mobile") or doc.get("mobile_no")
	voucher.company = doc.get("company")
	voucher.warehouse = promotion.warehouse
	voucher.insert(ignore_permissions=True)
	return voucher


def make_voucher_code():
	for _attempt in range(10):
		code = f"GV-{frappe.generate_hash(length=8).upper()}"
		if not frappe.db.exists("Gift Voucher Ledger", code):
			return code
	frappe.throw("Could not generate a unique gift voucher code. Please try again.")
