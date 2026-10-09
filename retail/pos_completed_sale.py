"""Preserve POS financial facts while retaining ERPNext document/account checks.

Only the authenticated sync service sets the immutable payload. Current ERP
prices/promotions are comparison data, never the source of completed POS totals.
"""
import frappe
from frappe.utils import cint, flt
from erpnext.accounts.doctype.pos_invoice.pos_invoice import POSInvoice


def payload_for(doc):
	if doc.doctype == "POS Invoice" and doc.get("pos_sync_source") == "Offline POS":
		return frappe.parse_json(doc.get("custom_pos_completed_payload") or "{}")
	return {}


def note_mismatch(doc, reason):
	"""Collect once across insert/submit; persist after the invoice is submitted."""
	reasons = doc.flags.get("pos_mismatch_reasons")
	if reasons is None:
		reasons = doc.flags.pos_mismatch_reasons = []
	if reason not in reasons:
		reasons.append(reason)


def audit_validation(doc, label, check):
	"""Current business policy is advisory for an authenticated completed sale.

	Only validation failures are comparisons. Programming/database errors and
	permission failures must not be misreported as successful posting.
	"""
	if not payload_for(doc):
		return check()
	message_count = len(frappe.local.message_log or [])
	try:
		return check()
	except frappe.ValidationError as exc:
		frappe.local.message_log = (frappe.local.message_log or [])[:message_count]
		note_mismatch(doc, f"{label}: {exc}. Completed POS sale retained; review required.")


def completed_session(doc, payload, counter):
	from retail.api import pos_sync

	audit_validation(doc, "Day closing", lambda: pos_sync._assert_day_not_closed(
		counter.branch, pos_sync._business_date(payload)))
	result = audit_validation(doc, "Cashier/session", lambda: pos_sync._validate_active_counter_session(
		payload, counter, check_day=False))
	if result is not None:
		return result
	# Keep valid historical links even when the shift has since closed. Missing
	# optional links remain in the immutable payload and the mismatch reason.
	values = []
	for doctype, value in (
		("Employee", payload.get("cashier_employee") or payload.get("cashier_id")),
		("POS Cashier Shift", payload.get("cashier_shift") or payload.get("cashier_shift_id")),
		("POS Counter Session", payload.get("counter_session") or payload.get("counter_session_id")),
	):
		values.append(value if value and frappe.db.exists(doctype, value) else None)
	return tuple(values)


def audit_effect(doc, label, action):
	"""A rejected ancillary effect is audited without leaving partial writes."""
	if not payload_for(doc):
		return action()
	def attempt():
		frappe.db.savepoint("pos_ancillary_effect")
		try:
			return action()
		except frappe.ValidationError:
			frappe.db.rollback(save_point="pos_ancillary_effect")
			raise
	return audit_validation(doc, label, attempt)


def prepare(doc, method=None):
	payload = payload_for(doc)
	if not payload:
		return
	previous = doc.get_doc_before_save()
	if previous and previous.get("custom_pos_completed_payload") != doc.custom_pos_completed_payload:
		frappe.throw("A completed POS snapshot cannot be changed.")
	if doc.is_new() and not doc.flags.from_completed_pos_sync:
		frappe.throw("Completed POS snapshots must be created through the POS sync API.")
	doc.ignore_pricing_rule = 1
	doc.taxes_and_charges = None
	doc.additional_discount_percentage = 0
	doc.discount_amount = _signed(doc, payload.get("discount_amount"))
	doc.apply_discount_on = "Net Total"
	doc.disable_rounded_total = 1
	# Use explicit tax amounts, assigned only to this company's configured accounts.
	taxes = payload.get("taxes") or []
	vat = payload.get("vat_amount")
	if vat is None:
		vat = sum(flt(row.get("tax_amount")) for row in taxes)
	if not taxes and flt(vat):
		account = _tax_account(doc)
		taxes = [{"account_head": account, "tax_amount": vat}]
	doc.set("taxes", [])
	for row in taxes:
		account = row.get("account_head") or _tax_account(doc)
		if frappe.get_cached_value("Account", account, "company") != doc.company:
			frappe.throw("Tax account must belong to the counter's company.")
		doc.append("taxes", {"charge_type": "Actual", "account_head": account,
			"description": row.get("description") or "POS reported VAT", "rate": 0,
			"tax_amount": _signed(doc, row.get("tax_amount")), "cost_center": doc.cost_center})
	for item in doc.get("items") or []:
		item.item_tax_template = None
		item.item_tax_rate = "{}"


def _tax_account(doc):
	profile_template = frappe.get_cached_value("POS Profile", doc.pos_profile, "taxes_and_charges")
	if profile_template:
		account = frappe.db.get_value("Sales Taxes and Charges", {"parent": profile_template}, "account_head")
		if account:
			return account
	for item in doc.get("items") or []:
		template = frappe.get_cached_value("Item", item.item_code, "custom_tax")
		if template:
			account = frappe.db.get_value("Item Tax Template Detail", {"parent": template}, "tax_type")
			if account and frappe.get_cached_value("Account", account, "company") == doc.company:
				return account
	frappe.throw("Configure a VAT account in the POS profile, or supply taxes[].account_head.")


def _signed(doc, value):
	return -abs(flt(value)) if doc.is_return else flt(value)


