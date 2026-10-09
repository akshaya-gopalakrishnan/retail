"""Real-ledger settlement scenarios, invoked inside the rollback-only day fixture."""
import frappe
from unittest.mock import patch
from frappe.utils import flt

from retail import pos_settlement_corrections as service


def exercise(pos, closing, shift, session, request):
    customer = frappe.get_doc("Customer", pos.customer)
    limits = [r for r in customer.credit_limits if r.company == pos.company]
    if limits:
        limits[0].credit_limit = 999999999
    else:
        customer.append("credit_limits", {"company": pos.company, "credit_limit": 999999999})
    customer.save()
    frappe.clear_document_cache("Customer", customer.name)
    original_total = pos.grand_total
    si_name = pos.consolidated_invoice
    stock_before = frappe.get_all("Stock Ledger Entry", filters={"voucher_no": si_name},
        fields=["name", "actual_qty", "stock_value_difference"], order_by="name")
    def state():
        return service.get_settlement_details(closing, pos.name)
    def call(action, suffix, **values):
        data = request(closing, suffix, pos_invoice=pos.name, action=action,
            expected_settlement_hash=state()["settlement_hash"], **values)
        result = service.correct_bill_settlement(data)
        assert service.correct_bill_settlement(data)["duplicate"] is True
        return result
    def balance(expected):
        assert abs(flt(frappe.db.get_value("Sales Invoice", si_name, "outstanding_amount")) - expected) < .001
        assert abs(flt(frappe.db.get_value("POS Invoice", pos.name, "outstanding_amount")) - expected) < .001
    amount = flt(pos.paid_amount)
    converted = call("SetCredit", "to-credit")
    balance(amount)
    assert converted["settlement"]["initial_paid_amount"] == 0
    assert all(not r.amount for r in frappe.get_doc("POS Invoice", pos.name).payments)
    partial = flt(amount / 2, 2)
    collection = call("CollectCredit", "collect-cash", mode_of_payment="Cash", amount=partial,
        cashier_shift=shift.name, counter_session=session.name)
    balance(amount - partial)
    assert abs(collection["expected_cash"] - partial) < .001
    assert abs(collection["payment_totals"]["Cash"] - partial) < .001
    original_payment = collection["payment_entry"]
    frappe.db.savepoint("cleared_collection")
    frappe.db.set_value("Payment Entry", original_payment, "clearance_date", frappe.utils.nowdate())
    try:
        call("ChangeCollectionMOP", "cleared-denied", mode_of_payment="Card", payment_entry=original_payment)
    except frappe.ValidationError:
        frappe.db.rollback(save_point="cleared_collection")
    else:
        raise AssertionError("Bank-cleared collection was changed")
    # Simulate a failure after cancelling the old collection: rollback must restore it.
    failed = request(closing, "failed-amend", pos_invoice=pos.name, action="ChangeCollectionMOP",
        expected_settlement_hash=state()["settlement_hash"], mode_of_payment="Card", payment_entry=original_payment)
    try:
        with patch.object(service, "create_collection", side_effect=RuntimeError("test failure")):
            service.correct_bill_settlement(failed)
    except RuntimeError:
        frappe.db.rollback(save_point="pos_operation_claim")
    else:
        raise AssertionError("Expected replacement failure")
    assert frappe.db.get_value("Payment Entry", original_payment, "docstatus") == 1
    balance(amount - partial)
    changed = call("ChangeCollectionMOP", "collection-to-card", mode_of_payment="Card", payment_entry=original_payment)
    balance(amount - partial)
    assert frappe.db.get_value("Payment Entry", original_payment, "docstatus") == 2
    replacement = changed["payment_entry"]
    assert frappe.db.get_value("Payment Entry", replacement, "amended_from") == original_payment
    assert abs(changed["expected_cash"]) < .001
    assert abs(changed["payment_totals"]["Card"] - partial) < .001
    call("ReverseCollection", "reverse-collection", payment_entry=replacement)
    balance(amount)
    assert frappe.db.get_value("Payment Entry", replacement, "docstatus") == 2
    # A later collection belongs to its own day, not the original sale day.
    from retail.retail_app.doctype.pos_branch_day_closing.pos_branch_day_closing import make_day_closing
    from retail.api import pos_sync
    from retail import pos_day_corrections as days
    tomorrow = frappe.utils.add_days(frappe.utils.nowdate(), 1)
    later_shift = frappe.copy_doc(shift)
    later_shift.opening_time = str(tomorrow) + " 00:00:00"
    later_shift.closing_amount = 0
    later_shift.insert()
    later_session = frappe.copy_doc(session)
    later_session.cashier_shift = later_shift.name
    later_session.started_at = str(tomorrow) + " 00:00:00"
    later_session.insert()
    later_day = make_day_closing(shift.branch, tomorrow).name
    later_request = request(later_day, "later-collection", pos_invoice=pos.name, action="CollectCredit",
        expected_settlement_hash=state()["settlement_hash"], amount=partial, mode_of_payment="Cash",
        cashier_shift=later_shift.name, counter_session=later_session.name)
    later = service.correct_bill_settlement(later_request)
    assert later["total_sales"] == 0 and abs(later["expected_cash"] - partial) < .001
    assert abs(days.recalculate(frappe.get_doc(days.DAY, closing))["expected_cash"]) < .001
    later_closed = pos_sync.submit_branch_day_closing({"branch": shift.branch, "business_date": tomorrow,
        "external_pos_reference": request(later_day, "later-close")["operation_reference"]})
    assert later_closed.get("docstatus") == 1, later_closed
    later_reopened = days.reopen_day_closing(request(later_day, "later-reopen"))["day_closing"]
    service.correct_bill_settlement(request(later_reopened, "later-reverse", pos_invoice=pos.name,
        action="ReverseCollection", expected_settlement_hash=state()["settlement_hash"], payment_entry=later["payment_entry"]))
    balance(amount)
    final = call("CollectCredit", "collect-card", mode_of_payment="Card", amount=amount,
        cashier_shift=shift.name, counter_session=session.name)
    balance(0)
    assert abs(final["payment_totals"]["Card"] - amount) < .001
    assert abs(final["expected_cash"]) < .001
    # Audit references cannot be used to repeat a collection with a new snapshot.
    stale = request(closing, "stale-settlement", pos_invoice=pos.name, action="CollectCredit",
        expected_settlement_hash=converted["settlement"]["settlement_hash"], amount=1,
        mode_of_payment="Cash", cashier_shift=shift.name, counter_session=session.name)
    try:
        service.correct_bill_settlement(stale)
    except frappe.ValidationError:
        frappe.db.rollback(save_point="pos_operation_claim")
    else:
        raise AssertionError("Stale settlement was accepted")
    balance(0)
    assert frappe.db.get_value("POS Invoice", pos.name, "grand_total") == original_total
    assert frappe.db.get_value("Sales Invoice", si_name, "grand_total") == original_total
    assert frappe.get_all("Stock Ledger Entry", filters={"voucher_no": si_name},
        fields=["name", "actual_qty", "stock_value_difference"], order_by="name") == stock_before
    for name in [si_name, final["payment_entry"]]:
        gl = frappe.get_all("GL Entry", filters={"voucher_no": name, "is_cancelled": 0}, fields=["debit", "credit"])
        assert gl and abs(sum(r.debit-r.credit for r in gl)) < .001
    return "paid-to-credit, partial cash collection, card amendment, collection reversal and full settlement preserve balances, stock and sales; later-day collection, rollback, bank clearing, retries and stale requests verified"
