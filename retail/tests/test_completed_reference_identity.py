"""Completed-sale references must resolve to the session's actual shift."""
import copy
import unittest
from unittest.mock import patch

import frappe
from retail.pos_external_refs import resolve_completed


class TestCompletedReferenceIdentity(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "external_shift_reference": "Sharjah-Counter-01-SHIFT",
            "external_session_reference": "Sharjah-Counter-01-SESSION",
            "branch": "Sharjah", "counter_code": "Counter-01",
            "pos_terminal_id": "Terminal-01", "cashier_employee": "E-1",
        }
        self.shift = frappe._dict(name="PSH-1", branch="Sharjah", cashier_employee="E-1",
                                  external_shift_reference="Sharjah-COUNTER-01-SHIFT")
        self.session = frappe._dict(name="PCS-1", branch="Sharjah", cashier_employee="E-1",
            counter_code="Counter-01", terminal_id="Terminal-01", cashier_shift="PSH-1",
            pos_opening_entry="POE-1")

    def resolve(self):
        def lookup(doctype, filters, field):
            reference = next(iter(filters.values()))
            expected = self.payload["external_shift_reference" if doctype == "POS Cashier Shift"
                                    else "external_session_reference"]
            if reference.casefold() != expected.casefold():
                return None
            return "PSH-1" if doctype == "POS Cashier Shift" else "PCS-1"
        with patch("retail.api.pos_sync._cashier_employee", return_value="E-1"), \
             patch.object(frappe.db, "get_value", side_effect=lookup), \
             patch.object(frappe, "get_doc", side_effect=lambda dt, name:
                          self.shift if dt == "POS Cashier Shift" else self.session):
            return resolve_completed(self.payload)

    def test_case_variant_keeps_original_payload_and_resolves_same_shift(self):
        before = copy.deepcopy(self.payload)
        result = self.resolve()
        self.assertEqual(result.cashier_shift, "PSH-1")
        self.assertEqual(result.counter_session, "PCS-1")
        self.assertEqual(self.payload, before)
        self.assertEqual(result.external_shift_reference, before["external_shift_reference"])

    def test_different_shift_is_rejected(self):
        self.session.cashier_shift = "PSH-2"
        with self.assertRaisesRegex(frappe.ValidationError, "another shift"):
            self.resolve()

    def test_other_identity_checks_remain_enforced(self):
        for field, value, error in (
            ("cashier_employee", "E-2", "Cashier"),
            ("branch", "Dubai", "another branch"),
            ("counter_code", "Counter-02", "another counter"),
            ("terminal_id", "Terminal-02", "another terminal"),
        ):
            with self.subTest(field=field):
                original = self.session[field]
                self.session[field] = value
                try:
                    with self.assertRaisesRegex(frappe.ValidationError, error):
                        self.resolve()
                finally:
                    self.session[field] = original
