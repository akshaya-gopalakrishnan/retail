import unittest
from unittest.mock import patch
import frappe
from retail.pos_delivery import append_charge, set_snapshots
from retail.pos_completed_sale import restore


class TestPOSDelivery(unittest.TestCase):
    def test_delivery_preserves_line_values_and_totals(self):
        for is_return in (0, 1):
            for explicit_total in (False, True):
                with self.subTest(is_return=is_return, explicit_total=explicit_total):
                    sign = -1 if is_return else 1
                    payload = dict(delivery_charge=5, cashier_name="Ahmed", customer_name="Mohammed",
                        customer_address="Dubai", delivery_person="E-5", delivery_person_name="Abdul",
                        vat_amount=.95, items=[dict(qty=1, amount=20, net_amount=19.05,
                            rate=20, rate_includes_vat=1, vat_rate=5, vat_amount=.95)])
                    if explicit_total:
                        payload['grand_total'] = 25
                    doc = frappe.get_doc(dict(doctype="POS Invoice", company="Test", is_return=is_return,
                        pos_sync_source="Offline POS", custom_pos_completed_payload=frappe.as_json(payload),
                        conversion_rate=1, items=[dict(item_code="I-66", qty=sign, amount=sign*19.05,
                            net_amount=sign*19.05, income_account="Sales")], payments=[dict(amount=sign*25)]))
                    set_snapshots(doc, payload)
                    with patch("retail.pos_delivery.frappe.get_cached_value", side_effect=lambda dt, *a: "Sales" if dt == "Company" else "Test"):
                        append_charge(doc, payload)
                    with patch("retail.pos_item_names.restore_item_names"), \
                         patch("retail.pos_completed_sale.frappe.get_cached_value", return_value=1), \
                         patch("retail.pos_tax_breakup.update"), patch.object(doc, "set_total_in_words"):
                        restore(doc)
                    self.assertAlmostEqual(doc.grand_total, sign*25)
                    self.assertAlmostEqual(doc.net_total, sign*19.05)
                    self.assertAlmostEqual(doc.total_taxes_and_charges, sign*5.95)
                    self.assertAlmostEqual(doc.items[0].net_amount, sign*19.05)
                    self.assertEqual(doc.custom_pos_customer_address, "Dubai")
                    self.assertEqual(doc.custom_pos_delivery_person, "E-5")
                    self.assertEqual(doc.taxes[0].account_head, "Sales")
                    self.assertEqual(doc.taxes[0].tax_amount, sign*5)
                    self.assertFalse(doc.flags.get('pos_mismatch_reasons'))

    def test_legacy_payload_adds_no_charge(self):
        doc = frappe.get_doc(dict(doctype="POS Invoice", taxes=[]))
        with patch("retail.pos_delivery.frappe.get_cached_value") as lookup:
            append_charge(doc, {})
        lookup.assert_not_called()
        self.assertFalse(doc.taxes)
