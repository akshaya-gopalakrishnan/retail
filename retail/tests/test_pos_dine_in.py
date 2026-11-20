import unittest
from unittest.mock import patch
import frappe
from retail.pos_dine_in import from_payload


class TestPOSDineIn(unittest.TestCase):
    def test_omitted_defaults_to_dine_in_but_null_and_blank_have_no_label(self):
        self.assertEqual(from_payload({}), 1)
        for value in (None, "", " "):
            self.assertEqual(from_payload({"is_dine_in": value}), 0)

    def test_explicit_false_is_not_lost_to_truthy_default(self):
        for value in (False, 0):
            self.assertEqual(from_payload({"is_dine_in": value}), 0)
        for value in (True, 1):
            self.assertEqual(from_payload({"is_dine_in": value}), 1)

    def test_invalid_values_are_rejected(self):
        for value in ("false", "true", "0", 2, [], {}, 0.0):
            with self.subTest(value=value), patch("retail.pos_dine_in.frappe.throw", side_effect=frappe.ValidationError):
                with self.assertRaises(frappe.ValidationError):
                    from_payload({"is_dine_in": value})

    def test_invoice_builder_stores_default_true_and_explicit_false(self):
        from retail.api import pos_sync
        counter = frappe._dict(default_customer="Customer", company="Company", warehouse="Warehouse",
            branch="Branch", name="Counter", terminal_id="Terminal", cost_center="Cost", pos_profile="Profile")
        for values, expected in (({}, 1), ({"is_dine_in": True}, 1), ({"is_dine_in": False}, 0), ({"is_dine_in": None}, 0), ({"is_dine_in": ""}, 0)):
            payload = frappe._dict(customer="Customer", external_pos_reference="ref", posting_date="2026-11-17", **values)
            doc = frappe._dict(flags=frappe._dict())
            with self.subTest(values=values), \
                 patch.object(pos_sync.frappe, "new_doc", return_value=doc), \
                 patch("retail.pos_external_refs.resolve_completed", side_effect=lambda data: data), \
                 patch("retail.pos_mixed_payments.set_loyalty"), \
                 patch("retail.pos_completed_sale.completed_session", return_value=(None, None, None)), \
                 patch.object(pos_sync, "_legacy_counter_name", return_value=None), \
                 patch.object(pos_sync, "now_datetime", return_value="2026-11-17 12:00:00"):
                result = pos_sync._base_invoice(payload, counter)
            self.assertEqual(result.custom_is_dine_in, expected)
            self.assertEqual(frappe.parse_json(result.custom_pos_completed_payload), dict(payload))
