"""Database-free regression checks for advisory accounting reconciliation."""
import unittest
from unittest.mock import Mock, patch

import frappe

from retail.pos_realtime import post_invoice
from retail.pos_rate_audit import create_for_pos_invoice


class TestPOSAccountingAudit(unittest.TestCase):
    def check_posting(self, accounting_total, outstanding, write_off, pos_total=100.0):
        receipt = frappe._dict(
            name="POS-75", docstatus=1, company="Company", customer="Customer",
            posting_date="2026-11-26", posting_time="13:31:00", due_date="2026-11-26",
            grand_total=pos_total, net_total=pos_total, total_taxes_and_charges=0,
            paid_amount=0, outstanding_amount=pos_total, flags=frappe._dict(), items=[],
        )
        accounting = frappe._dict(
            name="PSI-75", grand_total=accounting_total, net_total=accounting_total,
            total_taxes_and_charges=0, paid_amount=0,
            outstanding_amount=outstanding, write_off_amount=write_off,
            precision=lambda field: 2,
        )
        merge = Mock()
        db = Mock()
        db.get_value.side_effect = [None, "PSI-75"]
        db.exists.return_value = False
        with patch.object(frappe, "db", db), \
                patch.object(frappe, "new_doc", return_value=merge), \
                patch.object(frappe, "get_doc", return_value=accounting), \
                patch("retail.pos_realtime.refresh_closed_reconciliation"), \
                patch.object(frappe, "get_system_settings", return_value="Banker's Rounding"):
            self.assertEqual(post_invoice(receipt), "PSI-75")
        merge.submit.assert_called_once()
        self.assertEqual(receipt.status, "Consolidated")
        self.assertEqual(receipt.consolidated_invoice, "PSI-75")
        self.assertEqual(receipt.outstanding_amount, pos_total)
        with patch("retail.pos_rate_audit.insert_audit", return_value="AUDIT-1") as insert:
            rows = create_for_pos_invoice(receipt, {"items": []})
        self.assertEqual(len(rows), len(receipt.flags.get("pos_mismatch_reasons") or []))
        return [call.args[1]["reason"] for call in insert.call_args_list]

    def test_one_cent_total_difference_posts_and_creates_audit(self):
        reasons = self.check_posting(99.99, 99.99, 0)
        self.assertEqual(len(reasons), 3)
        self.assertTrue(any("grand_total" in r and "difference=-0.01" in r for r in reasons))

    def test_automatic_write_off_posts_and_creates_audit(self):
        reasons = self.check_posting(100.0, 0, 100.0)
        self.assertEqual(len(reasons), 1)
        self.assertIn("outstanding_amount", reasons[0])
        self.assertIn("accounting write_off_amount=100.0", reasons[0])

    def test_matching_accounting_creates_no_mismatch_audit(self):
        self.assertEqual(self.check_posting(100.0, 100.0, 0), [])

    def test_demo_credit_sale_write_off(self):
        reasons = self.check_posting(1.25, 0, 1.25, pos_total=1.25)
        self.assertEqual(len(reasons), 1)
        self.assertIn("POS=1.25, accounting=0.0", reasons[0])
        self.assertIn("accounting write_off_amount=1.25", reasons[0])
