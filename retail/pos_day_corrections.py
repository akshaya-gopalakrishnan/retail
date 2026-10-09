"""Manager-authorized, atomic revisions of POS business-day reconciliation."""

import hashlib
import json
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime

from retail import pos_operations

class POSDayClosed(frappe.ValidationError):
    pass


DAY = "POS Branch Day Closing"
REOPEN = "REOPEN_DAY_CLOSING"
ADJUST = "ADJUST_DAY_CLOSING_PAYMENTS"
CHANGE_MOP = "CHANGE_SETTLED_BILL_MOP"


def deny():
    frappe.throw(_("You do not have permission to perform this action. Please contact the software team."), frappe.PermissionError)


def authorize(closing, privilege):
    """A named manager authenticates as themselves; never trust a supplied operator ID."""
    from retail.access_control import is_super_admin
    from retail.module_access import require
    from retail.pos_privileges import profile_privileges
    require("POS")
    closing.check_permission("read")
    if is_super_admin():
        return
    roles = frappe.get_roles()
    if "POS Integration User" in roles:
        deny()
    employees = frappe.get_all("Employee", filters={"user_id": frappe.session.user, "status": "Active"},
        fields=["name", "branch", "pos_operator_privilege", "pos_login_enabled"])
    if not any(e.branch == closing.branch and e.pos_login_enabled and
               profile_privileges(e.pos_operator_privilege).get(privilege) for e in employees):
        deny()


def company_for(branch):
    companies = set(frappe.get_all("POS Branch Counter", filters={"branch": branch}, pluck="company"))
    companies.discard(None)
    if len(companies) != 1:
        frappe.throw(_("Day correction requires counters belonging to one company in this branch."))
    return companies.pop()


def check_period(company, date):
    from erpnext.accounts.general_ledger import validate_accounting_period
    date = getdate(date)
    frozen = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")
    if frozen and date <= getdate(frozen):
        frappe.throw(_("This date is frozen in Accounts Settings. Please contact the accounts team."))
    if frappe.db.exists("Period Closing Voucher", {"company": company, "docstatus": 1, "period_end_date": [">=", date]}):
        frappe.throw(_("This date belongs to a finalized accounting period."))
    for doctype in ("Sales Invoice", "POS Invoice"):
        validate_accounting_period([frappe._dict(company=company, posting_date=date, voucher_type=doctype)])


@contextmanager
def correction_context():
    previous = frappe.flags.get("retail_day_correction")
    frappe.flags.retail_day_correction = True
    try:
        yield
    finally:
        frappe.flags.retail_day_correction = previous


def payload(data=None, **kwargs):
    from retail.api.pos_sync import _as_dict
    result = _as_dict(data, **kwargs)
    if not result.get("day_closing"):
        frappe.throw(_("day_closing is required."))
    return result


def operation(kind, data, privilege, action, *, require_reason=True):
    closing = frappe.get_doc(DAY, data.day_closing)
    authorize(closing, privilege)  # Recheck permissions even for retries.
    if require_reason and (not isinstance(data.get("reason"), str) or not data.reason.strip()):
        frappe.throw(_("A reason is required."))
    request = {"actor": frappe.session.user, "payload": {**dict(data), "branch": closing.branch, "business_date": str(closing.business_date)}}
    def run():
        # Same order as sale sync and lifecycle APIs: branch, then day, then shift/invoice.
        frappe.db.get_value("Branch", closing.branch, "name", for_update=True)
        current = frappe.get_doc(DAY, closing.name, for_update=True)
        authorize(current, privilege)
        check_period(company_for(current.branch), current.business_date)
        with correction_context():
            return action(current)
    return pos_operations.execute(kind, data.get("operation_reference"), request, run)


def require_reopened(closing):
    if closing.docstatus != 0 or not closing.get("amended_from"):
        frappe.throw(_("Reopen the submitted day before making this correction."))
    if frappe.db.exists(DAY, {"branch": closing.branch, "business_date": closing.business_date, "docstatus": 1}):
        frappe.throw(_("This business day is already closed."))


