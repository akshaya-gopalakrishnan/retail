import unittest
from unittest.mock import patch

import frappe

from retail.pos_transaction_display import payload_transaction_type, transaction_type


class TestPOSSettlementDisplay(unittest.TestCase):
    def test_payload_labels(self):
        cases = [
            ("POS Sale", {"grand_total": 15, "payments": [{"mode": "Cash", "amount": 15}]}, "POS Invoice"),
            ("POS Sale", {"grand_total": 15, "credit_sale_amount": 15, "payments": []}, "Credit Sale"),
            ("POS Sale", {"grand_total": 15, "credit_sale_amount": 0,
                "credit_note_redemptions": [{"amount": 15}]}, "Credit Note Redeemed"),
            ("POS Sale", {"grand_total": 20, "credit_sale_amount": 5,
                "credit_note_redemptions": [{"amount": 15}]}, "Credit Sale + Credit Note Redeemed"),
            ("POS Return", {"return_settlement_type": "Reusable Customer Credit", "payments": []}, "Credit Note Issued"),
            ("POS Return", {"return_settlement_type": "Original Debt Reduction", "payments": []}, "Credit Note Reduced"),
            ("POS Return", {"return_settlement_type": "Cash Refund", "payments": [{"mode": "Cash", "amount": 15}]}, "Return"),
            ("POS Sale", {"grand_total": 15, "payments": [{"mode": "Credit Note", "amount": 15}]}, "Credit Note Redeemed"),
            ("Shift Closing", {}, "Shift Closing"),
        ]
        with patch("retail.pos_transaction_display.settlement_label", return_value=None):
            for kind, payload, expected in cases:
                with self.subTest(kind=kind, expected=expected):
                    self.assertEqual(payload_transaction_type(kind, payload), expected)

    def test_recorded_settlement_overrides_unpaid_tender_inference(self):
        doc = frappe._dict(external_pos_reference="receipt", grand_total=15, paid_amount=0)
        with patch("retail.pos_transaction_display.settlement_label", return_value="Credit Note Redeemed"):
            self.assertEqual(transaction_type(doc), "Credit Note Redeemed")

    def test_original_credit_sale_label_survives_later_payment(self):
        doc = frappe._dict(external_pos_reference="receipt", grand_total=15, paid_amount=15)
        with patch("retail.pos_transaction_display.settlement_label", return_value="Credit Sale"):
            self.assertEqual(transaction_type(doc), "Credit Sale")
