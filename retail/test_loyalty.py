"""Ledger and accounting integration coverage for Retail Sales Invoice loyalty."""
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today
from retail import loyalty


class TestRetailLoyalty(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.company = frappe.get_doc("Company", frappe.get_all("Company", pluck="name", limit=1)[0])
        self.expense = self.company.default_expense_account or frappe.get_all("Account", filters={
            "company": self.company.name, "root_type": "Expense", "is_group": 0}, pluck="name", limit=1)[0]
        self.program = frappe.get_doc({
            "doctype": "Loyalty Program", "loyalty_program_name": "Retail Test " + frappe.generate_hash(length=8),
            "loyalty_program_type": "Single Tier Program", "from_date": add_days(today(), -30),
            "conversion_factor": 1, "expiry_duration": 365, "company": self.company.name,
            "expense_account": self.expense, "cost_center": self.company.cost_center,
            "collection_rules": [{"tier_name": "Base", "min_spent": 0, "collection_factor": 10}],
        }).insert()
        self.customer = frappe.get_doc({
            "doctype": "Customer", "customer_name": "Retail Loyalty " + frappe.generate_hash(length=8),
            "customer_type": "Individual", "customer_group": frappe.get_all("Customer Group", filters={"is_group": 0}, pluck="name", limit=1)[0],
            "territory": "All Territories", "loyalty_program": self.program.name,
        }).insert()
        self.item = frappe.get_doc({
            "doctype": "Item", "item_code": "RLOY-" + frappe.generate_hash(length=8),
            "item_name": "Retail loyalty test service", "item_group": frappe.get_all("Item Group", filters={"is_group": 0}, pluck="name", limit=1)[0],
            "stock_uom": "Nos", "is_stock_item": 0,
        }).insert()

    def invoice(self, total=1000, points=0, submit=True, original=None, currency=None, conversion_rate=1):
        doc = frappe.get_doc({
            "doctype": "Sales Invoice", "company": self.company.name, "customer": self.customer.name,
            "posting_date": today(), "due_date": today(), "currency": currency or self.company.default_currency,
            "conversion_rate": conversion_rate, "disable_rounded_total": 1, "loyalty_program": self.program.name,
            "redeem_loyalty_points": int(bool(points)), "loyalty_points": points,
            "is_return": int(bool(original)), "return_against": original.name if original else None,
            "items": [{"item_code": self.item.name, "qty": -abs(total) if original else abs(total),
                       "rate": 1, "income_account": self.company.default_income_account,
                       "cost_center": self.company.cost_center}],
        })
        doc.insert()
        if submit:
            doc.submit()
        return doc

    def balance(self):
        return loyalty.get_available_points(self.customer.name, self.company.name, self.program.name)["available_points"]

    def test_submission_redemption_cancellation_and_totals(self):
        earned = self.invoice()
        initial = int(earned.base_grand_total / 10)
        self.assertEqual(self.balance(), initial)
        doc = self.invoice(total=100, points=40, submit=False)
        self.assertEqual(self.balance(), initial)  # Drafts reserve/deduct nothing.
        self.assertEqual(doc.custom_available_loyalty_points, initial)
        self.assertEqual(doc.loyalty_amount, 40)
        self.assertEqual(doc.outstanding_amount, doc.grand_total - 40)
        doc.submit()
        self.assertEqual(self.balance(), initial - 40 + int((doc.base_grand_total - 40) / 10))
        doc.cancel()
        self.assertEqual(self.balance(), initial)
        earned.cancel()
        self.assertEqual(self.balance(), 0)

    def test_partial_full_return_and_cancel_return(self):
        self.invoice()
        initial = self.balance()
        doc = self.invoice(total=100, points=40)
        first = self.invoice(total=50, original=doc)
        self.assertEqual((first.loyalty_points, first.loyalty_amount), (-20, -20))
        self.assertEqual(self.balance(), initial - 20 + int((doc.base_grand_total - 40) / 20))
        second = self.invoice(total=50, original=doc)
        self.assertEqual(second.loyalty_points, -20)
        self.assertEqual(self.balance(), initial)
        second.cancel()
        self.assertEqual(self.balance(), initial - 20 + int((doc.base_grand_total - 40) / 20))
        first.cancel()
        self.assertEqual(self.balance(), initial - 40 + int((doc.base_grand_total - 40) / 10))
        self.assertEqual(frappe.db.count("Loyalty Point Entry", {"invoice": doc.name, "loyalty_points": -40}), 1)

    def test_overspending_and_tampered_amount(self):
        self.invoice()
        initial = self.balance()
        with self.assertRaises(frappe.ValidationError):
            self.invoice(total=500, points=initial + 1, submit=False)
        doc = self.invoice(total=100, points=30, submit=False)
        doc.loyalty_amount = 99
        doc.custom_available_loyalty_points = 99999
        doc.save()
        self.assertEqual(doc.loyalty_amount, 30)
        self.assertEqual(doc.custom_available_loyalty_points, initial)

    def test_two_drafts_recheck_at_submission(self):
        self.invoice()
        first = self.invoice(total=100, points=80, submit=False)
        second = self.invoice(total=100, points=80, submit=False)
        first.submit()
        with self.assertRaises(frappe.ValidationError):
            second.submit()

    def test_balance_endpoint_permissions_and_program(self):
        self.invoice()
        with patch.object(frappe, "has_permission", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                loyalty.get_available_points(self.customer.name, self.company.name, self.program.name)
        with self.assertRaises(frappe.ValidationError):
            loyalty.get_available_points(self.customer.name, self.company.name, "Different Program")

    def test_expiry_future_entries_and_signed_movements(self):
        root = frappe._dict(name="earn", loyalty_points=100, redeem_against=None,
            posting_date=today(), expiry_date=add_days(today(), 10), invoice_type="Sales Invoice", invoice="A")
        debit = frappe._dict(name="spent", loyalty_points=-70, redeem_against="earn")
        restored = frappe._dict(name="return", loyalty_points=20, redeem_against="earn")
        self.assertEqual(loyalty.available_buckets([root, debit, restored])[0][1], 50)
        self.assertEqual(loyalty.available_buckets([root], exclude_invoice="A"), [])
        root.expiry_date = add_days(today(), -1)
        self.assertEqual(loyalty.available_buckets([root]), [])
        root.expiry_date = add_days(today(), 20)
        root.posting_date = add_days(today(), 1)
        self.assertEqual(loyalty.available_buckets([root]), [])
        self.assertEqual(loyalty.return_entitlement(7, 100, 33), 2)
        self.assertEqual(loyalty.return_entitlement(7, 100, 100, 2), 5)

    def test_expired_and_other_customer_points_are_not_available(self):
        earned = self.invoice()
        entry = frappe.get_doc("Loyalty Point Entry", {"invoice": earned.name, "redeem_against": ["is", "not set"]})
        entry.expiry_date = add_days(today(), -1)
        entry.save()
        self.assertEqual(self.balance(), 0)
        with self.assertRaises(frappe.ValidationError):
            self.invoice(total=100, points=1, submit=False)
        entry.expiry_date = add_days(today(), 30)
        entry.customer = frappe.get_all("Customer", filters={"name": ["!=", self.customer.name]}, pluck="name", limit=1)[0]
        entry.save()
        self.assertEqual(self.balance(), 0)

    def test_invalid_points_and_invoice_amount_limit(self):
        self.invoice()
        for points in (-1, 1.5):
            # Validation must reject decimals before an Int DB field can truncate them.
            doc = self.invoice(total=100, submit=False)
            doc.redeem_loyalty_points = 1
            doc.loyalty_points = points
            with self.assertRaises(frappe.ValidationError):
                doc.save()
        with self.assertRaises(frappe.ValidationError):
            self.invoice(total=10, points=20, submit=False)

    def test_cannot_cancel_earned_points_already_spent(self):
        earned = self.invoice()
        self.invoice(total=100, points=40)
        with self.assertRaises(frappe.ValidationError):
            earned.cancel()

    def test_return_gl_reverses_redemption_amount(self):
        self.invoice()
        doc = self.invoice(total=100, points=40)
        returned = self.invoice(total=100, original=doc)
        self.assertEqual(returned.loyalty_amount, -40)
        rows = frappe.get_all("GL Entry", filters={"voucher_type": "Sales Invoice",
            "voucher_no": returned.name, "account": self.expense, "is_cancelled": 0},
            fields=["debit", "credit"])
        self.assertEqual(sum(row.credit - row.debit for row in rows), 40)

    def test_customer_read_permission_is_checked(self):
        customer = frappe.get_doc("Customer", self.customer.name)
        with patch.object(frappe, "get_doc", return_value=customer), patch.object(
            customer, "check_permission", side_effect=frappe.PermissionError
        ), self.assertRaises(frappe.PermissionError):
            loyalty.get_available_points(self.customer.name, self.company.name, self.program.name)

    def test_foreign_currency_redemption_uses_company_currency(self):
        self.invoice()
        doc = self.invoice(total=100, points=40, currency="USD", conversion_rate=2, submit=False)
        doc.submit()
        self.assertEqual(doc.loyalty_amount, 40)
        rows = frappe.get_all("GL Entry", filters={"voucher_type": "Sales Invoice",
            "voucher_no": doc.name, "account": self.expense, "is_cancelled": 0},
            fields=["debit", "debit_in_transaction_currency"])
        self.assertEqual(sum(row.debit for row in rows), 40)
        self.assertEqual(sum(row.debit_in_transaction_currency for row in rows), 20)

    def test_return_cannot_refund_both_cash_and_redeemed_points(self):
        self.invoice()
        original = self.invoice(total=100, points=40)
        returned = self.invoice(total=100, original=original, submit=False)
        returned.is_pos = 1
        returned.append("payments", {"amount": -original.grand_total})
        with self.assertRaises(frappe.ValidationError):
            loyalty.validate_redemption(returned)
        returned.payments[0].amount = -(original.grand_total - 40)
        loyalty.validate_redemption(returned)
