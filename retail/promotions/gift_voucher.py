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
			"allow_on_submit": 1,
		},
		{
			"fieldname": "custom_gift_voucher_amount",
			"label": "Gift Voucher Amount",
			"fieldtype": "Currency",
			"insert_after": "custom_gift_voucher_code",
			"read_only": 1,
			"allow_on_submit": 1,
		},
		{
			"fieldname": "custom_gift_voucher_discount_applied",
			"label": "Gift Voucher Discount Applied",
			"fieldtype": "Currency",
			"insert_after": "custom_gift_voucher_amount",
			"hidden": 1,
			"read_only": 1,
			"allow_on_submit": 1,
		},
	]
	create_custom_fields({doctype: fields for doctype in SALES_DOCTYPES}, ignore_validate=True, update=True)


def apply_gift_voucher_redemption(doc, method=None):
	if doc.doctype not in SALES_DOCTYPES:
		return

	validate_return_safety(doc)

	code = doc.get("custom_gift_voucher_code")
	if not code or doc.get("is_return"):
		return

	voucher = validate_redeemable_voucher(code, doc)
	amount = min(flt(voucher.balance_amount), flt(doc.get("grand_total")) or flt(doc.get("net_total")))
	previous_amount = flt(doc.get("custom_gift_voucher_discount_applied"))
	doc.discount_amount = flt(doc.get("discount_amount")) - previous_amount + amount
	doc.custom_gift_voucher_amount = amount
	doc.custom_gift_voucher_discount_applied = amount


def mark_gift_voucher_redeemed(doc, method=None):
	if doc.doctype not in SALES_DOCTYPES or doc.get("is_return"):
		handle_returned_issued_vouchers(doc)
		return

	code = doc.get("custom_gift_voucher_code")
	amount = flt(doc.get("custom_gift_voucher_amount"))
	if not code or amount <= 0:
		return

	voucher = frappe.get_doc("Gift Voucher Ledger", code)
	new_balance = flt(voucher.balance_amount) - amount
	status = "Redeemed" if new_balance <= 0 else "Partially Used"
	frappe.db.set_value(
		"Gift Voucher Ledger",
		code,
		{
			"balance_amount": max(new_balance, 0),
			"status": status,
			"redeemed_against_type": doc.doctype,
			"redeemed_against": doc.name,
			"redeemed_date": doc.get("posting_date") or nowdate(),
		},
		update_modified=True,
	)


def restore_redeemed_gift_voucher(doc, method=None):
	if doc.doctype not in SALES_DOCTYPES:
		return

	code = doc.get("custom_gift_voucher_code")
	amount = flt(doc.get("custom_gift_voucher_amount"))
	if not code or amount <= 0 or not frappe.db.exists("Gift Voucher Ledger", code):
		return

	voucher = frappe.get_doc("Gift Voucher Ledger", code)
	restored_balance = min(flt(voucher.voucher_amount), flt(voucher.balance_amount) + amount)
	status = "Unused" if restored_balance == flt(voucher.voucher_amount) else "Partially Used"
	frappe.db.set_value(
		"Gift Voucher Ledger",
		code,
		{
			"balance_amount": restored_balance,
			"status": status,
			"redeemed_against_type": None,
			"redeemed_against": None,
			"redeemed_date": None,
		},
		update_modified=True,
	)


def validate_redeemable_voucher(code, doc):
	if not frappe.db.exists("Gift Voucher Ledger", code):
		frappe.throw(_("Gift Voucher {0} does not exist.").format(code))

	voucher = frappe.get_doc("Gift Voucher Ledger", code)
	if voucher.status not in ("Unused", "Partially Used"):
		frappe.throw(_("Gift Voucher {0} is {1}.").format(code, voucher.status))
	if flt(voucher.balance_amount) <= 0:
		frappe.throw(_("Gift Voucher {0} has no balance.").format(code))
	if voucher.expiry_date and getdate(voucher.expiry_date) < getdate(doc.get("posting_date") or nowdate()):
		frappe.db.set_value("Gift Voucher Ledger", code, "status", "Expired", update_modified=True)
		frappe.throw(_("Gift Voucher {0} is expired.").format(code))
	if voucher.company and doc.get("company") and voucher.company != doc.get("company"):
		frappe.throw(_("Gift Voucher {0} belongs to another company.").format(code))
	return voucher


def validate_return_safety(doc, method=None):
	if doc.doctype not in SALES_DOCTYPES or not doc.get("is_return") or not doc.get("return_against"):
		return

	issued_vouchers = frappe.get_all(
		"Gift Voucher Ledger",
		filters={"issued_against_type": doc.doctype, "issued_against": doc.return_against},
		fields=["name", "status", "voucher_amount", "balance_amount"],
	)
	for voucher in issued_vouchers:
		if voucher.status in ("Redeemed", "Partially Used") or flt(voucher.balance_amount) < flt(voucher.voucher_amount):
			frappe.throw(
				_(
					"Return is blocked because Gift Voucher {0} from the original invoice is already used. Manager must adjust the refund manually."
				).format(voucher.name)
			)


def handle_returned_issued_vouchers(doc):
	if doc.doctype not in SALES_DOCTYPES or not doc.get("is_return") or not doc.get("return_against"):
		return

	for voucher in frappe.get_all(
		"Gift Voucher Ledger",
		filters={"issued_against_type": doc.doctype, "issued_against": doc.return_against, "status": "Unused"},
		pluck="name",
	):
		frappe.db.set_value(
			"Gift Voucher Ledger",
			voucher,
			{"status": "Cancelled", "balance_amount": 0, "notes": f"Cancelled by return {doc.doctype} {doc.name}"},
			update_modified=True,
		)


def issue_gift_vouchers(doc, method=None):
	if doc.doctype not in SALES_DOCTYPES or doc.get("is_return"):
		return
	if doc.get("custom_gift_voucher_code"):
		return
	if frappe.db.exists("Gift Voucher Ledger", {"issued_against_type": doc.doctype, "issued_against": doc.name}):
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
	doc = frappe.get_doc(doctype, name)
	issue_gift_vouchers(doc)
	return frappe.get_all(
		"Gift Voucher Ledger",
		filters={"issued_against_type": doctype, "issued_against": name},
		fields=["voucher_code", "voucher_amount", "balance_amount", "status", "expiry_date"],
	)


def cancel_issued_gift_vouchers(doc, method=None):
	if doc.doctype not in SALES_DOCTYPES:
		return

	for voucher in frappe.get_all(
		"Gift Voucher Ledger",
		filters={"issued_against_type": doc.doctype, "issued_against": doc.name, "status": ("!=", "Redeemed")},
		pluck="name",
	):
		frappe.db.set_value(
			"Gift Voucher Ledger",
			voucher,
			{"status": "Cancelled", "balance_amount": 0, "notes": f"Cancelled with {doc.doctype} {doc.name}"},
			update_modified=True,
		)


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


def create_voucher(doc, promotion, voucher_amount):
	voucher = frappe.new_doc("Gift Voucher Ledger")
	voucher.voucher_code = make_voucher_code()
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