def payment_rows(invoice):
    return [{"payment_row": p.name, "mode_of_payment": p.mode_of_payment,
             "account": p.account, "amount": flt(p.amount)} for p in invoice.payments if flt(p.amount)]


def recalculate(closing):
    from retail.api.pos_sync import _refresh_cashier_shift_cash_totals
    from retail.retail_app.doctype.pos_branch_day_closing.pos_branch_day_closing import _get_cashier_shifts
    shifts = _get_cashier_shifts(closing.branch, closing.business_date)
    for shift in shifts:
        totals = _refresh_cashier_shift_cash_totals(shift.name)
        frappe.db.set_value("POS Cashier Shift", shift.name, "variance", flt(shift.closing_amount) - totals.expected_cash)
    closing.refresh_summaries()
    invoices = frappe.get_all("POS Invoice", filters={"pos_cashier_shift": ["in", [s.name for s in shifts]], "docstatus": 1},
        fields=["name", "modified", "grand_total", "company", "posting_date"], order_by="name") if shifts else []
    totals, sources = {}, []
    for row in invoices:
        invoice = frappe.get_doc("POS Invoice", row.name)
        remaining_change = flt(invoice.change_amount)
        for payment in invoice.payments:
            value = flt(payment.amount)
            if remaining_change and payment.account == invoice.account_for_change_amount:
                value -= remaining_change
                remaining_change = 0
            totals[payment.mode_of_payment] = totals.get(payment.mode_of_payment, 0) + value
        sources.append({"invoice": row.name, "modified": row.modified, "total": row.grand_total,
                        "payments": payment_rows(invoice)})
    collections = frappe.get_all("Payment Entry", filters={"pos_cashier_shift": ["in", [s.name for s in shifts]],
        "docstatus": 1, "payment_type": ["in", ["Receive", "Pay"]]}, fields=["name", "modified", "mode_of_payment",
        "payment_type", "paid_amount", "received_amount"], order_by="name") if shifts else []
    for payment in collections:
        amount = flt(payment.received_amount) if payment.payment_type == "Receive" else -flt(payment.paid_amount)
        totals[payment.mode_of_payment or "Unspecified"] = totals.get(payment.mode_of_payment or "Unspecified", 0) + amount
    from retail.pos_settlements import summary
    settlement_totals = summary({"branch": closing.branch, "business_date": closing.business_date})
    snapshot = {"settlement_totals": settlement_totals, "collections": collections, "invoices": sources, "cashiers": [r.as_dict() for r in closing.cashier_summaries],
                "payment_totals": totals, "active_sessions": closing.active_counter_session_count}
    # Child names/timestamps are regenerated by refresh_summaries, not business changes.
    for row in snapshot["cashiers"]:
        for key in ("name", "creation", "modified", "modified_by", "owner", "__islocal", "idx", "parent", "docstatus"):
            row.pop(key, None)
    closing.reconciliation_hash = hashlib.sha256(pos_operations.canonical(snapshot).encode()).hexdigest()
    closing.payment_totals = pos_operations.canonical(totals)
    closing.pos_settlement_totals = pos_operations.canonical(settlement_totals)
    for field in ("credit_sales", "credit_notes_issued", "credit_notes_redeemed", "credit_notes_applied", "credit_notes_unresolved"):
        closing.set("pos_" + field, settlement_totals[field])
    closing.last_recalculated_at = now_datetime()
    closing.save(ignore_permissions=True)
    return view(closing)


