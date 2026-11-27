"""Operation approval checks without reading or writing any site database."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from retail import backend_sales_admin as policy


class Doc(SimpleNamespace):
    def get(self, key):
        return getattr(self, key, None)

    def get_doc_before_save(self):
        return None


class TestSalesApproval(unittest.TestCase):
    def setUp(self):
        rounding = patch.object(frappe, "get_system_settings", return_value="Banker's Rounding")
        rounding.start()
        self.addCleanup(rounding.stop)
        self.translations = patch.object(policy, "_", side_effect=lambda text: text)
        self.translations.start()
        self.addCleanup(self.translations.stop)
        self.doc = Doc(name="new-sales-invoice-1", items=[], is_return=1)

    def test_automatic_packing_discount_uses_native_rounded_amount(self):
        row = SimpleNamespace(precision=lambda field: 2)
        for listed, discount, selling in [(1500, 750, 750), (499.95, 249.975, 249.97),
                                          (666.67, 333.335, 333.33), (333.33, 166.665, 166.67)]:
            with self.subTest(listed=listed):
                values = dict(rate=0, price_list_rate=listed, discount_amount=discount,
                              discount_percentage=50, pricing_rules='["automatic-rule"]')
                self.assertEqual(policy.automatic_row_rate(values, row), selling)

    def test_automatic_packing_margin_and_explicit_rule_rate(self):
        row = SimpleNamespace(precision=lambda field: 2)
        self.assertEqual(policy.automatic_row_rate(dict(price_list_rate=100, margin_type="Percentage",
                         margin_rate_or_amount=10, discount_percentage=5), row), 104.5)
        self.assertEqual(policy.automatic_row_rate(dict(rate=75, price_list_rate=100), row), 75)

    def test_administrator_requires_return_approval(self):
        with patch.object(policy, "approved", return_value=False), patch.object(policy, "allowed", return_value=True), patch.object(policy, "deny", side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):
                policy.validate(self.doc)

    def test_discount_requires_approval(self):
        self.doc.is_return = 0
        self.doc.discount_amount = 5
        with patch.object(policy, "approved", return_value=False), patch.object(policy, "deny", side_effect=frappe.PermissionError):
            with self.assertRaises(frappe.PermissionError):
                policy.validate(self.doc)

    def test_approved_return(self):
        with patch.object(policy, "approved", return_value=True):
            policy.validate(self.doc)

    def test_pos_and_van_unchanged(self):
        for field in ("is_pos", "is_consolidated", "custom_is_van_sale"):
            with self.subTest(field=field):
                setattr(self.doc, field, 1)
                with patch.object(policy, "approved", side_effect=AssertionError("Approval must not run")):
                    policy.validate(self.doc)
                setattr(self.doc, field, 0)

    def test_grant_bound_to_actor_document_values_and_active_approver(self):
        self.doc._retail_sales_approval = "opaque-token"
        grant = {"actor": "cashier@example.com", "approver": "manager@example.com",
                 "document": self.doc.name, "fingerprint": policy.fingerprint(self.doc),
                 "header": policy.header_snapshot(self.doc), "rows": []}
        cache = SimpleNamespace(get_value=lambda key: grant)
        db = SimpleNamespace(get_value=lambda *args: 1)
        with patch.object(frappe, "cache", cache), patch.object(frappe, "db", db), patch.object(frappe, "session", SimpleNamespace(user=grant["actor"])), patch.object(frappe, "get_roles", return_value=["Admin"]):
            self.assertTrue(policy.approved(self.doc))
            self.doc.discount_amount = 10
            self.assertFalse(policy.approved(self.doc))
            del self.doc.discount_amount
            self.doc.name = "another-invoice"
            self.assertFalse(policy.approved(self.doc))
            self.doc.name = grant["document"]
            grant["actor"] = "someone-else"
            self.assertFalse(policy.approved(self.doc))

    def test_missing_or_expired_grant(self):
        self.assertFalse(policy.approved(self.doc))
        self.doc._retail_sales_approval = "expired-token"
        with patch.object(frappe, "cache", SimpleNamespace(get_value=lambda key: None)):
            self.assertFalse(policy.approved(self.doc))

    def test_authorization_does_not_switch_session_or_store_password(self):
        captured = {}
        cache = SimpleNamespace(set_value=lambda key, value, **kwargs: captured.update(value))
        with patch.object(policy, "approval_document", return_value=self.doc), patch("frappe.utils.password.check_password", return_value="manager@example.com"), patch.object(frappe, "cache", cache), patch.object(frappe, "db", SimpleNamespace(get_value=lambda *args: 1)), patch.object(frappe, "session", SimpleNamespace(user="cashier@example.com")), patch.object(frappe, "request", None), patch.object(frappe, "get_roles", return_value=["Customer Administrator"]):
            with patch.object(frappe.local, "flags", frappe._dict(), create=True):
                token = policy.authorize({}, "manager@example.com", "test-only-not-a-real-password")
            self.assertTrue(token)
            self.assertEqual(frappe.session.user, "cashier@example.com")
            self.assertEqual(captured["approver"], "manager@example.com")
            self.assertNotIn("password", captured)

    def test_existing_administrator_profile_role_can_approve(self):
        with patch.object(frappe, "get_roles", return_value=["Customer Administrator", "Sales Manager"]):
            self.assertTrue(policy.can_approve("manager@example.com"))

    def test_access_or_cashier_roles_alone_cannot_approve(self):
        for role in ("Super Admin", "System Manager", "Sales Manager", "POS Manager"):
            with self.subTest(role=role), patch.object(frappe, "get_roles", return_value=[role]):
                self.assertFalse(policy.can_approve("cashier@example.com"))

    def test_approved_rows_survive_new_rows_and_native_quantity_changes(self):
        row = Doc(item_code="I-3", uom="Nos", rate=20, qty=1)
        self.doc.items = [row]
        self.doc._retail_sales_approval = ["row-token"]
        grant = {"actor": "cashier@example.com", "approver": "manager@example.com", "document": self.doc.name,
                 "header": policy.header_snapshot(self.doc), "rows": [policy.row_snapshot(row)]}
        with patch.object(frappe, "cache", SimpleNamespace(get_value=lambda key: grant)), patch.object(frappe, "db", SimpleNamespace(get_value=lambda *args: 1)), patch.object(frappe, "session", SimpleNamespace(user=grant["actor"])), patch.object(policy, "can_approve", return_value=True):
            self.assertTrue(policy.approved(self.doc))
            row.qty = 3
            self.assertTrue(policy.approved(self.doc))
            self.doc.items.append(Doc(item_code="I-4", uom="Nos", rate=10))
            self.assertTrue(policy.approved_row(self.doc, row))
            self.assertFalse(policy.approved(self.doc))
            row.rate = 21
            self.assertFalse(policy.approved_row(self.doc, row))

    def test_new_invoice_naming_keeps_approved_prices_valid(self):
        self.doc.flags = frappe._dict()
        self.doc._retail_sales_approval = "new-token"
        grant = {"actor": "cashier@example.com", "approver": "manager@example.com", "document": self.doc.name,
                 "header": policy.header_snapshot(self.doc), "rows": []}
        policy.before_insert(self.doc)
        self.doc.name = "SI-new-permanent-name"
        with patch.object(frappe, "cache", SimpleNamespace(get_value=lambda key: grant)), patch.object(frappe, "db", SimpleNamespace(get_value=lambda *args: 1)), patch.object(frappe, "session", SimpleNamespace(user=grant["actor"])), patch.object(policy, "can_approve", return_value=True):
            self.assertTrue(policy.approved(self.doc))

    def test_native_discount_representation_does_not_revoke_approved_rate(self):
        row = Doc(item_code="I-93", uom="Kg", rate=15.29, price_list_rate=14.29,
                  discount_amount=0, margin_rate_or_amount=1)
        approved = policy.row_snapshot(row)
        row.discount_amount = -1
        row.margin_type = "Amount"
        self.assertEqual(policy.row_snapshot(row), approved)
        row.rate = 16
        self.assertNotEqual(policy.row_snapshot(row), approved)

    def test_desk_cleared_new_name_uses_native_localname(self):
        self.doc.flags = frappe._dict()
        self.doc.localname = self.doc.name
        self.doc.name = None
        policy.before_insert(self.doc)
        self.assertEqual(self.doc.flags.retail_approval_original_name, self.doc.localname)