def restore(doc, method=None):
	"""Restore submitted amounts after core derives stock/payment helper fields."""
	payload = payload_for(doc)
	if not payload:
		return
	factor = flt(doc.conversion_rate) or 1
	for item, row in zip(doc.items, payload.get("items") or []):
		# rate/amount are before invoice-level discount; net_amount is after it.
		if row.get("amount") is not None:
			item.amount = _signed(doc, row["amount"])
		if row.get("net_amount") is not None:
			item.net_amount = _signed(doc, row["net_amount"])
		item.rate = item.amount / item.qty if item.qty else 0
		item.net_rate = item.net_amount / item.qty if item.qty else 0
		for field in ("rate", "amount", "net_rate", "net_amount"):
			item.set("base_" + field, flt(item.get(field) * factor, item.precision("base_" + field)))
		vat = row.get("vat_amount", row.get("tax_amount"))
		if vat is not None:
			item.custom_amount_including_vat = item.net_amount + _signed(doc, vat)
			item.custom_rate_including_vat = item.custom_amount_including_vat / item.qty if item.qty else 0
	doc.total = sum(flt(row.amount) for row in doc.items)
	doc.net_total = sum(flt(row.net_amount) for row in doc.items)
	vat = payload.get("vat_amount")
	if vat is None:
		vat = sum(flt(row.get("tax_amount")) for row in payload.get("taxes") or [])
	doc.total_taxes_and_charges = _signed(doc, vat)
	reported_total = payload.get("grand_total")
	rows = payload.get("items") or []
	# Legacy terminals send inclusive unit prices and a bill VAT total, but no
	# grand_total/net_amount. Derive the bill from those original prices before
	# ERP's rounded exclusive unit rates can change what the customer paid.
	if reported_total is None and rows and all(
		row.get("amount") is None and row.get("net_amount") is None
		and cint(row.get("rate_includes_vat", frappe.get_cached_value(
			"Item", item.item_code, "custom_sales_rate_includes_vat")))
		for item, row in zip(doc.items, rows)
	):
		reported_total = sum((flt(row.get("rate")) - flt(row.get("discount_amount")))
			* abs(flt(row.get("qty"))) for row in rows) - flt(payload.get("discount_amount"))
	doc.grand_total = _signed(doc, reported_total) if reported_total is not None else doc.net_total + doc.total_taxes_and_charges
	# Explicit final total is authoritative. Allocate any difference to the final
	# line only when POS did not send final per-line net amounts (legacy clients).
	difference = flt(doc.grand_total - doc.total_taxes_and_charges - doc.net_total, 9)
	if difference and doc.items:
		if payload.get("grand_total") is None and reported_total is not None and abs(difference) > 0.01:
			note_mismatch(doc, f"ERP rounded line totals differ from POS inclusive bill by {difference}. "
				"POS gross total and VAT retained; difference allocated to final line.")
		if all(row.get("net_amount") is not None for row in payload.get("items") or []):
			note_mismatch(doc, "POS line net amounts + VAT differ from grand_total by "
				f"{difference}. POS grand_total and VAT retained; difference allocated to final line. "
				"Original line amounts preserved in the completed payload.")
		item = doc.items[-1]
		item.net_amount += difference
		item.net_rate = item.net_amount / item.qty
		item.base_net_amount = flt(item.net_amount * factor, item.precision("base_net_amount"))
		item.base_net_rate = item.net_rate * factor
		doc.net_total += difference
	for field in ("total", "net_total", "grand_total", "total_taxes_and_charges", "discount_amount"):
		doc.set("base_" + field, flt(doc.get(field) * factor, doc.precision("base_" + field)))
	doc.rounded_total = _signed(doc, payload.get("rounded_total"))
	doc.rounding_adjustment = _signed(doc, payload.get("rounding_adjustment"))
	doc.base_rounded_total = flt(doc.rounded_total * factor, doc.precision("base_rounded_total"))
	doc.base_rounding_adjustment = flt(doc.rounding_adjustment * factor, doc.precision("base_rounding_adjustment"))
	doc.disable_rounded_total = 0 if payload.get("rounded_total") is not None else 1
	for tax in doc.taxes:
		tax.tax_amount_after_discount_amount = tax.tax_amount
		tax.base_tax_amount = tax.base_tax_amount_after_discount_amount = flt(tax.tax_amount * factor, tax.precision("base_tax_amount"))
		tax.total = doc.grand_total
		tax.base_total = doc.base_grand_total
	doc.paid_amount = sum(flt(row.amount) for row in doc.payments)
	doc.base_paid_amount = flt(doc.paid_amount * factor, doc.precision("base_paid_amount"))
	doc.outstanding_amount = flt((doc.rounded_total if not doc.disable_rounded_total else doc.grand_total)
		- doc.paid_amount - flt(doc.write_off_amount), doc.precision("outstanding_amount"))
	if doc.outstanding_amount < 0 and not doc.is_return:
		doc.outstanding_amount = 0
	doc.set_total_in_words()


class RetailPOSInvoice(POSInvoice):
	def before_cancel(self):
		if payload_for(self):
			frappe.throw("Completed POS bills cannot be cancelled; use an independently referenced return.")
		from retail.pos_realtime import cancel_invoice_posting
		cancel_invoice_posting(self)
		super().before_cancel()

	def validate_max_discount(self):
		return audit_validation(self, "Maximum discount", super().validate_max_discount)

	def validate_selling_price(self):
		return audit_validation(self, "Selling price", super().validate_selling_price)

	def validate_pos_opening_entry(self):
		return audit_validation(self, "POS opening", super().validate_pos_opening_entry)

	def validate_stock_availablility(self):
		return audit_validation(self, "Stock availability", super().validate_stock_availablility)

	def validate_full_payment(self):
		return audit_validation(self, "Payment policy", super().validate_full_payment)

	def calculate_taxes_and_totals(self):
		if not payload_for(self):
			from retail.promotions.gift_voucher import calculate_invoice_totals
			return calculate_invoice_totals(self, super().calculate_taxes_and_totals)
		prepare(self)
		super().calculate_taxes_and_totals()
		restore(self)