def view(closing):
    return {"status": "Success", "day_closing": closing.name, "previous_closing": closing.get("amended_from"),
        "branch": closing.branch, "business_date": str(closing.business_date), "revision": cint(closing.revision),
        "state": "Closed" if closing.docstatus == 1 else "Reopened", "docstatus": closing.docstatus,
        "reconciliation_hash": closing.reconciliation_hash, "payment_totals": json.loads(closing.payment_totals or "{}"),
        "settlement_totals": json.loads(closing.get("pos_settlement_totals") or "{}"),
        "total_sales": closing.total_sales, "invoice_count": closing.total_invoice_count,
        "expected_cash": closing.total_expected_cash, "counted_cash": closing.total_closing_cash,
        "variance": closing.total_variance, "open_shifts": closing.open_shift_count,
        "active_sessions": closing.active_counter_session_count}


@frappe.whitelist(methods=["POST"])
def reopen_day_closing(data=None, **kwargs):
    data = payload(data, **kwargs)
    def action(old):
        if old.docstatus != 1:
            frappe.throw(_("Only a submitted day can be reopened."))
        from retail.retail_app.doctype.pos_branch_day_closing.pos_branch_day_closing import _get_cashier_shifts
        shifts = _get_cashier_shifts(old.branch, old.business_date)
        if shifts:
            for bill in frappe.get_all("POS Invoice", filters={"pos_cashier_shift": ["in", [s.name for s in shifts]], "docstatus": 1}, fields=["name", "consolidated_invoice"]):
                if bill.consolidated_invoice:
                    check_bank_settlement(bill.consolidated_invoice, bill.name)
        from retail.pos_settlement_corrections import check_bank
        if shifts:
            for name in frappe.get_all("Payment Entry", filters={"pos_cashier_shift": ["in", [s.name for s in shifts]], "docstatus": 1}, pluck="name"):
                check_bank(frappe.get_doc("Payment Entry", name))
        old.cancel_reason = data.reason
        old.flags.ignore_permissions = True
        old.cancel()  # Preserve totals in the cancelled original; never reset docstatus directly.
        new = frappe.get_doc({"doctype": DAY, "branch": old.branch, "business_date": old.business_date,
            "amended_from": old.name, "revision": cint(old.revision) + 1,
            "reopened_by": frappe.session.user, "reopened_at": now_datetime(), "reopen_reason": data.reason})
        new.insert(ignore_permissions=True)
        return recalculate(new)
    return operation("Day Reopen", data, REOPEN, action)


@frappe.whitelist(methods=["POST"])
def recalculate_day_closing(data=None, **kwargs):
    data = payload(data, **kwargs)
    def action(closing):
        require_reopened(closing)
        return recalculate(closing)
    return operation("Day Recalculate", data, "DAY_CLOSING", action, require_reason=False)


@frappe.whitelist(methods=["POST"])
def reclose_day_closing(data=None, **kwargs):
    data = payload(data, **kwargs)
    def action(closing):
        require_reopened(closing)
        if not data.get("expected_reconciliation_hash"):
            frappe.throw(_("Recalculate and review the closing before confirming it."))
        result = recalculate(closing)
        if result["reconciliation_hash"] != data.expected_reconciliation_hash:
            frappe.throw(_("Day totals changed. Recalculate and review the latest totals before closing."))
        closing.manager_user = frappe.session.user
        closing.closed_at = now_datetime()
        closing.flags.ignore_permissions = True
        closing.submit()
        return view(closing)
    return operation("Day Reclose", data, "DAY_CLOSING", action, require_reason=False)


