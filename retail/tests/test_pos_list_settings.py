"""Regression tests for POS list summaries and single operation logging."""
import unittest
from unittest.mock import patch, MagicMock

import frappe
from retail import pos_list_settings as settings
from retail.api import pos_sync


class TestPOSListSettings(unittest.TestCase):
    def test_opening_cash_excludes_cards(self):
        doc = frappe._dict(balance_details=[
            frappe._dict(mode_of_payment="Cash", opening_amount=100),
            frappe._dict(mode_of_payment="Card", opening_amount=500),
        ])
        with patch.object(frappe, "get_all", return_value=["Cash"]):
            settings.set_opening_summary(doc)
        self.assertEqual(doc.custom_opening_cash, 100)

    def test_closing_amount_includes_all_counted_tenders(self):
        doc = frappe._dict(payment_reconciliation=[
            frappe._dict(closing_amount=100), frappe._dict(closing_amount=250),
        ])
        settings.set_closing_summary(doc)
        self.assertEqual(doc.custom_closing_amount, 350)

    def test_log_uses_business_date_and_resolves_counter_code(self):
        doc = frappe._dict(request_json='{"payload":{"business_date":"2026-09-23",'
            '"counter_code":"counter01","branch":"Branch A"}}')
        with patch.object(frappe, "get_all", return_value=["Counter 01"]) as query:
            settings.set_log_metadata(doc)
        self.assertEqual(str(doc.posting_date), "2026-09-23")
        self.assertEqual(doc.pos_counter, "Counter 01")
        self.assertEqual(query.call_args.kwargs['filters'],
            {"counter_code": "counter01", "branch": "Branch A"})

    def test_receipted_operations_do_not_write_a_second_log(self):
        for kind in ("Shift Opening", "Shift Closing", "Cash Movement", "Sales Invoice", "Return"):
            for duplicate in (False, True):
                result = {"status": "Success", "duplicate": duplicate}
                with self.subTest(kind=kind, duplicate=duplicate), \
                        patch('retail.pos_external_refs.authorize', return_value=frappe._dict(company='Company', name='Counter')), \
                        patch('retail.pos_operations.execute', return_value=result), \
                        patch.object(pos_sync, '_sync_log') as log:
                    self.assertEqual(pos_sync._run(kind, {'external_pos_reference': 'reference'}, lambda: result), result)
                    log.assert_not_called()

    def test_opening_end_date_tracks_submitted_closing_and_cancellation(self):
        doc = frappe._dict(pos_opening_entry='Opening 1')
        for end, expected in [('2026-09-24 17:30:00', '2026-09-24'), (None, None)]:
            with self.subTest(end=end), patch.object(frappe, 'db', new=MagicMock()) as db:
                db.get_value.return_value = end
                settings.update_opening_end_date(doc)
                value = db.set_value.call_args.args[3]
                self.assertEqual(str(value) if value else None, expected)
