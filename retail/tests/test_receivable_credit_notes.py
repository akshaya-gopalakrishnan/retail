import unittest

import frappe

from retail.core_compat.accounts_receivable import ReceivablePayableReport


class TestReceivableCreditNotes(unittest.TestCase):
    def allocate(self, *, is_return=1, voucher_type="Sales Invoice", linked=False,
                 amount=-31.5, account_type="Receivable", party_currency=False):
        report = ReceivablePayableReport.__new__(ReceivablePayableReport)
        report.filters = frappe._dict(in_party_currency=party_currency)
        report.account_type = account_type
        report.invoice_details = {"RETURN": {"is_return": is_return}}
        row = frappe._dict(voucher_no="ORIGINAL" if linked else "RETURN",
                          invoiced=0, paid=0, credit_note=0,
                          invoiced_in_account_currency=0, paid_in_account_currency=0,
                          credit_note_in_account_currency=0)
        report.get_voucher_balance = lambda ple: row
        ple = frappe._dict(voucher_type=voucher_type, voucher_no="RETURN",
                           against_voucher_no=row.voucher_no, amount=amount,
                           amount_in_account_currency=amount / 2)
        report.update_voucher_balance(ple)
        return row

    def test_standalone_return_is_credit_in_both_currencies(self):
        row = self.allocate()
        self.assertEqual((row.paid, row.credit_note), (0, 31.5))
        self.assertEqual((row.paid_in_account_currency, row.credit_note_in_account_currency),
                         (0, 15.75))
        self.assertEqual(row.invoiced - row.paid - row.credit_note, -31.5)

    def test_party_currency_uses_account_amount(self):
        row = self.allocate(party_currency=True)
        self.assertEqual((row.paid, row.credit_note), (0, 15.75))

    def test_linked_return_remains_credit(self):
        row = self.allocate(linked=True)
        self.assertEqual((row.paid, row.credit_note), (0, 31.5))

    def test_payments_nonreturns_and_payables_keep_existing_classification(self):
        for options in ({"voucher_type": "Payment Entry"}, {"is_return": 0},
                        {"voucher_type": "Purchase Invoice", "account_type": "Payable"}):
            with self.subTest(options=options):
                row = self.allocate(**options)
                self.assertEqual((row.paid, row.credit_note), (31.5, 0))

    def test_refund_reduces_credit_balance_without_becoming_another_credit(self):
        row = self.allocate(voucher_type="Payment Entry", linked=True, amount=10)
        self.assertEqual((row.invoiced, row.paid, row.credit_note), (0, -10, 0))
