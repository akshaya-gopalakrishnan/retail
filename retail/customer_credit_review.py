"""Read-only evidence for an accountant's customer credit decision."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.model import get_permitted_fields
from frappe.utils import add_months, date_diff, flt, getdate, nowdate

from erpnext.accounts.utils import get_currency_precision
from erpnext.selling.doctype.customer.customer import get_credit_limit
from retail.customer_balances import _CustomerReceivables


def _read(doctype, fields, filters, *, child=None, optional=False):
	"""Keep document, user and field permissions on every source query."""
	if not frappe.has_permission(doctype, "read"):
		if optional:
			return None
		frappe.throw(_("Read access to {0} is required for the credit review.").format(_(doctype)), frappe.PermissionError)
	allowed = set(get_permitted_fields(doctype, permission_type="read"))
	child_allowed = set(get_permitted_fields(child, parenttype=doctype, permission_type="read")) if child else set()
	for field in fields:
		if field.startswith("`tab"):
			name = field.split("`.")[1].split(" as ")[0].strip("`")
			permitted = child_allowed
		else:
			name, permitted = field, allowed
		if name not in permitted:
			if optional:
				return None
			frappe.throw(_("Your field permissions do not allow this credit review."), frappe.PermissionError)
	return frappe.get_list(doctype, filters=filters, fields=fields, limit_page_length=0)


@frappe.whitelist()
def get_review(customer, company, months=12):
	"""No saves, reconciliation, limit changes, ratings or automatic credit actions."""
	if str(months) not in {"3", "6", "12", "24"}:
		frappe.throw(_("Choose a review period of 3, 6, 12 or 24 months."))
	if not customer or not company:
		frappe.throw(_("Select a customer and company first."))
	frappe.has_permission("Payment Entry", "read", throw=True)
	customer_doc = frappe.get_doc("Customer", customer)
	customer_doc.check_permission("read")
	company_doc = frappe.get_doc("Company", company)
	company_doc.check_permission("read")
	as_of = getdate(nowdate())
	from_date = getdate(add_months(as_of, -int(months)))
	precision = get_currency_precision() or 2
	common = {"company": company, "customer": customer, "docstatus": 1, "posting_date": ["<=", as_of]}
	invoices = _read("Sales Invoice", [
		"name", "posting_date", "due_date", "currency", "grand_total", "rounded_total",
		"disable_rounded_total", "outstanding_amount", "is_return", "return_against",
		"update_outstanding_for_self", "is_pos", "is_opening", "paid_amount", "write_off_amount", "loyalty_amount",
	], common)
	names = [row.name for row in invoices]
	payments = _read("Payment Entry", [
		"name", "posting_date", "docstatus", "payment_type", "mode_of_payment",
		"paid_amount", "received_amount", "paid_from_account_currency", "paid_to_account_currency",
		"unallocated_amount", "reference_date", "clearance_date",
	], {"company": company, "party_type": "Customer", "party": customer,
		"docstatus": ["in", [1, 2]], "posting_date": ["<=", as_of]})
	ledger = _read("Payment Ledger Entry", [
		"name", "voucher_type", "voucher_no", "against_voucher_type", "against_voucher_no",
		"posting_date", "account_currency", "amount", "amount_in_account_currency",
	], {"company": company, "party_type": "Customer", "party": customer,
		"account_type": "Receivable", "delinked": 0, "posting_date": ["<=", as_of]})
	schedules, references, deductions = [], [], []
	# Read children through permission-aware parent queries, never arbitrary child IDs.
	if names:
		schedules = _read("Sales Invoice", ["name",
			"`tabPayment Schedule`.`payment_term` as term", "`tabPayment Schedule`.`due_date` as term_due_date",
			"`tabPayment Schedule`.`payment_amount` as term_amount",
		], common, child="Payment Schedule")
	if payments:
		payment_filters = {"company": company, "party_type": "Customer", "party": customer,
			"docstatus": 1, "posting_date": ["<=", as_of]}
		references = _read("Payment Entry", ["name",
			"`tabPayment Entry Reference`.`reference_doctype` as reference_doctype",
			"`tabPayment Entry Reference`.`reference_name` as reference_name",
			"`tabPayment Entry Reference`.`payment_term` as term",
			"`tabPayment Entry Reference`.`allocated_amount` as allocated_amount",
		], payment_filters, child="Payment Entry Reference")
		deductions = _read("Payment Entry", ["name", "`tabPayment Entry Deduction`.`amount` as deduction"],
			payment_filters, child="Payment Entry Deduction")
	adjusted_payments = {row.name for row in deductions if flt(row.deduction)}
	payment_map = {row.name: row for row in payments if row.docstatus == 1}
	return_map = {row.name: row.return_against for row in invoices
		if row.is_return and row.return_against and not row.update_outstanding_for_self}
	by_invoice, by_schedule, by_reference = defaultdict(list), defaultdict(list), defaultdict(list)
	for row in ledger:
		if row.against_voucher_type == "Sales Invoice":
			by_invoice[return_map.get(row.against_voucher_no, row.against_voucher_no)].append(row)
	for row in schedules:
		if row.term_amount:
			by_schedule[row.name].append(row)
	for row in references:
		if row.reference_doctype == "Sales Invoice":
			by_reference[(row.name, row.reference_name)].append(row)
	# Review recent credit history and retain older invoices that still have debt.
	analyses = []
	for invoice in invoices:
		if invoice.is_return:
			continue
		due_dates = [getdate(row.term_due_date) for row in by_schedule[invoice.name] if row.term_due_date]
		if invoice.due_date:
			due_dates.append(getdate(invoice.due_date))
		if (getdate(invoice.posting_date) < from_date and not flt(invoice.outstanding_amount)
			and not any(date >= from_date for date in due_dates)):
			continue
		analyses.append(analyse_invoice(invoice, by_invoice[invoice.name], by_schedule[invoice.name],
			payment_map, by_reference, adjusted_payments, as_of, precision))

	native, open_rows = _receivables(customer, company, as_of)
	ageing_warning = False
	if any(len(rows) > 1 for rows in by_schedule.values()):
		_term_report, term_rows = _receivables(customer, company, as_of, by_terms=True)
		if matching_voucher_totals(open_rows, term_rows, precision):
			open_rows = term_rows
		else:
			ageing_warning = True
	snapshot = current_snapshot(open_rows, native.total_row_map.get(customer, {}), as_of, precision)
	snapshot["ageing_warning"] = ageing_warning
	snapshot["credit_limit"] = get_credit_limit(customer, company)
	credit_rows = _read("Customer", ["name", "`tabCustomer Credit Limit`.`company` as limit_company",
		"`tabCustomer Credit Limit`.`credit_limit` as credit_limit",
		"`tabCustomer Credit Limit`.`bypass_credit_limit_check` as bypass_credit_limit_check"],
		{"name": customer}, child="Customer Credit Limit")
	bypass = next((bool(row.bypass_credit_limit_check) for row in credit_rows if row.limit_company == company), False)
	commitments = _commitments(customer, company, bypass)
	snapshot.update(commitments)
	snapshot["credit_exposure"] = (flt(snapshot["outstanding"] + commitments["commitments"], precision)
		if commitments["commitments"] is not None else None)
	snapshot["available_credit"] = (flt(snapshot["credit_limit"] - snapshot["credit_exposure"], precision)
		if snapshot["credit_limit"] > 0 and snapshot["credit_exposure"] is not None else None)

	terms = [term for invoice in analyses for term in invoice["terms"]]
	statistics = payment_statistics(terms, from_date, as_of)
	trends = [{"months": count, **payment_statistics(terms, getdate(add_months(as_of, -count)), as_of)}
		for count in (3, 6, 12) if count <= int(months)]
	analyses.sort(key=lambda row: (row["posting_date"], row["invoice"]), reverse=True)
	visible_payments = sorted((dict(row) for row in payments if getdate(row.posting_date) >= from_date
		or (row.docstatus == 1 and flt(row.unallocated_amount))), key=lambda row: (row["posting_date"], row["name"]), reverse=True)
	return {"customer": customer, "customer_name": customer_doc.customer_name, "company": company,
		"currency": company_doc.default_currency, "as_of": str(as_of), "from_date": str(from_date),
		"payment_terms": customer_doc.get("payment_terms"), "snapshot": snapshot, "statistics": statistics,
		"trends": trends, "invoices": analyses[:200], "invoice_count": len(analyses),
		"payments": visible_payments[:200], "payment_count": len(visible_payments),
		"paid_at_sale_count": sum(row["paid_at_sale"] for row in analyses)}


def _receivables(customer, company, as_of, by_terms=False):
	report = _CustomerReceivables({"company": company, "party_type": "Customer", "party": [customer],
		"report_date": as_of, "group_by_party": 1, "based_on_payment_terms": int(by_terms),
		"ageing_based_on": "Due Date", "calculate_ageing_with": "Report Date"})
	report.list_parties = {customer: {}}
	rows = report.run({"account_type": "Receivable", "naming_by": ["Selling Settings", "cust_master_name"]})[1]
	return report, rows


def matching_voucher_totals(original, split, precision=2):
	"""An instalment display must never change a native invoice/credit balance."""
	def totals(rows):
		result = defaultdict(float)
		for row in rows:
			if row.get("voucher_no"):
				result[(row["voucher_type"], row["voucher_no"])] += flt(row.get("outstanding"))
		return result
	first, second = totals(original), totals(split)
	return all(flt(first[key] - second[key], precision) == 0 for key in first.keys() | second.keys())


def current_snapshot(rows, total, as_of, precision=2):
	result = {"outstanding": flt(total.get("outstanding"), precision), "overdue": 0.0,
		"oldest_overdue_days": 0, "unallocated_receipts": 0.0, "unused_credit_notes": 0.0,
		"ageing": {"1_30": 0.0, "31_60": 0.0, "61_90": 0.0, "over_90": 0.0}}
	for row in rows:
		if not row.get("voucher_no"):
			continue
		amount = flt(row.get("outstanding"))
		if amount < 0:
			if row.get("voucher_type") == "Payment Entry":
				result["unallocated_receipts"] -= amount
			elif row.get("voucher_type") == "Sales Invoice" and row.get("is_return"):
				result["unused_credit_notes"] -= amount
		if amount > 0 and row.get("due_date") and getdate(row["due_date"]) < as_of:
			days = date_diff(as_of, row["due_date"])
			result["overdue"] += amount
			result["oldest_overdue_days"] = max(result["oldest_overdue_days"], days)
			bucket = "1_30" if days <= 30 else "31_60" if days <= 60 else "61_90" if days <= 90 else "over_90"
			result["ageing"][bucket] += amount
	for key in ("overdue", "unallocated_receipts", "unused_credit_notes"):
		result[key] = flt(result[key], precision)
	result["ageing"] = {key: flt(value, precision) for key, value in result["ageing"].items()}
	return result


def _commitments(customer, company, bypass):
	"""The native credit-exposure formula, restricted to readable source records."""
	order_total = 0.0
	if not bypass:
		orders = _read("Sales Order", ["name", "base_grand_total", "per_billed"],
			{"customer": customer, "company": company, "docstatus": 1, "per_billed": ["<", 100],
				"status": ["!=", "Closed"]}, optional=True)
		if orders is None:
			return {"commitments": None, "sales_order_bypass": bypass}
		order_total = sum(flt(row.base_grand_total) * (100 - flt(row.per_billed)) / 100 for row in orders)
	deliveries = _read("Delivery Note", ["name", "base_net_total", "base_grand_total",
		"`tabDelivery Note Item`.`name` as detail", "`tabDelivery Note Item`.`amount` as amount",
		"`tabDelivery Note Item`.`against_sales_order` as against_sales_order",
		"`tabDelivery Note Item`.`against_sales_invoice` as against_sales_invoice"],
		{"company": company, "customer": customer, "docstatus": 1, "status": ["not in", ["Closed", "Stopped"]]},
		child="Delivery Note Item", optional=True)
	if deliveries is None:
		return {"commitments": None, "sales_order_bypass": bypass}
	bills = _read("Sales Invoice", ["name", "`tabSales Invoice Item`.`dn_detail` as detail",
		"`tabSales Invoice Item`.`amount` as amount"],
		{"company": company, "customer": customer, "docstatus": 1}, child="Sales Invoice Item", optional=True)
	if bills is None:
		return {"commitments": None, "sales_order_bypass": bypass}
	billed = defaultdict(float)
	for row in bills:
		billed[row.detail] += flt(row.amount)
	for row in deliveries:
		if row.against_sales_order or row.against_sales_invoice or not row.base_net_total:
			continue
		order_total += max(0, flt(row.amount) - billed[row.detail]) * flt(row.base_grand_total) / flt(row.base_net_total)
	return {"commitments": order_total, "sales_order_bypass": bypass}


def analyse_invoice(invoice, ledger, schedules, payments, references, adjusted_payments, as_of, precision=2):
	"""Timing uses account-currency allocations; never infer payment from balance alone."""
	tolerance = 0.5 / 10**precision
	claim_rows = [row for row in ledger if row.voucher_type == "Sales Invoice"
		and row.voucher_no == invoice.name and row.against_voucher_no == invoice.name
		and flt(row.amount_in_account_currency) > 0]
	amount = sum(flt(row.amount_in_account_currency) for row in claim_rows)
	currencies = {row.account_currency for row in ledger}
	currency = next(iter(currencies)) if len(currencies) == 1 else invoice.currency
	issues = []
	if not claim_rows or len(currencies) != 1:
		issues.append("Invoice ledger is incomplete or uses multiple account currencies")
	if invoice.get("is_opening") == "Yes":
		issues.append("Opening invoice: earlier payment history is not available")
	ledger_balance = sum(flt(row.amount_in_account_currency) for row in ledger)
	if invoice.get("outstanding_amount") is not None and abs(ledger_balance - flt(invoice.outstanding_amount)) > max(tolerance, 0.02):
		issues.append("Visible ledger and invoice balance differ; reconcile before judging payment timing")
	face = flt(invoice.get("rounded_total")) if not invoice.get("disable_rounded_total") and invoice.get("rounded_total") else flt(invoice.grand_total)
	terms = [{"term": row.term or "", "due_date": str(row.term_due_date) if row.term_due_date else None,
		"amount": flt(row.term_amount) * amount / face if face else 0.0} for row in schedules]
	if not terms:
		terms = [{"term": "", "due_date": str(invoice.due_date) if invoice.due_date else None, "amount": amount}]
	if abs(sum(term["amount"] for term in terms) - amount) > max(tolerance, 0.02):
		issues.append("Payment schedule does not match the invoice ledger")
	if any(not term["due_date"] for term in terms):
		issues.append("Missing payment due date")
	terms.sort(key=lambda term: term["due_date"] or "9999-12-31")
	for term in terms:
		term.update(paid=0.0, full_payment_date=None, invoice=invoice.name)
	events, receipts, adjustments = [], 0.0, 0.0
	# A payment may have several ledger rows (including one per instalment).
	# Combine those before applying its explicit term allocations exactly once.
	grouped = {}
	for source in ledger:
		key = (source.voucher_type, source.voucher_no, source.posting_date, source in claim_rows)
		if key not in grouped:
			grouped[key] = frappe._dict(source)
			grouped[key].amount_in_account_currency = 0.0
		grouped[key].amount_in_account_currency += flt(source.amount_in_account_currency)
	for key, row in grouped.items():
		value = -flt(row.amount_in_account_currency)
		if key[-1] or abs(value) <= tolerance:
			continue
		kind = "Adjustment"
		event_date = str(row.posting_date)
		if row.voucher_type == "Payment Entry" and row.voucher_no in payments:
			payment = payments[row.voucher_no]
			if row.voucher_no not in adjusted_payments:
				if value > 0 and payment.payment_type == "Receive":
					kind = "Receipt"
				elif value < 0 and payment.payment_type == "Pay":
					kind = "Refund"
			is_cheque = ("cheque" in (payment.mode_of_payment or "").lower()
				or "check" in (payment.mode_of_payment or "").lower()
				or (payment.reference_date and getdate(payment.reference_date) > as_of))
			if is_cheque:
				if not payment.clearance_date or getdate(payment.clearance_date) > as_of:
					issues.append("Cheque or future-dated payment requires clearance review")
				else:
					event_date = max(event_date, str(payment.clearance_date))
		elif row.voucher_type == "Sales Invoice" and row.voucher_no == invoice.name:
			kind = "Invoice settlement"
		if kind in ("Receipt", "Refund"):
			receipts += value
		else:
			adjustments += value
		allocation_rows = references.get((row.voucher_no, invoice.name), [])
		term_rows = [ref for ref in allocation_rows if flt(ref.allocated_amount)]
		# Explicit term allocations win; otherwise use earliest-due-first and label that basis.
		if any(ref.term for ref in term_rows) and kind == "Receipt":
			weight = sum(abs(flt(ref.allocated_amount)) for ref in term_rows)
			for ref in term_rows:
				events.append({"date": event_date, "doctype": row.voucher_type, "name": row.voucher_no,
					"kind": kind, "amount": value * abs(flt(ref.allocated_amount)) / weight, "term": ref.term or ""})
		else:
			events.append({"date": event_date, "doctype": row.voucher_type, "name": row.voucher_no,
				"kind": kind, "amount": value, "term": ""})
	events.sort(key=lambda event: (event["date"], event["name"], event["term"]))
	for event in events:
		remaining = event["amount"]
		candidates = [term for term in terms if not event["term"] or term["term"] == event["term"]]
		if not candidates:
			issues.append("A payment term could not be matched")
		for term in (candidates if remaining >= 0 else list(reversed(candidates))):
			applied = min(remaining, max(0, term["amount"] - term["paid"])) if remaining >= 0 else -min(-remaining, term["paid"])
			was_full = term["paid"] >= term["amount"] - tolerance
			term["paid"] += applied
			remaining -= applied
			if term["paid"] >= term["amount"] - tolerance and not was_full:
				term["full_payment_date"] = max(event["date"], str(invoice.posting_date))
			elif term["paid"] < term["amount"] - tolerance:
				term["full_payment_date"] = None
		if abs(remaining) > max(tolerance, 0.02):
			issues.append("Settlement allocations need review")
	self_settled = sum(event["amount"] for event in events if event["kind"] == "Invoice settlement")
	paid_at_sale = (amount > 0 and invoice.get("is_pos") and self_settled >= amount - tolerance
		and flt(invoice.get("paid_amount")) >= face - tolerance
		and not flt(invoice.get("write_off_amount")) and not flt(invoice.get("loyalty_amount"))
		and abs(ledger_balance) <= tolerance
		and all(event["date"] <= str(invoice.posting_date) for event in events))
	# Ordinary cash invoices can be settled by a same-day Payment Entry as well.
	if (amount > 0 and receipts >= amount - tolerance and not adjustments and not issues
		and abs(ledger_balance) <= tolerance
		and all(event["kind"] in ("Receipt", "Refund") and event["date"] <= str(invoice.posting_date) for event in events)
		and all(term["due_date"] and term["due_date"] <= str(invoice.posting_date) for term in terms)):
		paid_at_sale = True
	paid_at_sale = bool(paid_at_sale)
	if any(event["kind"] not in ("Receipt", "Refund") for event in events) and not paid_at_sale:
		issues.append("Settlement includes credits, write-offs or other adjustments")
	for term in terms:
		term["balance"] = flt(max(0, term["amount"] - term["paid"]), precision)
		term["eligible"] = not issues and not paid_at_sale and term["amount"] > tolerance
		term["days_late"] = (max(0, date_diff(term["full_payment_date"], term["due_date"]))
			if term["full_payment_date"] and term["due_date"] else None)
		term["timing"] = ("Paid at sale" if paid_at_sale else "Needs review" if issues else
			"Paid late" if term["full_payment_date"] and term["days_late"] else
			"Paid by due date" if term["full_payment_date"] else
			"Overdue" if term["due_date"] and getdate(term["due_date"]) < as_of else "Not yet overdue")
		for key in ("amount", "paid"):
			term[key] = flt(term[key], precision)
	return {"invoice": invoice.name, "posting_date": str(invoice.posting_date), "due_date": str(invoice.due_date) if invoice.due_date else None,
		"currency": currency, "amount": flt(amount, precision), "allocated_receipts": flt(receipts, precision),
		"other_settlement": flt(adjustments, precision), "balance": flt(ledger_balance, precision),
		"paid_at_sale": paid_at_sale, "issues": sorted(set(issues)), "terms": terms, "events": events,
		"status": "Paid at sale" if paid_at_sale else "Needs review" if issues else
			"Fully paid" if all(term["balance"] <= tolerance for term in terms) else
			"Partially paid" if receipts > tolerance else "Unpaid"}


def payment_statistics(terms, from_date, as_of):
	# Due today is still within its payment period. Future terms never lower the rate.
	due = [term for term in terms if term["due_date"] and from_date <= getdate(term["due_date"]) < as_of]
	eligible = [term for term in due if term["eligible"]]
	on_time = sum(term["timing"] == "Paid by due date" for term in eligible)
	delays = [term["days_late"] for term in eligible if term["timing"] == "Paid late"]
	return {"due_terms": len(eligible), "paid_on_time": on_time, "paid_late": len(delays),
		"overdue_unpaid": sum(term["balance"] > 0 for term in eligible),
		"excluded_terms": len(due) - len(eligible),
		"on_time_percent": flt(on_time / len(eligible) * 100, 1) if eligible else None,
		"average_days_late": flt(sum(delays) / len(delays), 1) if delays else None,
		"longest_paid_delay": max(delays) if delays else None}
