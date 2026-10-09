"""Read-only regression checks for the Customer List accounting projection."""

import unittest
from unittest.mock import Mock, patch

import frappe
from retail import customer_balances as service


class TestCustomerBalances(unittest.TestCase):
    def setUp(self):
        for patcher in (
            patch.object(frappe.local, "flags", frappe._dict(in_test=False), create=True),
            patch.object(frappe, "get_system_settings", return_value="Banker's Rounding"),
            patch.object(service, "now_datetime", return_value="2026-09-28 12:00:00"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_unused_credit_is_informational_and_not_deducted_twice(self):
        balances = {"C1": {"credit_limit": 10000, "outstanding_amount": 1570,
                           "unused_credit_note_amount": 0}}
        rows = [
            # Original return was 2,000; 1,500 has already been allocated.
            frappe._dict(party="C1", voucher_type="Sales Invoice", voucher_no="RETURN",
                         invoice_amount=-2000, outstanding=-500, outstanding_in_account_currency=-125),
            frappe._dict(party="C1", voucher_type="Sales Invoice", voucher_no="INVOICE", outstanding=3000),
            frappe._dict(party="C1", voucher_type="Sales Invoice", voucher_no="USED-RETURN", outstanding=0),
            frappe._dict(party="C1", voucher_type="Sales Invoice", voucher_no="OVERPAID", outstanding=-30),
            frappe._dict(party="C1", voucher_type="Payment Entry", voucher_no="ADVANCE", outstanding=-700),
            frappe._dict(party="C1", voucher_type="Journal Entry", voucher_no="ADVANCE-JE", outstanding=-200),
            frappe._dict(party="HIDDEN", voucher_type="Sales Invoice", voucher_no="OTHER", outstanding=999),
        ]
        service._set_unused_credit_notes(balances, rows, {"RETURN", "USED-RETURN"})
        service._finalize(balances["C1"], 2)
        self.assertEqual(balances["C1"], {
            "credit_limit": 10000, "outstanding_amount": 1570, "unused_credit_note_amount": 500,
            "net_balance": 1570, "remaining_credit_limit": 8430,
            "available_credit_including_credit_notes": 8430,
        })

    def test_negative_balances_are_not_clamped(self):
        balance = {"credit_limit": 100, "outstanding_amount": -50, "unused_credit_note_amount": 200}
        service._finalize(balance, 2)
        self.assertEqual(balance["remaining_credit_limit"], 150)
        self.assertEqual(balance["net_balance"], -50)
        self.assertEqual(balance["available_credit_including_credit_notes"], 150)

    def test_endpoint_uses_native_signed_totals_for_every_customer(self):
        company = Mock(default_currency="AED")
        parties = [frappe._dict(name="C1", customer_group="G"),
                   frappe._dict(name="C2", customer_group="G")]
        report = Mock()
        # Native totals already include the unallocated payment and credit note.
        report.total_row_map = {"C1": {"outstanding": 22022.0}, "C2": {"outstanding": -25.5}}
        report.run.return_value = ([], [
            frappe._dict(party="C1", voucher_type="Sales Invoice", voucher_no="SI", outstanding=22222),
            frappe._dict(party="C1", voucher_type="Payment Entry", voucher_no="PE", outstanding=-200),
            frappe._dict(party="C2", voucher_type="Sales Invoice", voucher_no="SI2", outstanding=4.5),
            frappe._dict(party="C2", voucher_type="Sales Invoice", voucher_no="CN", outstanding=-30),
            {"party": "C2", "bold": 1, "outstanding": -25.5}, {},
        ])
        with patch.object(frappe, "has_permission", return_value=True), \
                patch.object(frappe, "get_doc", return_value=company), \
                patch.object(frappe, "get_list", return_value=parties), \
                patch.object(frappe, "get_all", return_value=["CN"]), \
                patch.object(service, "_credit_limits", return_value={"C1": 30000, "C2": 0}), \
                patch.object(service, "_CustomerReceivables", return_value=report) as native, \
                patch.object(service, "nowdate", return_value="2026-09-28"), \
                patch.object(service, "get_currency_precision", return_value=2):
            result = service.get_customer_credit_balances(["C1", "C2"], "Company")
        self.assertEqual(native.call_args.args[0]["party"], ["C1", "C2"])
        self.assertEqual(native.call_args.args[0]["company"], "Company")
        report.run.assert_called_once()
        first, second = result["data"]
        self.assertEqual(first["outstanding_amount"], 22022)
        self.assertEqual(first["remaining_credit_limit"], 7978)
        self.assertEqual(second["outstanding_amount"], -25.5)
        self.assertEqual(second["unused_credit_note_amount"], 30)
        self.assertEqual(second["remaining_credit_limit"], 25.5)

    def test_credit_limit_fallback_is_batched(self):
        parties = [frappe._dict(name="C1", customer_group="G1"),
                   frappe._dict(name="C2", customer_group="G1"),
                   frappe._dict(name="C3", customer_group="G2")]
        with patch.object(frappe, "get_all", side_effect=[
            [frappe._dict(parent="C1", credit_limit=100), frappe._dict(parent="C2", credit_limit=0)],
            [frappe._dict(parent="G1", credit_limit=200)],
        ]) as query:
            limits = service._credit_limits(parties, frappe._dict(name="Company", credit_limit=300))
        self.assertEqual(limits, {"C1": 100, "C2": 200, "C3": 300})
        self.assertEqual(query.call_count, 2)
        self.assertEqual(query.call_args.kwargs["filters"]["bypass_credit_limit_check"], 0)

    def test_accounting_permission_denied_before_queries(self):
        with patch.object(frappe, "has_permission", side_effect=[True, frappe.PermissionError]), \
                patch.object(frappe, "get_list") as query, patch.object(frappe, "get_all") as raw:
            with self.assertRaises(frappe.PermissionError):
                service.get_customer_credit_balances(["C1"], "Company")
            query.assert_not_called()
            raw.assert_not_called()

    def test_customer_permission_exclusion_stops_ledger_query(self):
        company = Mock(default_currency="AED")
        with patch.object(frappe, "has_permission", return_value=True), \
                patch.object(frappe, "get_doc", return_value=company), \
                patch.object(frappe, "get_list", return_value=[]) as query, \
                patch.object(service, "_CustomerReceivables") as ledger:
            result = service.get_customer_credit_balances(["HIDDEN"], "Company")
        company.check_permission.assert_called_once_with("read")
        self.assertEqual(result["data"], [])
        self.assertEqual(query.call_args.kwargs["filters"], {"name": ["in", ["HIDDEN"]]})
        ledger.assert_not_called()

    def test_company_permission_denied_before_customer_query(self):
        company = Mock()
        company.check_permission.side_effect = frappe.PermissionError
        with patch.object(frappe, "has_permission", return_value=True), \
                patch.object(frappe, "get_doc", return_value=company), \
                patch.object(frappe, "get_list") as query:
            with self.assertRaises(frappe.PermissionError):
                service.get_customer_credit_balances(["C1"], "Other Company")
        query.assert_not_called()

    def test_whitelisted_but_not_guest(self):
        self.assertIn(service.get_customer_credit_balances, frappe.whitelisted)
        self.assertNotIn(service.get_customer_credit_balances, frappe.guest_methods)
