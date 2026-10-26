import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe

from retail.pos_transaction_display import payload_transaction_type, transaction_type


class TestPOSSettlementDisplay(unittest.TestCase):
    def test_legacy_sale_operation_uses_posted_return(self):
        payload = {"external_pos_reference": "legacy-sale", "grand_total": -63,
            "payments": [{"mode": "Cash", "amount": -63}]}
        original = dict(payload)
        db = SimpleNamespace(get_value=Mock(return_value="POS-44"))
        with patch("retail.pos_transaction_display.settlement_label", return_value=None), \
                patch.object(frappe, "db", db):
            self.assertEqual(payload_transaction_type("Sales Invoice", payload), "Return")
        self.assertEqual(payload, original)
        db.get_value.assert_called_once_with("POS Invoice", {
            "external_pos_reference": "legacy-sale", "is_return": 1}, "name")

    def test_posted_return_preserves_recorded_credit_note_type(self):
        for label in ("Credit Note Issued", "Credit Note Reduced"):
            with self.subTest(label=label), \
                    patch("retail.pos_transaction_display.settlement_label", return_value=label):
                self.assertEqual(payload_transaction_type("Sales Invoice", {
                    "external_pos_reference": "legacy-sale"}), label)

    def test_normal_sale_reference_keeps_sale_label(self):
        db = SimpleNamespace(get_value=Mock(return_value=None))
        with patch("retail.pos_transaction_display.settlement_label", return_value=None), \
                patch.object(frappe, "db", db):
            self.assertEqual(payload_transaction_type("Sales Invoice", {
                "external_pos_reference": "sale", "grand_total": 63,
                "payments": [{"mode": "Cash", "amount": 63}]}), "POS Invoice")

    def test_referenced_sale_tenders_without_posted_return_are_unchanged(self):
        cases = [
            ({"payments": [{"mode": "Cash", "amount": 20}]}, "POS Invoice"),
            ({"credit_sale_amount": 20}, "Credit Sale"),
            ({"credit_sale_amount": 0, "credit_note_redemptions": [{"amount": 20}]},
                "Credit Note Redeemed"),
            ({"credit_sale_amount": 5, "credit_note_redemptions": [{"amount": 15}]},
                "Credit Sale + Credit Note Redeemed"),
        ]
        db = SimpleNamespace(get_value=Mock(return_value=None))
        with patch("retail.pos_transaction_display.settlement_label", return_value=None), \
                patch.object(frappe, "db", db):
            for kind in ("POS Sale", "Sales Invoice", "Credit Sales Invoice"):
                for tender, label in cases:
                    with self.subTest(kind=kind, label=label):
                        payload = {"external_pos_reference": "sale", "grand_total": 20, **tender}
                        self.assertEqual(payload_transaction_type(kind, payload), label)

    def test_explicit_return_types_do_not_use_legacy_sale_fallback(self):
        cases = [("Cash Refund", "Return"), ("Card Refund", "Return"),
            ("Reusable Customer Credit", "Credit Note Issued"),
            ("Original Debt Reduction", "Credit Note Reduced")]
        db = SimpleNamespace(get_value=Mock(side_effect=AssertionError("Unexpected legacy lookup")))
        with patch("retail.pos_transaction_display.settlement_label", return_value=None), \
                patch.object(frappe, "db", db):
            for kind in ("POS Return", "Return"):
                for settlement, label in cases:
                    with self.subTest(kind=kind, settlement=settlement):
                        self.assertEqual(payload_transaction_type(kind, {
                            "external_pos_reference": "return",
                            "return_settlement_type": settlement}), label)

    def test_upgrade_repairs_only_return_display_metadata(self):
        from retail.patches.repair_pos_return_type_labels import execute

        rows = [
            frappe._dict(name="POS-41", is_return=1, external_pos_reference="legacy",
                custom_pos_transaction_type="POS Invoice"),
            frappe._dict(name="POS-101", is_return=1, external_pos_reference="credit",
                custom_pos_transaction_type="Credit Note Issued"),
            frappe._dict(name="manual", is_return=1, external_pos_reference=None,
                custom_pos_transaction_type="Return"),
        ]
        db = SimpleNamespace(set_value=Mock())
        def get_all(doctype, **kwargs):
            if doctype == "POS Invoice":
                self.assertEqual(kwargs["filters"], {"is_return": 1})
                return rows
            self.assertEqual(doctype, "POS Sync Log")
            reference = kwargs["filters"]["external_reference"]
            return ["LOG-" + reference]

        with patch.object(frappe, "db", db), patch.object(frappe, "get_all", side_effect=get_all), \
                patch("retail.pos_transaction_display.settlement_label",
                    side_effect=lambda ref: "Credit Note Issued" if ref == "credit" else None):
            execute()
        self.assertEqual(db.set_value.call_args_list, [
            unittest.mock.call("POS Invoice", "POS-41", "custom_pos_transaction_type",
                "Return", update_modified=False),
            unittest.mock.call("POS Sync Log", "LOG-legacy", "custom_pos_transaction_type",
                "Return", update_modified=False),
            unittest.mock.call("POS Sync Log", "LOG-credit", "custom_pos_transaction_type",
                "Credit Note Issued", update_modified=False),
        ])

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