@frappe.whitelist(methods=["POST"])
def adjust_day_closing_payments(data=None, **kwargs):
    """Correct counted CASH declarations, never overwrite expected totals."""
    data = payload(data, **kwargs)
    def action(closing):
        require_reopened(closing)
        rows = data.get("counted_cash")
        if not isinstance(rows, list) or not rows:
            frappe.throw(_("counted_cash must contain cashier_shift, expected_amount and closing_amount."))
        changes, seen = [], set()
        for row in rows:
            name = row.get("cashier_shift")
            if name in seen:
                frappe.throw(_("A cashier shift cannot be adjusted twice in one request."))
            seen.add(name)
            shift = frappe.get_doc("POS Cashier Shift", name, for_update=True)
            if shift.branch != closing.branch or getdate(shift.opening_time) != getdate(closing.business_date) or shift.status != "Closed":
                frappe.throw(_("The shift must be closed and belong to this branch and business day."))
            amount = money(row.get("closing_amount"))
            if money(row.get("expected_amount")) != money(shift.closing_amount):
                frappe.throw(_("The counted cash changed. Refresh before correcting it."))
            changes.append({"cashier_shift": name, "before": shift.closing_amount, "after": float(amount)})
            frappe.db.set_value("POS Cashier Shift", name, "closing_amount", float(amount))
        return {**recalculate(closing), "counted_cash_changes": changes}
    return operation("Day Payment Adjustment", data, ADJUST, action)


