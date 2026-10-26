"""Voucher snapshots on the existing POS promotion endpoint."""
import unittest
from datetime import datetime
from unittest.mock import patch

import frappe
from retail.promotions import pos_download


class TestPOSVoucherDownload(unittest.TestCase):
    def snapshot(self, entries, batches=None, restrictions=None):
        counter = frappe._dict(company="nesto", warehouse="Stores - N")
        queries = {}
        def query(doctype, **kwargs):
            queries[doctype] = kwargs
            return {"Voucher Card Batch": batches or [], "Gift Voucher Ledger": entries,
                    "Voucher Card Restriction": restrictions or []}[doctype]
        with patch.object(frappe, "get_all", side_effect=query), \
                patch.object(frappe, "get_cached_value", return_value="AED"), \
                patch.object(pos_download, "matching_item_groups", return_value=["Drinks", "Juice"]), \
                patch("retail.api.gift_vouchers.nowdate", return_value="2026-10-22"), \
                patch("retail.api.gift_vouchers.now_datetime", return_value=datetime(2026, 10, 22, 12)):
            result = pos_download._voucher_snapshot(counter)
        return result, queries

    def voucher(self, **kwargs):
        return frappe._dict(dict(name="ABCDE", voucher_code="ABCDE", company="nesto",
            warehouse=None, voucher_amount=100, balance_amount=40, status="Partially Used",
            valid_from="2026-10-20", expiry_date="2026-10-25", voucher_card_batch="BATCH",
            use_redemption_hours=1, active_from_time="10:00:00", active_to_time="11:00:00",
            issued_against="INV-1", customer="CUSTOMER", card_number=1, **kwargs))

    def test_saved_balances_dates_links_and_restrictions_are_preserved(self):
        batch = frappe._dict(name="BATCH", company="nesto", all_products=0,
            use_redemption_hours=1, active_from_time="10:00:00", active_to_time="11:00:00")
        restriction = frappe._dict(parent="BATCH", idx=1, item_group="Drinks", brand=None, item_code=None)
        result, queries = self.snapshot([self.voucher()], [batch], [restriction])
        row = result["gift_voucher_ledger"][0]
        self.assertEqual((row.balance_amount, row.voucher_amount), (40, 100))
        self.assertEqual((row.current_status, row.valid), ("Partially Used", True))
        self.assertEqual(row.issued_against, "INV-1")
        self.assertEqual(row.customer, "CUSTOMER")
        self.assertEqual(row.eligibility[0]["matching_item_groups"], ["Drinks", "Juice"])
        self.assertTrue(row.use_activation_times)
        self.assertEqual(row.active_to_time, "11:00:00")
        self.assertEqual(queries["Gift Voucher Ledger"]["filters"], {"company": "nesto"})
        self.assertEqual(queries["Gift Voucher Ledger"]["or_filters"],
            [["warehouse", "=", "Stores - N"], ["warehouse", "is", "not set"]])
        self.assertNotIn("modified", queries["Voucher Card Batch"]["filters"])
        self.assertEqual(result["voucher_snapshot"]["mode"], "full")

    def test_blocked_archived_expired_and_draft_remain_in_snapshot(self):
        rows = []
        for changes in ({"card_blocked": 1}, {"card_archived": 1},
                        {"expiry_date": "2026-10-21"}, {"status": "Draft"}):
            row = self.voucher()
            row.update(changes)
            rows.append(row)
        result, _ = self.snapshot(rows)
        self.assertEqual([row["reason"] for row in result["gift_voucher_ledger"]],
                         ["Blocked", "Archived", "Expired", "Draft"])
        self.assertTrue(all(not row["valid"] for row in result["gift_voucher_ledger"]))

    def test_legacy_voucher_and_empty_replacement(self):
        row = self.voucher()
        row.update(voucher_card_batch=None, use_redemption_hours=0, status="Unused", balance_amount=100)
        result, _ = self.snapshot([row])
        row = result["gift_voucher_ledger"][0]
        self.assertEqual(row.voucher_kind, "Promotion Voucher")
        self.assertIsNone(row.active_from_time)
        self.assertEqual(row.currency, "AED")
        empty, _ = self.snapshot([])
        self.assertEqual(empty["gift_voucher_ledger"], [])
        self.assertEqual(empty["voucher_card_batches"], [])


def run_tests():
    from retail.tests.test_pos_combined_promotions import TestPOSCombinedPromotions
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
        for cls in (TestPOSVoucherDownload, TestPOSCombinedPromotions))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise AssertionError("POS voucher download tests failed")
    return {"tests": result.testsRun, "passed": True}
