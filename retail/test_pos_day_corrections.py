"""Rollback-only integration checks for closing revisions and real accounting."""
import copy
import json

import frappe
from frappe.utils import flt, nowdate, nowtime


def run_integration():
    if frappe.local.site != "retail-test.localhost":
        raise RuntimeError("Use retail-test.localhost")
    from retail.api import pos_sync
    from retail import pos_day_corrections as service
    from retail.retail_app.doctype.pos_branch_day_closing.pos_branch_day_closing import make_day_closing
    frappe.set_user("Administrator")
    frappe.flags.in_test = True
    results = []
    token = frappe.generate_hash(length=10)
    base = json.loads(frappe.db.get_value("POS Sync Log", "PSL-2644", "request_json"))
    if "payload" in base:
        base = base["payload"]
    original_counter = pos_sync._counter(base["branch"], base["counter_code"])
    try:
        # Isolate the fixture from the site's editable MOP labels/types. This
        # native metadata change is rolled back with the entire fixture.
        card = frappe.get_doc("Mode of Payment", "Card")
        card.type = "Bank"
        card.save()
        frappe.clear_document_cache("Mode of Payment", "Card")
        branch = frappe.get_doc({"doctype": "Branch", "branch": "Correction Test " + token}).insert()
        profile = frappe.copy_doc(frappe.get_doc("POS Profile", original_counter.pos_profile))
        profile.name = "Correction Test " + token
        modes = [r.mode_of_payment for r in profile.payments]
        if "Card" not in modes:
            profile.append("payments", {"mode_of_payment": "Card"})
        profile.insert()
        counter = frappe.copy_doc(original_counter)
        counter.branch = branch.name
        counter.counter_code = "COR" + token
        counter.counter_name = counter.counter_code
        counter.pos_profile = profile.name
        counter.insert()
        employee = base.get("cashier_employee") or base.get("cashier_id")
        if not employee:
            employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
        shift = frappe.get_doc({"doctype": "POS Cashier Shift", "branch": branch.name,
            "cashier_employee": employee, "opening_time": nowdate() + " 00:00:00", "status": "Closed",
            "opening_amount": 0, "closing_amount": 0}).insert()
        opening = frappe.get_doc({"doctype": "POS Opening Entry", "company": counter.company,
            "pos_profile": profile.name, "user": "Administrator", "period_start_date": nowdate() + " 00:00:00",
            "balance_details": [{"mode_of_payment": "Cash", "opening_amount": 0}]}).insert()
        opening.submit()
        session = frappe.get_doc({"doctype": "POS Counter Session", "branch": branch.name, "counter": counter.name,
            "counter_code": counter.counter_code, "cashier_employee": employee, "cashier_shift": shift.name,
            "started_at": nowdate() + " 00:00:00", "status": "Closed", "pos_opening_entry": opening.name}).insert()
        for field in ("external_shift_reference", "external_session_reference", "cashier_shift_id", "counter_session_id", "pos_terminal_id", "terminal_id"):
            base.pop(field, None)
        base.update(branch=branch.name, counter_code=counter.counter_code, cashier_employee=employee,
            cashier_id=employee, cashier_shift=shift.name, counter_session=session.name,
            pos_shift_no=opening.name, posting_date=nowdate(), business_date=nowdate(), posting_time=nowtime())
        def sale(suffix):
            data = {**copy.deepcopy(base), "external_pos_reference": f"day-test-{token}-{suffix}"}
            response = pos_sync.create_pos_invoice(data)
            assert response.get("status") == "Success", response
            return frappe.get_doc("POS Invoice", response["invoice_name"])
        def request(closing, suffix, **values):
            return {"day_closing": closing, "operation_reference": f"day-test-{token}-{suffix}", "reason": "Integration test correction", **values}
        first = sale("first")
        assert len([r for r in first.payments if r.amount]) == 1
        assert first.paid_amount > 0 and not first.change_amount and not first.outstanding_amount
        pos_sync._refresh_cashier_shift_cash_totals(shift.name)
        frappe.db.set_value("POS Cashier Shift", shift.name, "closing_amount", first.paid_amount)
        original = frappe.get_doc(DAY := "POS Branch Day Closing", make_day_closing(branch.name, nowdate()).name)
        initial_close_request = {"branch": branch.name, "business_date": nowdate(), "external_pos_reference": f"day-test-{token}-initial-close"}
        initial_close = pos_sync.submit_branch_day_closing(initial_close_request)
        assert initial_close.get("docstatus") == 1, initial_close
        assert initial_close["invoice_count"] == 1 and initial_close["payment_totals"]["Cash"] == first.paid_amount
        original.reload()
        original_total = original.total_sales
        opening_request = request(original.name, "reopen")
        reopened = service.reopen_day_closing(opening_request)
        assert frappe.db.get_value(DAY, original.name, "docstatus") == 2
        assert frappe.db.get_value(DAY, original.name, "total_sales") == original_total
        assert reopened["revision"] == 1 and reopened["business_date"] == nowdate()
        assert service.reopen_day_closing(opening_request)["duplicate"] is True
        results.append("reopen preserves original snapshot and retry returns one revision")
        current = reopened["day_closing"]
        si = frappe.get_doc("Sales Invoice", first.consolidated_invoice)
        sle_before = frappe.db.count("Stock Ledger Entry", {"voucher_no": si.name})
        gl_before = frappe.db.count("GL Entry", {"voucher_no": si.name})
        payment_request = request(current, "mop", pos_invoice=first.name, expected_payment_revision=0,
            payments=[{"payment_row": r.name, "mode_of_payment": "Card"} for r in first.payments if r.amount])
        for label, mutate in (
            ("stale", lambda d: d.update(expected_payment_revision=99)),
            ("amount", lambda d: d["payments"][0].update(amount=1)),
        ):
            rejected = copy.deepcopy(payment_request)
            rejected["operation_reference"] += "-" + label
            mutate(rejected)
            try:
                service.correct_settled_bill_mop(rejected)
            except frappe.ValidationError:
                frappe.db.rollback(save_point="pos_operation_claim")
            else:
                raise AssertionError("Invalid payment request was accepted: " + label)
            assert frappe.db.get_value("POS Invoice", first.name, "custom_payment_revision") == 0
        frappe.db.savepoint("bank_clearance_check")
        frappe.db.set_value("Sales Invoice Payment", next(p.name for p in si.payments if p.amount), "clearance_date", nowdate())
        try:
            service.correct_settled_bill_mop(payment_request)
        except frappe.ValidationError:
            pass
        else:
            raise AssertionError("Bank-cleared payment was corrected")
        frappe.db.rollback(save_point="bank_clearance_check")
        results.append("stale revisions, amount edits and bank-cleared payments are rejected")
        correction = service.correct_settled_bill_mop(payment_request)
        assert correction["accounting_repost"], correction
        assert correction["payment_revision"] == 1
        assert frappe.db.get_value("Sales Invoice", si.name, "outstanding_amount") == si.outstanding_amount
        target_account = correction["payments"][0]["account"]
        assert service.correct_settled_bill_mop(payment_request)["duplicate"] is True
        assert frappe.db.count("Stock Ledger Entry", {"voucher_no": si.name}) == sle_before
        assert frappe.db.count("GL Entry", {"voucher_no": si.name}) > gl_before
        assert frappe.db.get_value("POS Invoice", first.name, "grand_total") == first.grand_total
        active_gl = frappe.get_all("GL Entry", filters={"voucher_type": "Sales Invoice", "voucher_no": si.name, "is_cancelled": 0}, fields=["debit", "credit", "account"])
        assert active_gl and abs(sum(r.debit-r.credit for r in active_gl)) < 0.001
        assert abs(sum(r.debit-r.credit for r in active_gl if r.account == target_account) - first.paid_amount) < 0.001
        for dt, name in (("POS Invoice", first.name), ("Sales Invoice", si.name)):
            corrected_payments = [p for p in frappe.get_doc(dt, name).payments if p.amount]
            assert [p.mode_of_payment for p in corrected_payments] == ["Card"]
            assert all(p.type == frappe.get_cached_value("Mode of Payment", "Card", "type") for p in corrected_payments)
        assert abs(correction["expected_cash"]) < 0.001
        results.append("MOP correction updates both payment records and native GL with retained history, unchanged stock/sales and idempotent retry")
        from retail.test_pos_settlement_corrections import exercise
        results.append(exercise(first, current, shift, session, request))
        adjusted = service.adjust_day_closing_payments(request(current, "count", counted_cash=[{
            "cashier_shift": shift.name, "expected_amount": first.paid_amount, "closing_amount": 0}]))
        assert adjusted["counted_cash"] == 0 and adjusted["variance"] == 0
        reviewed = service.recalculate_day_closing(request(current, "review"))
        late = sale("late")
        assert late.docstatus == 1
        try:
            service.reclose_day_closing(request(current, "stale-close", expected_reconciliation_hash=reviewed["reconciliation_hash"]))
        except frappe.ValidationError:
            frappe.db.rollback(save_point="pos_operation_claim")
        else:
            raise AssertionError("Stale review must not close the day")
        # No recalculation request or review hash: the existing endpoint must include
        # the late bill itself, even though the earlier preview is stale.
        close_request = {"branch": branch.name, "business_date": nowdate(), "external_pos_reference": f"day-test-{token}-revised-close"}
        closed = pos_sync.submit_branch_day_closing(close_request)
        assert closed.get("docstatus") == 1, closed
        assert closed["name"] == current and closed["invoice_count"] == 2
        assert closed["payment_totals"]["Card"] == first.paid_amount
        assert closed["payment_totals"]["Cash"] == late.paid_amount
        assert pos_sync.submit_branch_day_closing(close_request)["duplicate"] is True
        assert pos_sync.submit_branch_day_closing(initial_close_request)["name"] == original.name
        assert frappe.db.get_value(DAY, original.name, "docstatus") == 2
        assert closed["state"] == "Closed" and closed["business_date"] == nowdate()
        assert abs(closed["total_sales"] - first.grand_total - late.grand_total) < 0.001
        results.append("existing close API recalculates initial and reopened days, includes late bills without preview, and retries safely")
        frappe.db.savepoint("frozen_check")
        frappe.db.set_single_value("Accounts Settings", "acc_frozen_upto", nowdate())
        try:
            service.reopen_day_closing(request(current, "frozen"))
        except frappe.ValidationError:
            pass
        else:
            raise AssertionError("Frozen day was reopened")
        frappe.db.rollback(save_point="frozen_check")
        results.append("accounting freeze prevents reopening")
        try:
            service.guard_sale_day(first)
        except service.POSDayClosed:
            pass
        else:
            raise AssertionError("New billing was permitted on a closed business day")
        results.append("closed-day submission guard rejects new billing")
        return {"passed": results, "business_data": "rolled back"}
    finally:
        frappe.db.rollback()
        frappe.clear_cache()