def money(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        frappe.throw(_("A valid payment amount is required."))
    if not result.is_finite() or result < 0:
        frappe.throw(_("Payment amounts must be finite and non-negative."))
    return result


def check_bank_settlement(accounting_invoice, pos_invoice):
    if frappe.db.exists("Sales Invoice Payment", {"parent": accounting_invoice, "parenttype": "Sales Invoice", "clearance_date": ["is", "set"]}):
        frappe.throw(_("The payment has been bank cleared. Please contact the accounts team."))
    if frappe.db.sql("""select p.name from `tabBank Transaction Payments` p
        join `tabBank Transaction` b on b.name=p.parent
        where p.payment_document='Sales Invoice' and p.payment_entry=%s and b.docstatus=1 limit 1""", (accounting_invoice,)):
        frappe.throw(_("The payment has been bank reconciled. Please use the accounts team's correction process."))


def validate_invoice(invoice, closing):
    shift = frappe.get_doc("POS Cashier Shift", invoice.pos_cashier_shift)
    if shift.branch != closing.branch or getdate(shift.opening_time) != getdate(closing.business_date):
        frappe.throw(_("The bill does not belong to this business day."))
    if invoice.company != company_for(closing.branch):
        frappe.throw(_("The bill belongs to another company."))
    currency = frappe.get_cached_value("Company", invoice.company, "default_currency")
    if (invoice.docstatus != 1 or invoice.is_return or not invoice.consolidated_invoice
            or flt(invoice.outstanding_amount) or flt(invoice.change_amount) or flt(invoice.write_off_amount)
            or flt(invoice.loyalty_amount) or flt(invoice.get("custom_gift_voucher_amount"))
            or invoice.currency != currency or flt(invoice.conversion_rate) != 1):
        frappe.throw(_("This correction supports fully paid, company-currency POS sales without change, returns, write-offs, loyalty or vouchers."))
    if frappe.db.exists("POS Invoice", {"return_against": invoice.name, "docstatus": 1}):
        frappe.throw(_("A bill with submitted returns requires accounts review."))
    if frappe.db.count("POS Invoice", {"consolidated_invoice": invoice.consolidated_invoice, "docstatus": 1}) != 1:
        frappe.throw(_("The bill belongs to a combined accounting invoice and requires accounts review."))
    accounting = frappe.get_doc("Sales Invoice", invoice.consolidated_invoice, for_update=True)
    if accounting.docstatus != 1 or accounting.company != invoice.company or flt(accounting.outstanding_amount):
        frappe.throw(_("The linked accounting invoice is not eligible for correction."))
    if flt(accounting.paid_amount) != flt(invoice.paid_amount) or flt(accounting.change_amount) or flt(accounting.write_off_amount) or flt(invoice.paid_amount) <= 0:
        frappe.throw(_("The original settled payment amounts do not match."))
    check_period(invoice.company, invoice.posting_date)
    check_period(accounting.company, accounting.posting_date)
    check_bank_settlement(accounting.name, invoice.name)
    return accounting


def new_account(mode, invoice):
    mop = frappe.get_doc("Mode of Payment", mode)
    if not mop.enabled or mop.type not in ("Cash", "Bank"):
        frappe.throw(_("Only enabled cash/bank payment methods can be corrected here."))
    profile = frappe.get_doc("POS Profile", invoice.pos_profile)
    if mode not in {p.mode_of_payment for p in profile.payments}:
        frappe.throw(_("The payment method is not configured in this POS Profile."))
    accounts = [r.default_account for r in mop.accounts if r.company == invoice.company]
    if len(accounts) != 1:
        frappe.throw(_("Configure exactly one payment account for this company and method."))
    account = frappe.get_doc("Account", accounts[0])
    if account.is_group or account.disabled or account.company != invoice.company or account.account_currency != invoice.currency or account.account_type not in ("Cash", "Bank"):
        frappe.throw(_("The payment account must be an enabled company-currency cash or bank account."))
    if account.account_type != mop.type:
        frappe.throw(_("The payment method type must match its Cash or Bank account type. Please contact the software team."))
    return account.name


@frappe.whitelist(methods=["POST"])
def correct_settled_bill_mop(data=None, **kwargs):
    data = payload(data, **kwargs)
    def action(closing):
        require_reopened(closing)
        invoice = frappe.get_doc("POS Invoice", data.get("pos_invoice"), for_update=True)
        invoice.check_permission("read")
        accounting = validate_invoice(invoice, closing)
        if not str(data.get("expected_payment_revision", "")).isdigit() or cint(data.expected_payment_revision) != cint(invoice.get("custom_payment_revision")):
            frappe.throw(_("Bill payments changed. Refresh the bill before correcting it."))
        before = payment_rows(invoice)
        wanted = data.get("payments")
        if not isinstance(wanted, list) or not wanted or {r.get("payment_row") for r in wanted} != {r["payment_row"] for r in before} or len(wanted) != len(before):
            frappe.throw(_("Send every non-zero payment row exactly once."))
        old_by_id = {r["payment_row"]: r for r in before}
        old_modes = [r["mode_of_payment"] for r in before]
        if len(set(old_modes)) != len(old_modes):
            frappe.throw(_("Repeated original payment modes require accounts review."))
        after, changes = [], []
        for change in wanted:
            if set(change) != {"payment_row", "mode_of_payment"}:
                frappe.throw(_("Only payment_row and mode_of_payment may be supplied; amounts cannot change."))
            old = old_by_id[change["payment_row"]]
            if old["amount"] <= 0:
                frappe.throw(_("Only positive settled payments are supported."))
            # Validate the original account too, including an old method disabled since sale.
            old_account = frappe.get_doc("Account", old["account"])
            if old_account.account_type not in ("Cash", "Bank") or old_account.account_currency != invoice.currency:
                frappe.throw(_("The original payment account requires accounts review."))
            account = new_account(change["mode_of_payment"], invoice)
            matching = [p for p in accounting.payments if p.mode_of_payment == old["mode_of_payment"] and flt(p.amount) == old["amount"] and p.account == old["account"]]
            if len(matching) != 1:
                frappe.throw(_("POS and accounting payment rows do not match; no correction was made."))
            after.append({**old, "mode_of_payment": change["mode_of_payment"], "account": account})
            changes.append((old["payment_row"], matching[0].name, change["mode_of_payment"], account))
        if len({r["mode_of_payment"] for r in after}) != len(after):
            frappe.throw(_("Use distinct payment methods for split payments."))
        if all(old_by_id[r["payment_row"]]["mode_of_payment"] == r["mode_of_payment"] for r in after):
            frappe.throw(_("The payment methods have not changed."))
        # Validate native repost policy and deferred-revenue restrictions first.
        accounting.validate_for_repost()
        # Narrow, audited settlement metadata change. Preserve the completed-sale
        # payload and all amounts; the native repost will reverse/rebuild GL only.
        for pos_row, accounting_row, mode, account in changes:
            for row in (pos_row, accounting_row):
                frappe.db.set_value("Sales Invoice Payment", row, {"mode_of_payment": mode, "account": account,
                    "type": frappe.get_cached_value("Mode of Payment", mode, "type")}, update_modified=False)
        revision = cint(invoice.get("custom_payment_revision")) + 1
        for doc in (invoice, accounting):
            frappe.db.set_value(doc.doctype, doc.name, "custom_payment_revision", revision)
            frappe.clear_document_cache(doc.doctype, doc.name)
            doc.add_comment("Info", text=f"Payment method corrected by {frappe.session.user}. Reference: {data.operation_reference}. {data.reason}")
        repost = frappe.get_doc({"doctype": "Repost Accounting Ledger", "company": accounting.company,
            "delete_cancelled_entries": 0, "vouchers": [{"voucher_type": "Sales Invoice", "voucher_no": accounting.name}]})
        repost.flags.ignore_permissions = True
        previous_repost = frappe.flags.get("through_repost_accounting_ledger")
        try:
            repost.insert()
            repost.submit()  # A single voucher executes synchronously, in this transaction.
        finally:
            frappe.flags.through_repost_accounting_ledger = previous_repost
        result = recalculate(closing)
        return {**result, "invoice_name": invoice.name, "accounting_invoice": accounting.name,
                "payment_revision": revision, "accounting_repost": repost.name,
                "before_payments": before, "payments": after}
    return operation("Bill MOP Correction", data, CHANGE_MOP, action)


def guard_day_document(doc, method=None):
    if frappe.flags.get("retail_day_correction"):
        return
    if method == "before_cancel" or (doc.get("amended_from") and method in ("before_insert", "before_submit", "on_trash")):
        frappe.throw(_("Use the authorized day reopening/reclosing API so the revision and audit are retained."))
    if doc.get("branch") and method in ("before_insert", "before_validate", "before_submit"):
        frappe.db.get_value("Branch", doc.branch, "name", for_update=True)
    if method == "on_trash" and doc.docstatus != 0:
        frappe.throw(_("Closing history must be retained."))
    old = doc.get_doc_before_save()
    if old and (old.docstatus != 0 or doc.get("amended_from")) and any(doc.get(f) != old.get(f) for f in ("branch", "business_date")):
        frappe.throw(_("The business date and branch of a closing revision cannot change."))
    if old and any(doc.get(f) != old.get(f) for f in ("amended_from", "revision", "reopened_by", "reopened_at", "reopen_reason")):
        frappe.throw(_("Day revision identity cannot be changed."))


def guard_corrected_document(doc, method=None):
    if frappe.flags.get("retail_day_correction"):
        return
    if doc.doctype in ("POS Invoice", "Sales Invoice"):
        old = doc.get_doc_before_save()
        if method == "before_cancel" and doc.get("custom_payment_revision"):
            frappe.throw(_("This bill has payment corrections. Use an authorized return instead of cancelling it."))
        if old and (doc.get("custom_payment_revision") != old.get("custom_payment_revision") or
                    (old.docstatus == 1 and payment_rows(doc) != payment_rows(old))):
            frappe.throw(_("Use the authorized settled-bill payment correction API."))


def guard_sale_day(doc, method=None):
    """Serialize late sync with close/reopen, including completed offline receipts."""
    counter = doc.get("pos_counter") or doc.get("pos_branch_counter")
    branch = doc.get("pos_branch") or (frappe.db.get_value("POS Branch Counter", counter, "branch") if counter else None)
    if not branch:
        return
    frappe.db.get_value("Branch", branch, "name", for_update=True)
    date = doc.posting_date
    if doc.get("pos_cashier_shift"):
        date = getdate(frappe.db.get_value("POS Cashier Shift", doc.pos_cashier_shift, "opening_time"))
    from retail.api.pos_sync import _assert_day_not_closed
    from retail.pos_completed_sale import audit_validation
    audit_validation(doc, "Late transaction after day close", lambda: _assert_day_not_closed(branch, date))


@frappe.whitelist(methods=["GET"])
def get_bill_payment_details(day_closing, pos_invoice):
    closing = frappe.get_doc(DAY, day_closing)
    authorize(closing, CHANGE_MOP)
    invoice = frappe.get_doc("POS Invoice", pos_invoice)
    invoice.check_permission("read")
    validate_invoice(invoice, closing)
    return {"pos_invoice": invoice.name, "payment_revision": cint(invoice.get("custom_payment_revision")),
            "payments": payment_rows(invoice), "day_closing": closing.name}


def guard_closed_shift(doc, method=None):
    if frappe.flags.get("retail_day_correction"):
        return
    old = doc.get_doc_before_save()
    if old and old.status == "Closed" and any(doc.get(f) != old.get(f) for f in
        ("branch", "opening_time", "cashier_employee", "closing_amount", "expected_cash", "variance")):
        frappe.throw(_("Use the authorized day correction API to adjust a closed shift."))


@frappe.whitelist(methods=["GET"])
def get_day_correction_actions(day_closing):
    """Native form visibility; mutations always authorize independently."""
    from retail.access_control import is_super_admin
    from retail.module_access import require
    from retail.pos_privileges import profile_privileges
    require("POS")
    closing = frappe.get_doc(DAY, day_closing)
    closing.check_permission("read")
    privileges = set()
    if is_super_admin():
        privileges = {REOPEN, ADJUST, CHANGE_MOP, "DAY_CLOSING"}
    elif "POS Integration User" not in frappe.get_roles():
        for employee in frappe.get_all("Employee", filters={"user_id": frappe.session.user,
                "status": "Active", "branch": closing.branch, "pos_login_enabled": 1},
                fields=["pos_operator_privilege"]):
            privileges.update(k for k, allowed in profile_privileges(employee.pos_operator_privilege).items() if allowed)
    return {"reopen": closing.docstatus == 1 and REOPEN in privileges,
            "recalculate": closing.docstatus == 0 and bool(closing.amended_from) and "DAY_CLOSING" in privileges,
            "reclose": closing.docstatus == 0 and bool(closing.amended_from) and "DAY_CLOSING" in privileges}


def authorize_day_close(branch, business_date):
    """Keep ordinary POS clients compatible; revised days need a named manager."""
    from retail.api.pos_sync import _assert_pos_user
    name = frappe.db.get_value(DAY, {"branch": branch, "business_date": business_date,
        "docstatus": ["!=", 2]}, "name")
    if name:
        closing = frappe.get_doc(DAY, name)
        if closing.amended_from:
            authorize(closing, "DAY_CLOSING")
            return
    _assert_pos_user()
    if "System Manager" not in frappe.get_roles() and not frappe.db.exists("POS Branch Counter",
            {"branch": branch, "integration_user": frappe.session.user, "is_active": 1, "allow_offline_sync": 1}):
        deny()


def close_branch_day(branch, business_date):
    """Recalculate and submit the current revision atomically, without a preview hash."""
    from retail.retail_app.doctype.pos_branch_day_closing.pos_branch_day_closing import make_day_closing
    if not branch:
        frappe.throw(_("Branch is required."))
    business_date = getdate(business_date)
    frappe.db.get_value("Branch", branch, "name", for_update=True)
    authorize_day_close(branch, business_date)
    doc = make_day_closing(branch, business_date)
    closing = frappe.get_doc(DAY, doc.name, for_update=True)
    if closing.docstatus == 1:
        return {**closing.as_dict(), **view(closing)}
    check_period(company_for(branch), business_date)
    if closing.amended_from:
        require_reopened(closing)
    with correction_context():
        recalculate(closing)
        closing.manager_user = frappe.session.user
        closing.closed_at = now_datetime()
        if closing.amended_from:
            closing.flags.ignore_permissions = True
        closing.submit()
    return {**closing.as_dict(), **view(closing)}
