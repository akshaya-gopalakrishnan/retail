import unittest
from unittest.mock import Mock, patch

import frappe
from retail import pos_day_corrections as service


class TestDayCorrectionPermissions(unittest.TestCase):
    def setUp(self):
        self.patch(frappe.local, "session", new=frappe._dict(user="manager@example.com"), create=True)
        self.patch(frappe.local, "flags", new=frappe._dict(), create=True)
        self.patch(frappe.local, "db", new=Mock(), create=True)
        self.patch(service, "_", side_effect=lambda text:text)
        self.patch(frappe, "throw", side_effect=frappe.PermissionError)
        self.patch("retail.module_access", "require")
        self.super_admin = self.patch("retail.access_control", "is_super_admin", return_value=False)
        self.roles = self.patch(frappe, "get_roles", return_value=["POS Manager"])
        self.employees = self.patch(frappe, "get_all", return_value=[frappe._dict(branch="Branch A",pos_login_enabled=1,pos_operator_privilege="Manager")])
        self.privileges = self.patch("retail.pos_privileges", "profile_privileges", return_value={service.REOPEN:True})
        self.closing = Mock(branch="Branch A", business_date="2026-09-30", docstatus=0)
        self.closing.get.side_effect=lambda key: "ORIGINAL" if key=="amended_from" else None

    def patch(self, target, name, **kwargs):
        if isinstance(target, str):
            target = __import__(target, fromlist=[name])
        patcher=patch.object(target,name,**kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_named_manager_needs_matching_branch_and_privilege(self):
        service.authorize(self.closing,service.REOPEN)
        self.closing.check_permission.assert_called_with("read")
        self.closing.branch="Branch B"
        with self.assertRaises(frappe.PermissionError):
            service.authorize(self.closing,service.REOPEN)
        self.closing.branch="Branch A"
        self.privileges.return_value={}
        with self.assertRaises(frappe.PermissionError):
            service.authorize(self.closing,service.REOPEN)

    def test_shared_integration_identity_cannot_approve_corrections(self):
        self.roles.return_value=["POS Manager","POS Integration User"]
        with self.assertRaises(frappe.PermissionError):
            service.authorize(self.closing,service.REOPEN)

    def test_super_admin_can_support_without_employee_identity(self):
        self.super_admin.return_value=True
        service.authorize(self.closing,service.REOPEN)
        self.employees.assert_not_called()

    def test_privilege_is_checked_before_replaying_any_operation(self):
        self.patch(frappe,"get_doc",return_value=self.closing)
        self.privileges.return_value={}
        execute=self.patch(service.pos_operations,"execute")
        with self.assertRaises(frappe.PermissionError):
            service.operation("Day Reopen",frappe._dict(day_closing="DAY",reason="Reason",operation_reference="ref"),service.REOPEN,Mock())
        execute.assert_not_called()

    def test_corrections_require_reopened_draft(self):
        for state in (1,2):
            self.closing.docstatus=state
            with self.assertRaises(frappe.PermissionError):
                service.require_reopened(self.closing)

    def test_period_lock_is_strict_even_for_developer(self):
        frappe.db.get_single_value.return_value="2026-09-30"
        with self.assertRaises(frappe.PermissionError):
            service.check_period("Company","2026-09-29")

    def test_bank_reconciliation_blocks_correction(self):
        self.employees.return_value=[]
        frappe.db.sql.return_value=[("bank-payment",)]
        with self.assertRaises(frappe.PermissionError):
            service.check_bank_settlement("SI-1","POS-1")

    def test_invalid_counted_amounts_are_rejected(self):
        for value in (None,"abc","NaN","Infinity",-1):
            with self.subTest(value=value),self.assertRaises(frappe.PermissionError):
                service.money(value)

    def test_correction_context_does_not_leak_after_failure(self):
        with self.assertRaises(ValueError):
            with service.correction_context():
                self.assertTrue(frappe.flags.retail_day_correction)
                raise ValueError()
        self.assertFalse(frappe.flags.retail_day_correction)

    def test_changing_payment_revision_does_not_bypass_audit_protection(self):
        doc=Mock(doctype="POS Invoice")
        doc.get.return_value=0
        doc.get_doc_before_save.return_value=frappe._dict(custom_payment_revision=1,docstatus=1)
        with self.assertRaises(frappe.PermissionError):
            service.guard_corrected_document(doc)

    def test_existing_close_routes_reopened_day_through_manager_authorization(self):
        frappe.db.get_value.return_value = "REVISED-DAY"
        self.closing.amended_from = "ORIGINAL-DAY"
        self.patch(frappe, "get_doc", return_value=self.closing)
        allowed = self.patch(service, "authorize")
        legacy = self.patch("retail.api.pos_sync", "_assert_pos_user")
        service.authorize_day_close("Branch A", "2026-09-30")
        allowed.assert_called_once_with(self.closing, "DAY_CLOSING")
        legacy.assert_not_called()

    def test_existing_close_does_not_fall_back_when_manager_authorization_fails(self):
        frappe.db.get_value.return_value = "REVISED-DAY"
        self.closing.amended_from = "ORIGINAL-DAY"
        self.patch(frappe, "get_doc", return_value=self.closing)
        self.patch(service, "authorize", side_effect=frappe.PermissionError)
        legacy = self.patch("retail.api.pos_sync", "_assert_pos_user")
        with self.assertRaises(frappe.PermissionError):
            service.authorize_day_close("Branch A", "2026-09-30")
        legacy.assert_not_called()

    def test_settlement_details_require_the_separate_settlement_privilege(self):
        from retail import pos_settlement_corrections as settlement
        self.patch(frappe, "get_doc", return_value=self.closing)
        gate = self.patch(service, "authorize", side_effect=frappe.PermissionError)
        pair = self.patch(settlement, "invoice_pair")
        with self.assertRaises(frappe.PermissionError):
            settlement.get_settlement_details("DAY", "POS")
        gate.assert_called_once_with(self.closing, settlement.PRIVILEGE)
        pair.assert_not_called()

    def test_settlement_mutation_uses_separate_privilege_and_audited_operation(self):
        from retail import pos_settlement_corrections as settlement
        self.patch(service, "payload", return_value=frappe._dict(action="SetCredit"))
        operation = self.patch(service, "operation", return_value={"status": "Success"})
        settlement.correct_bill_settlement({})
        self.assertEqual(operation.call_args.args[0], "Bill Settlement Correction")
        self.assertEqual(operation.call_args.args[2], "CHANGE_BILL_SETTLEMENT")

    def test_collection_mop_cannot_silently_change_amount(self):
        from retail import pos_settlement_corrections as settlement
        self.patch(service, "payload", return_value=frappe._dict(action="ChangeCollectionMOP", amount=10))
        operation = self.patch(service, "operation")
        self.patch(settlement, "_", side_effect=lambda text:text)
        with self.assertRaises(frappe.PermissionError):
            settlement.correct_bill_settlement({})
        operation.assert_not_called()

    def test_corrected_collection_cannot_be_cancelled_through_document_api(self):
        from retail import pos_settlement_corrections as settlement
        self.patch(settlement, "_", side_effect=lambda text:text)
        doc = Mock()
        doc.get.side_effect = lambda field: "OP-1" if field == "custom_settlement_operation" else None
        doc.get_doc_before_save.return_value = frappe._dict(custom_settlement_operation="OP-1", docstatus=1)
        with self.assertRaises(frappe.PermissionError):
            settlement.guard_payment(doc, "before_cancel")


    def test_recalculate_and_reclose_accept_no_reason(self):
        self.patch(frappe, "get_doc", return_value=self.closing)
        self.patch(service, "authorize")
        self.patch(service, "require_reopened")
        self.patch(service, "company_for", return_value="Company")
        self.patch(service, "check_period")
        self.patch(service, "now_datetime", return_value="2026-09-30 12:00:00")
        self.patch(service, "recalculate", return_value={"reconciliation_hash": "reviewed"})
        self.patch(service, "view", return_value={"status": "Success"})
        execute = self.patch(service.pos_operations, "execute", side_effect=lambda kind, ref, request, run: run())
        data = {"day_closing": "DAY", "operation_reference": "preview"}
        self.assertEqual(service.recalculate_day_closing(data)["reconciliation_hash"], "reviewed")
        self.assertEqual(service.reclose_day_closing({**data, "operation_reference": "close",
            "expected_reconciliation_hash": "reviewed"})["status"], "Success")
        self.closing.submit.assert_called_once()
        self.assertEqual(execute.call_count, 2)
        self.assertNotIn("reason", execute.call_args.args[2]["payload"])

    def test_other_corrections_still_require_reason(self):
        self.patch(frappe, "get_doc", return_value=self.closing)
        self.patch(service, "authorize")
        execute = self.patch(service.pos_operations, "execute")
        for kind in ("Day Reopen", "Day Payment Adjustment", "Bill MOP Correction", "Bill Settlement Correction"):
            for reason in (None, "", "   "):
                with self.subTest(kind=kind, reason=reason), self.assertRaises(frappe.PermissionError):
                    service.operation(kind, frappe._dict(day_closing="DAY", operation_reference="ref", reason=reason),
                        service.REOPEN, Mock())
        execute.assert_not_called()
