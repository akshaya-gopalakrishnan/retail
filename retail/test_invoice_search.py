"""Invoice finder boundaries and permission regressions (no business writes)."""
import unittest
from unittest.mock import patch
from datetime import datetime

import frappe
from retail.invoice_search import date_windows, search_invoices


class TestInvoiceSearch(unittest.TestCase):
    def test_interval_boundaries(self):
        for start, end in (("2026-09-24 14:00:00", "2026-09-25 16:00:00"),
                           ("2026-09-25 14:00:00", "2026-09-25 16:00:00"),
                           (None, "2026-09-25 16:00:00"),
                           ("2026-09-24 14:00:00", None)):
            windows = date_windows(start, end)
            for value in ("2026-09-24 13:59:59", "2026-09-24 14:00:00", "2026-09-25 00:00:00",
                          "2026-09-25 14:00:00", "2026-09-25 16:00:00", "2026-09-25 16:00:01"):
                stamp = datetime.fromisoformat(value)
                matches = 0
                for window in windows:
                    ok = True
                    for field, op, boundary in window:
                        actual = stamp.date() if field == "posting_date" else stamp.time()
                        ok &= {"=": actual == boundary, ">": actual > boundary, "<": actual < boundary,
                               ">=": actual >= boundary, "<=": actual <= boundary}[op]
                    matches += bool(ok)
                expected = (not start or value >= start) and (not end or value <= end)
                self.assertEqual(matches, int(expected), (start, end, value))

    def test_invalid_range_and_empty_search(self):
        with self.assertRaises(frappe.ValidationError):
            date_windows("2026-09-25 16:00:00", "2026-09-25 14:00:00")
        with self.assertRaises(frappe.ValidationError):
            search_invoices({})

    def test_denied_invoice_type_never_queries(self):
        with patch("retail.invoice_search.frappe.has_permission", return_value=False), patch("retail.invoice_search.frappe.get_list") as query:
            with self.assertRaises(frappe.PermissionError):
                search_invoices({"bill_number": "000002", "invoice_type": "Sales Invoice"})
            self.assertFalse(any(call.args[0] in ("POS Invoice", "Sales Invoice")
                                 for call in query.call_args_list if call.args))

    def test_leading_zeros_and_combined_filters(self):
        with patch("retail.invoice_search.frappe.has_permission", return_value=True), patch("retail.invoice_search.frappe.get_meta") as meta, patch("retail.invoice_search.frappe.get_list", return_value=[]) as query:
            meta.return_value.has_field.return_value = True
            search_invoices({"invoice_type": "POS Invoice", "bill_number": "000002",
                "customer": "CUST-1", "cashier": "EMP-1", "counter": "CTR-1", "branch": "Branch 1"})
            args = query.call_args.kwargs
            self.assertIn(["pos_bill_no", "=", "000002"], args["or_filters"])
            for field, value in (("customer", "CUST-1"), ("pos_cashier_employee", "EMP-1"),
                                 ("pos_counter", "CTR-1"), ("pos_branch", "Branch 1")):
                self.assertIn([field, "=", value], args["filters"])
            self.assertNotIn("ignore_permissions", args)

    def test_offline_sale_keeps_original_posting_timestamp(self):
        from retail.api.pos_sync import _base_invoice
        from erpnext.utilities.transaction_base import TransactionBase
        payload = frappe._dict(customer="CUST-1", external_pos_reference="offline-ref",
            posting_date="2026-09-20", posting_time="14:25:30", pos_bill_no="000123")
        counter = frappe._dict(company="Company", branch="Branch", name="Counter")
        doc = frappe._dict(flags=frappe._dict())
        with patch("retail.api.pos_sync.frappe.new_doc", return_value=doc), \
             patch("retail.pos_external_refs.resolve", return_value=payload), \
             patch("retail.pos_completed_sale.completed_session", return_value=(None, None, None)), \
             patch("retail.api.pos_sync._legacy_counter_name", return_value=None):
            invoice = _base_invoice(payload, counter)
        TransactionBase.validate_posting_time(invoice)
        self.assertEqual(invoice.posting_date, "2026-09-20")
        self.assertEqual(invoice.posting_time, "14:25:30")
