"""Additive POS credit-note response contract; no accounting writes."""

import unittest
from unittest.mock import Mock, patch

import frappe
from pypika import Table
from retail import customer_credit_notes as service


class TestCustomerCreditNotes(unittest.TestCase):
    def setUp(self):
        for patcher in (
            patch.object(frappe, "get_system_settings", return_value="Banker's Rounding"),
            patch.object(frappe, "get_cached_value", return_value="AED"),
            patch.object(service, "get_currency_precision", return_value=2),
            patch.object(service, "now_datetime", return_value="2026-09-28 12:00:00"),
            patch.object(service, "nowdate", return_value="2026-09-28"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_partial_allocation_currency_and_existing_fields(self):
        rows = [{"name": "C1", "credit_limit": 200, "modified": "unchanged"}, {"name": "C2"}]
        ledger = Mock()
        ledger.ple = Table("tabPayment Ledger Entry")
        ledger.get_voucher_outstandings.return_value = [
            frappe._dict(party="C1", voucher_type="Sales Invoice", voucher_no="CN1",
                         invoice_amount=-1000, outstanding=-100, outstanding_in_account_currency=-25,
                         currency="USD"),
            frappe._dict(party="C1", voucher_type="Sales Invoice", voucher_no="CN2",
                         outstanding=0, outstanding_in_account_currency=0, currency="USD"),
        ]
        with patch.object(frappe, "get_all", return_value=[
            frappe._dict(name="CN1", debit_to="Debtors USD"),
            frappe._dict(name="CN2", debit_to="Debtors USD"),
        ]) as invoices, patch.object(service, "QueryPaymentLedger", return_value=ledger):
            service.add_credit_note_snapshots(rows, "Company", "name")
        self.assertEqual(rows[0]["credit_limit"], 200)
        self.assertEqual(rows[0]["modified"], "unchanged")
        self.assertEqual(rows[0]["unused_credit_note_amount"], 100)
        self.assertEqual(rows[0]["unused_credit_notes"], [{
            "reference_doctype": "Sales Invoice", "reference_name": "CN1",
            "receivable_account": "Debtors USD", "remaining_amount": 100,
            "currency": "AED", "remaining_amount_in_account_currency": 25, "account_currency": "USD",
        }])
        self.assertEqual(rows[1]["unused_credit_notes"], [])
        self.assertEqual(rows[1]["unused_credit_note_amount"], 0)
        filters = invoices.call_args.kwargs["filters"]
        self.assertEqual(filters["company"], "Company")
        self.assertEqual(filters["docstatus"], 1)
        self.assertEqual(filters["is_return"], 1)
        self.assertEqual(filters["posting_date"], ["<=", "2026-09-28"])
        ledger.get_voucher_outstandings.assert_called_once()
        self.assertTrue(ledger.get_voucher_outstandings.call_args.kwargs["get_payments"])

    def test_no_returns_keeps_historical_balance_and_adds_zero_snapshot(self):
        rows = [{"customer": "C1", "current_balance": -150, "opening_balance": 12}]
        with patch.object(frappe, "get_all", return_value=[]), \
                patch.object(service, "QueryPaymentLedger") as ledger:
            service.add_credit_note_snapshots(rows, "Company", "customer")
        self.assertEqual(rows[0]["current_balance"], -150)
        self.assertEqual(rows[0]["opening_balance"], 12)
        self.assertEqual(rows[0]["unused_credit_note_amount"], 0)
        self.assertEqual(rows[0]["unused_credit_notes"], [])
        self.assertEqual(rows[0]["credit_note_currency"], "AED")
        self.assertEqual(rows[0]["credit_notes_as_of"], "2026-09-28 12:00:00")
        ledger.assert_not_called()

    def test_multiple_customers_are_batched_per_account(self):
        rows = [{"customer": f"C{i}"} for i in range(100)]
        ledger = Mock()
        ledger.ple = Table("tabPayment Ledger Entry")
        ledger.get_voucher_outstandings.return_value = [
            frappe._dict(party="C0", voucher_type="Sales Invoice", voucher_no="CN1",
                         outstanding=-10, outstanding_in_account_currency=-10, currency="AED"),
            frappe._dict(party="C99", voucher_type="Sales Invoice", voucher_no="CN2",
                         outstanding=-20, outstanding_in_account_currency=-20, currency="AED"),
        ]
        with patch.object(frappe, "get_all", return_value=[
            frappe._dict(name="CN1", debit_to="Debtors"), frappe._dict(name="CN2", debit_to="Debtors"),
        ]), patch.object(service, "QueryPaymentLedger", return_value=ledger):
            service.add_credit_note_snapshots(rows, "Company", "customer")
        ledger.get_voucher_outstandings.assert_called_once()
        self.assertEqual(rows[0]["unused_credit_note_amount"], 10)
        self.assertEqual(rows[99]["unused_credit_note_amount"], 20)

    def test_empty_response_does_not_query(self):
        with patch.object(frappe, "get_all") as query:
            service.add_credit_note_snapshots([], "Company", "customer")
        query.assert_not_called()
