"""Add current unused credit-note snapshots to authorized POS customer responses."""

from collections import defaultdict

import frappe
from frappe.utils import flt, now_datetime, nowdate

from erpnext.accounts.utils import QueryPaymentLedger, get_currency_precision


def add_credit_note_snapshots(rows, company, customer_field):
	"""Internal helper: callers retain existing POS authorization and customer scope.

	Amounts come from ERPNext's payment-reconciliation query, not invoice totals.
	This is a current snapshot, independent of a balance pull's historical dates.
	"""
	if not rows:
		return
	names = list({row[customer_field] for row in rows})
	currency = frappe.get_cached_value("Company", company, "default_currency")
	precision = get_currency_precision() or 2
	as_of = str(now_datetime())
	snapshots = {name: [] for name in names}
	returns = frappe.get_all(
		"Sales Invoice",
		filters={"company": company, "customer": ["in", names], "docstatus": 1,
			"is_return": 1, "posting_date": ["<=", nowdate()]},
		fields=["name", "debit_to"], order_by="name asc",
	)
	by_account = defaultdict(list)
	for invoice in returns:
		by_account[invoice.debit_to].append(
			frappe._dict(voucher_type="Sales Invoice", voucher_no=invoice.name)
		)
	# Batch all customers per receivable account; never query once per customer.
	for account, vouchers in by_account.items():
		ledger = QueryPaymentLedger()
		ple = ledger.ple
		open_notes = ledger.get_voucher_outstandings(
			vouchers=vouchers, get_payments=True,
			common_filter=[ple.company == company, ple.party_type == "Customer",
				ple.party.isin(names), ple.account_type == "Receivable",
				ple.account == account, ple.posting_date <= nowdate()],
		)
		for note in open_notes:
			from retail.pos_settlements import reusable_credit
			if not reusable_credit(note.voucher_no):
				continue
			remaining = flt(-flt(note.outstanding_in_account_currency), precision)
			if note.party not in snapshots or remaining <= 0:
				continue
			snapshots[note.party].append({
				"reference_doctype": note.voucher_type,
				"reference_name": note.voucher_no,
				"receivable_account": account,
				"remaining_amount": flt(-flt(note.outstanding), precision),
				"currency": currency,
				"remaining_amount_in_account_currency": remaining,
				"account_currency": note.currency,
			})
	for row in rows:
		notes = sorted(snapshots[row[customer_field]], key=lambda note: (note["reference_name"], note["receivable_account"]))
		for note in notes:
			pos_name = frappe.db.get_value("POS Invoice", {"consolidated_invoice": note["reference_name"]}, "name")
			note["external_pos_reference"] = frappe.db.get_value("POS Invoice", pos_name, "external_pos_reference") if pos_name else None
		row.update({
			"unused_credit_note_amount": flt(sum(note["remaining_amount"] for note in notes), precision),
			"unused_credit_notes": notes,
			"credit_note_currency": currency,
			"credit_notes_as_of": as_of,
		})

	from retail.pos_settlements import add_customer_summaries
	add_customer_summaries(rows, company, customer_field)
