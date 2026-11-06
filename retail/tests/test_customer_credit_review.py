import unittest
from datetime import date
from unittest.mock import patch

import frappe

from retail import customer_credit_review as review


class TestCustomerCreditReview(unittest.TestCase):
	def setUp(self):
		self.rounding = patch.object(frappe, "get_system_settings", return_value="Banker's Rounding")
		self.rounding.start()
		self.addCleanup(self.rounding.stop)
		self.as_of = date(2026, 11, 6)
		self.invoice = frappe._dict(name="INV-1", posting_date="2026-10-01", due_date="2026-10-31",
			currency="AED", grand_total=100, rounded_total=0, disable_rounded_total=0,
			is_opening="No", is_pos=0)
		self.claim = self.entry("Sales Invoice", "INV-1", 100, "2026-10-01")
		self.schedule = [frappe._dict(term="", term_due_date="2026-10-31", term_amount=100)]

	def entry(self, doctype, name, amount, posting_date, *, currency="AED"):
		return frappe._dict(voucher_type=doctype, voucher_no=name, against_voucher_type="Sales Invoice",
			against_voucher_no="INV-1", posting_date=posting_date, account_currency=currency,
			amount=amount, amount_in_account_currency=amount)

	def payment(self, payment_type="Receive", **values):
		return frappe._dict(payment_type=payment_type, mode_of_payment="Cash", reference_date=None,
			clearance_date=None, **values)

	def analyse(self, entries=(), payments=None, schedules=None, references=None, adjusted=()):
		return review.analyse_invoice(self.invoice, [self.claim, *entries],
			self.schedule if schedules is None else schedules, payments or {}, references or {},
			set(adjusted), self.as_of)

	def stats(self, *invoices):
		return review.payment_statistics([term for invoice in invoices for term in invoice["terms"]],
			date(2026, 8, 1), self.as_of)

	def test_full_on_time_and_fully_paid_late_are_different(self):
		for paid_on, timing, delay in [("2026-10-30", "Paid by due date", 0), ("2026-11-04", "Paid late", 4)]:
			with self.subTest(paid_on=paid_on):
				row = self.analyse([self.entry("Payment Entry", "PE-1", -100, paid_on)], {"PE-1": self.payment()})
				self.assertEqual(row["status"], "Fully paid")
				self.assertEqual(row["terms"][0]["timing"], timing)
				self.assertEqual(row["terms"][0]["days_late"], delay)

	def test_partial_payment_before_due_does_not_count_as_full_on_time(self):
		row = self.analyse([self.entry("Payment Entry", "PE-1", -60, "2026-10-20"),
			self.entry("Payment Entry", "PE-2", -40, "2026-11-03")],
			{"PE-1": self.payment(), "PE-2": self.payment()})
		self.assertEqual(row["terms"][0]["full_payment_date"], "2026-11-03")
		self.assertEqual(self.stats(row)["on_time_percent"], 0)
		self.assertEqual(self.stats(row)["average_days_late"], 3)

	def test_unpaid_overdue_terms_are_in_the_rate_denominator(self):
		paid = self.analyse([self.entry("Payment Entry", "PE-1", -100, "2026-10-20")], {"PE-1": self.payment()})
		unpaid = self.analyse()
		stats = self.stats(paid, unpaid)
		self.assertEqual((stats["due_terms"], stats["paid_on_time"], stats["overdue_unpaid"]), (2, 1, 1))
		self.assertEqual(stats["on_time_percent"], 50)

	def test_due_today_future_and_missing_due_dates_do_not_lower_rate(self):
		for due in ("2026-11-06", "2026-12-01", None):
			with self.subTest(due=due):
				row = self.analyse(schedules=[frappe._dict(term="", term_due_date=due, term_amount=100)])
				self.assertIsNone(self.stats(row)["on_time_percent"])

	def test_cash_sale_does_not_establish_credit_payment_history(self):
		self.invoice.update(is_pos=1, paid_amount=100)
		row = self.analyse([self.entry("Sales Invoice", "INV-1", -100, "2026-10-01")])
		self.assertTrue(row["paid_at_sale"])
		self.assertEqual(row["status"], "Paid at sale")
		self.assertIsNone(self.stats(row)["on_time_percent"])

	def test_invoice_written_off_in_full_is_not_labelled_paid_at_sale(self):
		self.invoice.update(is_pos=1, paid_amount=0, write_off_amount=100)
		row = self.analyse([self.entry("Sales Invoice", "INV-1", -100, "2026-10-01")])
		self.assertFalse(row["paid_at_sale"])
		self.assertEqual(row["status"], "Needs review")

	def test_immediate_cash_invoice_paid_by_payment_entry_is_excluded_from_credit_history(self):
		self.invoice.due_date = "2026-10-01"
		row = self.analyse([self.entry("Payment Entry", "PE-1", -100, "2026-10-01")], {"PE-1": self.payment()},
			schedules=[frappe._dict(term="", term_due_date="2026-10-01", term_amount=100)])
		self.assertTrue(row["paid_at_sale"])
		self.assertIsNone(self.stats(row)["on_time_percent"])

	def test_incomplete_visible_ledger_is_flagged_instead_of_rating_customer(self):
		self.invoice.outstanding_amount = 0
		row = self.analyse()
		self.assertEqual(row["status"], "Needs review")
		self.assertIsNone(self.stats(row)["on_time_percent"])

	def test_credit_note_and_writeoff_are_not_customer_receipts(self):
		for doctype in ("Sales Invoice", "Journal Entry"):
			row = self.analyse([self.entry(doctype, "ADJ-1", -100, "2026-10-25")])
			self.assertEqual(row["allocated_receipts"], 0)
			self.assertEqual(row["other_settlement"], 100)
			self.assertEqual(row["status"], "Needs review")
			self.assertIsNone(self.stats(row)["on_time_percent"])

	def test_offsetting_adjustments_still_require_review(self):
		row = self.analyse([self.entry("Journal Entry", "ADJ-1", -50, "2026-10-20"),
			self.entry("Journal Entry", "ADJ-2", 50, "2026-10-21")])
		self.assertEqual(row["other_settlement"], 0)
		self.assertEqual(row["status"], "Needs review")

	def test_refund_reopens_paid_invoice(self):
		row = self.analyse([self.entry("Payment Entry", "PE-1", -100, "2026-10-20"),
			self.entry("Payment Entry", "PE-2", 30, "2026-11-01")],
			{"PE-1": self.payment(), "PE-2": self.payment("Pay")})
		self.assertEqual(row["balance"], 30)
		self.assertEqual(row["terms"][0]["balance"], 30)
		self.assertIsNone(row["terms"][0]["full_payment_date"])
		self.assertEqual(self.stats(row)["overdue_unpaid"], 1)

	def test_multiple_instalments_use_their_own_due_dates(self):
		terms = [frappe._dict(term="First", term_due_date="2026-10-15", term_amount=50),
			frappe._dict(term="Second", term_due_date="2026-10-31", term_amount=50)]
		row = self.analyse([self.entry("Payment Entry", "PE-1", -100, "2026-10-20")],
			{"PE-1": self.payment()}, schedules=terms)
		self.assertEqual([term["timing"] for term in row["terms"]], ["Paid late", "Paid by due date"])
		self.assertEqual(self.stats(row)["on_time_percent"], 50)

	def test_explicit_term_allocation_does_not_pay_an_earlier_instalment(self):
		terms = [frappe._dict(term="First", term_due_date="2026-10-15", term_amount=50),
			frappe._dict(term="Second", term_due_date="2026-10-31", term_amount=50)]
		refs = {("PE-1", "INV-1"): [frappe._dict(term="Second", allocated_amount=50)]}
		row = self.analyse([self.entry("Payment Entry", "PE-1", -50, "2026-10-20")],
			{"PE-1": self.payment()}, schedules=terms, references=refs)
		self.assertEqual([term["balance"] for term in row["terms"]], [50, 0])

	def test_one_payment_with_multiple_ledger_rows_is_not_allocated_twice(self):
		terms = [frappe._dict(term="First", term_due_date="2026-10-15", term_amount=40),
			frappe._dict(term="Second", term_due_date="2026-10-31", term_amount=60)]
		refs = {("PE-1", "INV-1"): [frappe._dict(term="First", allocated_amount=40), frappe._dict(term="Second", allocated_amount=60)]}
		row = self.analyse([self.entry("Payment Entry", "PE-1", -40, "2026-10-10"),
			self.entry("Payment Entry", "PE-1", -60, "2026-10-10")],
			{"PE-1": self.payment()}, schedules=terms, references=refs)
		self.assertEqual(row["allocated_receipts"], 100)
		self.assertEqual([term["paid"] for term in row["terms"]], [40, 60])
		self.assertEqual(row["issues"], [])

	def test_credits_deductions_and_uncleared_cheques_require_review(self):
		entry = self.entry("Payment Entry", "PE-1", -100, "2026-10-20")
		deducted = self.analyse([entry], {"PE-1": self.payment()}, adjusted=["PE-1"])
		self.assertEqual(deducted["allocated_receipts"], 0)
		cheque = self.payment()
		cheque.mode_of_payment = "Cheque"
		row = self.analyse([entry], {"PE-1": cheque})
		self.assertEqual(row["status"], "Needs review")
		self.assertIsNone(self.stats(row)["on_time_percent"])
		cheque.clearance_date = "2026-11-01"
		cleared = self.analyse([entry], {"PE-1": cheque})
		self.assertEqual(cleared["status"], "Fully paid")
		self.assertEqual(cleared["terms"][0]["full_payment_date"], "2026-11-01")
		self.assertEqual(cleared["terms"][0]["days_late"], 1)

	def test_hidden_or_cancelled_payment_is_not_assumed_to_be_cash(self):
		row = self.analyse([self.entry("Payment Entry", "PE-1", -100, "2026-10-20")])
		self.assertEqual(row["status"], "Needs review")
		self.assertEqual(row["allocated_receipts"], 0)

	def test_account_currency_not_exchange_rate_difference_drives_timing(self):
		self.invoice.currency = "USD"
		self.claim.account_currency = "USD"
		self.claim.amount = 367
		entry = self.entry("Payment Entry", "PE-1", -100, "2026-10-20", currency="USD")
		entry.amount = -370
		row = self.analyse([entry], {"PE-1": self.payment()})
		self.assertEqual((row["amount"], row["balance"], row["currency"]), (100, 0, "USD"))
		self.assertEqual(row["status"], "Fully paid")

	def test_advance_payment_date_is_not_before_invoice_posting_date(self):
		row = self.analyse([self.entry("Payment Entry", "PE-1", -100, "2026-09-20")], {"PE-1": self.payment()})
		self.assertEqual(row["terms"][0]["full_payment_date"], "2026-10-01")

	def test_snapshot_keeps_unallocated_credits_separate_without_deducting_twice(self):
		rows = [dict(voucher_type="Sales Invoice", voucher_no="INV-1", outstanding=100, due_date="2026-10-01"),
			dict(voucher_type="Payment Entry", voucher_no="PE-1", outstanding=-20),
			dict(voucher_type="Sales Invoice", voucher_no="RETURN", outstanding=-10, is_return=1),
			dict(outstanding=70)]
		result = review.current_snapshot(rows, {"outstanding": 70}, self.as_of)
		self.assertEqual((result["outstanding"], result["overdue"]), (70, 100))
		self.assertEqual((result["unallocated_receipts"], result["unused_credit_notes"]), (20, 10))
		self.assertEqual(result["ageing"]["31_60"], 100)

	def test_instalment_split_cannot_change_an_invoice_or_hide_an_unallocated_credit(self):
		original = [dict(voucher_type="Sales Invoice", voucher_no="INV", outstanding=100),
			dict(voucher_type="Payment Entry", voucher_no="PE", outstanding=-5)]
		split = [dict(voucher_type="Sales Invoice", voucher_no="INV", outstanding=40),
			dict(voucher_type="Sales Invoice", voucher_no="INV", outstanding=60),
			dict(voucher_type="Payment Entry", voucher_no="PE", outstanding=-5)]
		self.assertTrue(review.matching_voucher_totals(original, split))
		split[-1]["outstanding"] = 0
		self.assertFalse(review.matching_voucher_totals(original, split))
		split[-1]["outstanding"] = -5
		split[1]["outstanding"] = 65
		self.assertFalse(review.matching_voucher_totals(original, split))

	def test_permission_checks_precede_queries_and_never_ignore_user_permissions(self):
		with patch.object(frappe, "has_permission", return_value=False), patch.object(frappe, "get_list") as query:
			self.assertIsNone(review._read("Sales Order", ["name"], {}, optional=True))
			query.assert_not_called()
		with patch.object(frappe, "has_permission", return_value=True), \
			patch.object(review, "get_permitted_fields", return_value=["name"]), \
			patch.object(frappe, "get_list", return_value=[]) as query:
			review._read("Sales Invoice", ["name"], {"company": "Allowed", "customer": "C-1"})
			self.assertEqual(query.call_args.kwargs["filters"], {"company": "Allowed", "customer": "C-1"})
			self.assertNotIn("ignore_permissions", query.call_args.kwargs)

	def test_child_field_permissions_are_required(self):
		with patch.object(frappe, "has_permission", return_value=True), \
			patch.object(review, "get_permitted_fields", return_value=["name"]), \
			patch.object(frappe, "get_list") as query:
			self.assertIsNone(review._read("Sales Invoice", ["`tabPayment Schedule`.`payment_amount` as amount"],
				{}, child="Payment Schedule", optional=True))
			query.assert_not_called()

	def test_only_supported_periods_are_accepted_before_any_record_reads(self):
		with patch.object(frappe, "get_doc") as read, patch.object(frappe, "throw", side_effect=ValueError):
			for months in (0, -1, 100, "12 or 1=1"):
				with self.assertRaises(ValueError):
					review.get_review("C-1", "Company", months)
			read.assert_not_called()
