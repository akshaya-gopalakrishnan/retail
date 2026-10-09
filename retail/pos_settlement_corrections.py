"""Audited POS settlement changes using native invoice reposts and Payment Entries."""
import hashlib

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from retail import pos_day_corrections as days
from retail.pos_operations import canonical

PRIVILEGE = "CHANGE_BILL_SETTLEMENT"
ACTIONS = {"SetCredit", "CollectCredit", "ChangeCollectionMOP", "ReverseCollection"}


def invoice_pair(name, closing):
    pos = frappe.get_doc("POS Invoice", name, for_update=True)
    pos.check_permission("read")
    shift = frappe.get_doc("POS Cashier Shift", pos.pos_cashier_shift)
    if shift.branch != closing.branch or pos.company != days.company_for(closing.branch):
        frappe.throw(_("The invoice must belong to this branch and company."))
    if pos.docstatus != 1 or pos.is_return or not pos.consolidated_invoice:
        frappe.throw(_("A submitted, individually posted POS sale is required."))
    if frappe.db.count("POS Invoice", {"consolidated_invoice": pos.consolidated_invoice, "docstatus": 1}) != 1:
        frappe.throw(_("Combined accounting invoices require accounts review."))
    si = frappe.get_doc("Sales Invoice", pos.consolidated_invoice, for_update=True)
    currency = frappe.get_cached_value("Company", pos.company, "default_currency")
    for doc in (pos, si):
        if (doc.docstatus != 1 or doc.customer != pos.customer or doc.company != pos.company
                or doc.currency != currency or flt(doc.conversion_rate) != 1
                or flt(doc.change_amount) or flt(doc.write_off_amount) or flt(doc.loyalty_amount)
                or flt(doc.get("custom_gift_voucher_amount"))):
            frappe.throw(_("Currency, change, write-off, loyalty or voucher settlements require accounts review."))
        if frappe.db.exists(doc.doctype, {"return_against": doc.name, "docstatus": 1}):
            frappe.throw(_("Invoices with returns require accounts review."))
    if si.get("advances"):
        frappe.throw(_("Invoices with allocated advances require accounts review."))
    if flt(pos.paid_amount) != flt(si.paid_amount):
        frappe.throw(_("POS and accounting payment amounts do not match."))
    return pos, si, shift


def collections(si):
    names = frappe.db.sql("""select distinct p.name from `tabPayment Entry` p
        join `tabPayment Entry Reference` r on r.parent=p.name and r.parenttype='Payment Entry'
        where p.docstatus=1 and r.reference_doctype='Sales Invoice' and r.reference_name=%s
        order by p.name""", si.name, pluck=True)
    return [frappe.get_doc("Payment Entry", name, for_update=True) for name in names]


def snapshot(pos, si):
    payments = collections(si)
    state = {"pos_invoice": pos.name, "accounting_invoice": si.name, "customer": si.customer,
        "payment_revision": cint(pos.get("custom_payment_revision")),
        "initial_paid_amount": flt(si.paid_amount), "outstanding_amount": flt(si.outstanding_amount),
        "payments": days.payment_rows(pos),
        "collections": [{"payment_entry": p.name, "modified": str(p.modified), "posting_date": str(p.posting_date),
            "mode_of_payment": p.mode_of_payment, "amount": flt(p.paid_amount), "account": p.paid_to,
            "cashier_shift": p.get("pos_cashier_shift"), "counter_session": p.get("pos_counter_session"),
            "references": [{"doctype": r.reference_doctype, "name": r.reference_name,
                            "amount": flt(r.allocated_amount)} for r in p.references]} for p in payments]}
    state["settlement_hash"] = hashlib.sha256(canonical(state).encode()).hexdigest()
    return state


def ensure_open(closing):
    if closing.docstatus != 0 or frappe.db.exists(days.DAY, {"branch": closing.branch,
            "business_date": closing.business_date, "docstatus": 1}):
        frappe.throw(_("Reopen the affected closed business day before correcting settlement."))


@frappe.whitelist(methods=["GET"])
def get_settlement_details(day_closing, pos_invoice):
    closing = frappe.get_doc(days.DAY, day_closing)
    days.authorize(closing, PRIVILEGE)
    pos, si, _shift = invoice_pair(pos_invoice, closing)
    return {"day_closing": closing.name, **snapshot(pos, si)}


def repost(si):
    si.validate_for_repost()
    doc = frappe.get_doc({"doctype": "Repost Accounting Ledger", "company": si.company,
        "delete_cancelled_entries": 0,
        "vouchers": [{"voucher_type": "Sales Invoice", "voucher_no": si.name}]})
    doc.flags.ignore_permissions = True
    previous = frappe.flags.get("through_repost_accounting_ledger")
    try:
        doc.insert()
        doc.submit()
    finally:
        frappe.flags.through_repost_accounting_ledger = previous
    return doc.name


def payment_period(company, date):
    from erpnext.accounts.general_ledger import validate_accounting_period
    days.check_period(company, date)
    validate_accounting_period([frappe._dict(company=company, posting_date=getdate(date), voucher_type="Payment Entry")])


def check_bank(payment):
    if payment.clearance_date or frappe.db.sql("""select p.name from `tabBank Transaction Payments` p
        join `tabBank Transaction` b on b.name=p.parent
        where p.payment_document='Payment Entry' and p.payment_entry=%s and b.docstatus=1 limit 1""", payment.name):
        frappe.throw(_("This collection has been bank cleared or reconciled. Please contact the accounts team."))


def collection_context(closing, shift_name, session_name):
    shift = frappe.get_doc("POS Cashier Shift", shift_name, for_update=True)
    session = frappe.get_doc("POS Counter Session", session_name, for_update=True)
    if (shift.branch != closing.branch or getdate(shift.opening_time) != getdate(closing.business_date)
            or session.branch != closing.branch or session.cashier_shift != shift.name
            or session.cashier_employee != shift.cashier_employee):
        frappe.throw(_("Collection shift and session must belong to this business day and branch."))
    counter = frappe.get_doc("POS Branch Counter", session.counter)
    if counter.branch != closing.branch or counter.company != days.company_for(closing.branch):
        frappe.throw(_("The collection counter belongs to another company or branch."))
    return shift, session, counter


def validate_collection(payment, pos, si, closing):
    payment.check_permission("read")
    if (payment.docstatus != 1 or payment.payment_type != "Receive" or payment.party_type != "Customer"
            or payment.party != si.customer or payment.company != si.company
            or payment.get("pos_branch") != closing.branch or getdate(payment.posting_date) != getdate(closing.business_date)
            or payment.get("pos_credit_invoice") not in (None, "", pos.name)
            or payment.paid_from_account_currency != si.currency or payment.paid_to_account_currency != si.currency
            or flt(payment.source_exchange_rate) != 1 or flt(payment.target_exchange_rate) != 1
            or flt(payment.unallocated_amount) or flt(payment.difference_amount)
            or payment.deductions or payment.taxes or flt(payment.paid_amount) != flt(payment.received_amount)
            or len(payment.references) != 1):
        frappe.throw(_("Only a simple, fully allocated POS customer collection can be corrected here."))
    ref = payment.references[0]
    if (ref.reference_doctype != "Sales Invoice" or ref.reference_name != si.name
            or flt(ref.allocated_amount) != flt(payment.paid_amount)):
        frappe.throw(_("The collection allocation does not match this invoice."))
    if frappe.get_cached_value("Account", payment.paid_to, "account_type") not in ("Cash", "Bank"):
        frappe.throw(_("This collection account requires accounts review."))
    check_bank(payment)
    payment_period(payment.company, payment.posting_date)
    return collection_context(closing, payment.pos_cashier_shift, payment.pos_counter_session)


def create_collection(pos, si, closing, data, amount, context, amended_from=None):
    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    shift, session, counter = context
    payment_period(si.company, closing.business_date)
    account = days.new_account(data.get("mode_of_payment"), pos)
    if data.mode_of_payment not in {r.mode_of_payment for r in frappe.get_doc("POS Profile", counter.pos_profile).payments}:
        frappe.throw(_("The payment method is not configured for the collection counter."))
    pe = get_payment_entry("Sales Invoice", si.name, bank_account=account, bank_amount=amount,
        reference_date=closing.business_date, ignore_permissions=True)
    # No discounts, deductions, FX gains or excess/unallocated collections.
    pe.set("deductions", [])
    pe.set("taxes", [])
    pe.paid_amount = pe.received_amount = amount
    pe.set("references", [{"reference_doctype": "Sales Invoice", "reference_name": si.name, "allocated_amount": amount}])
    pe.posting_date = pe.reference_date = closing.business_date
    pe.mode_of_payment = data.mode_of_payment
    pe.reference_no = data.get("reference_no") or data.operation_reference
    pe.pos_credit_invoice = pos.name
    pe.pos_branch = closing.branch
    pe.pos_counter = counter.name
    pe.pos_cashier_shift = shift.name
    pe.pos_cashier_employee = shift.cashier_employee
    pe.pos_counter_session = session.name
    pe.pos_terminal_id = counter.terminal_id
    pe.external_pos_reference = "settlement-" + hashlib.sha256(data.operation_reference.encode()).hexdigest()
    pe.custom_settlement_operation = data.operation_reference
    pe.amended_from = amended_from
    pe.flags.ignore_permissions = True
    pe.insert()
    pe.submit()
    if flt(pe.unallocated_amount) or flt(pe.difference_amount):
        frappe.throw(_("The collection was not fully allocated; no correction was saved."))
    return pe


@frappe.whitelist(methods=["POST"])
def correct_bill_settlement(data=None, **kwargs):
    data = days.payload(data, **kwargs)
    if data.get("action") not in ACTIONS:
        frappe.throw(_("Choose SetCredit, CollectCredit, ChangeCollectionMOP or ReverseCollection."))
    allowed = {"day_closing", "operation_reference", "reason", "pos_invoice", "action", "expected_settlement_hash", "customer"}
    allowed.update({
        "SetCredit": set(),
        "CollectCredit": {"amount", "mode_of_payment", "cashier_shift", "counter_session", "reference_no"},
        "ChangeCollectionMOP": {"payment_entry", "mode_of_payment", "reference_no"},
        "ReverseCollection": {"payment_entry"},
    }[data.action])
    if set(data) - allowed:
        frappe.throw(_("The request contains fields not allowed for this settlement action."))
    def action(closing):
        ensure_open(closing)
        pos, si, sale_shift = invoice_pair(data.get("pos_invoice"), closing)
        before = snapshot(pos, si)
        if not data.get("expected_settlement_hash") or data.expected_settlement_hash != before["settlement_hash"]:
            frappe.throw(_("Settlement changed. Refresh the bill before correcting it."))
        if data.get("customer") and data.customer != pos.customer:
            frappe.throw(_("Settlement correction cannot change the invoice customer. Please contact the accounts team."))
        result = {}
        if data.action == "SetCredit":
            if getdate(sale_shift.opening_time) != getdate(closing.business_date):
                frappe.throw(_("Reopen the sale's original business day to remove its initial payment."))
            if before["collections"] or flt(si.outstanding_amount) or flt(si.paid_amount) <= 0:
                frappe.throw(_("SetCredit requires an initially fully paid bill without later collections."))
            days.validate_invoice(pos, closing)
            payment_values = lambda doc: sorted((p.mode_of_payment, p.account, flt(p.amount), flt(p.base_amount))
                for p in doc.payments if flt(p.amount))
            if payment_values(pos) != payment_values(si) or flt(sum(p.amount for p in si.payments), si.precision("paid_amount")) != flt(si.paid_amount):
                frappe.throw(_("POS and accounting payment rows do not match."))
            if any(flt(p.amount) < 0 or frappe.get_cached_value("Account", p.account, "account_type") not in ("Cash", "Bank")
                    for p in si.payments if flt(p.amount)):
                frappe.throw(_("Only initially recorded Cash/Bank payments can be moved to credit."))
            from retail.api.pos_sync import _validate_credit_customer
            _validate_credit_customer(pos.customer, pos.company, si.paid_amount)
            si.validate_for_repost()
            for doc in (pos, si):
                for row in doc.payments:
                    frappe.db.set_value("Sales Invoice Payment", row.name, {"amount": 0, "base_amount": 0}, update_modified=False)
                frappe.db.set_value(doc.doctype, doc.name, {"paid_amount": 0, "base_paid_amount": 0})
                frappe.clear_document_cache(doc.doctype, doc.name)
            result["accounting_repost"] = repost(si)
        elif data.action == "CollectCredit":
            amount = float(days.money(data.get("amount")))
            if amount <= 0 or amount > flt(si.outstanding_amount) or amount != flt(amount, si.precision("outstanding_amount")):
                frappe.throw(_("Collection must be positive and no greater than the current outstanding amount."))
            context = collection_context(closing, data.get("cashier_shift"), data.get("counter_session"))
            pe = create_collection(pos, si, closing, data, amount, context)
            result["payment_entry"] = pe.name
        else:
            pe = frappe.get_doc("Payment Entry", data.get("payment_entry"), for_update=True)
            context = validate_collection(pe, pos, si, closing)
            if data.action == "ChangeCollectionMOP":
                if data.get("mode_of_payment") == pe.mode_of_payment:
                    frappe.throw(_("The payment method has not changed."))
                days.new_account(data.get("mode_of_payment"), pos)
            else:
                from retail.api.pos_sync import _validate_credit_customer
                _validate_credit_customer(pos.customer, pos.company, pe.paid_amount)
            amount = flt(pe.paid_amount)
            frappe.db.set_value(pe.doctype, pe.name, "custom_settlement_operation", data.operation_reference)
            pe.reload()
            pe.flags.ignore_permissions = True
            pe.cancel()
            result["cancelled_payment_entry"] = pe.name
            si.reload()
            if data.action == "ChangeCollectionMOP":
                replacement = create_collection(pos, si, closing, data, amount, context, amended_from=pe.name)
                result["payment_entry"] = replacement.name
        revision = cint(pos.get("custom_payment_revision")) + 1
        for doc in (pos, si):
            frappe.db.set_value(doc.doctype, doc.name, "custom_payment_revision", revision)
            frappe.clear_document_cache(doc.doctype, doc.name)
            doc.add_comment("Info", text=f"Settlement {data.action} by {frappe.session.user}. Reference: {data.operation_reference}. {data.reason}")
        # Refresh POS from the actual accounting balance (also handles older collections
        # whose pos_credit_invoice link was not populated).
        si.reload()
        frappe.db.set_value("POS Invoice", pos.name, "outstanding_amount", si.outstanding_amount)
        pos.reload()
        pos.set_status(update=True)
        return {**days.recalculate(closing), **result, "action": data.action,
                "before_settlement": before, "settlement": snapshot(pos, si), "invoice_name": pos.name}
    return days.operation("Bill Settlement Correction", data, PRIVILEGE, action)


def guard_payment(doc, method=None):
    if frappe.flags.get("retail_day_correction"):
        return
    if method == "before_submit" and doc.get("pos_cashier_shift"):
        shift = frappe.get_doc("POS Cashier Shift", doc.pos_cashier_shift)
        frappe.db.get_value("Branch", shift.branch, "name", for_update=True)
        from retail.api.pos_sync import _assert_day_not_closed
        _assert_day_not_closed(shift.branch, getdate(shift.opening_time))
    old = doc.get_doc_before_save()
    if doc.get("custom_settlement_operation") and not old:
        frappe.throw(_("Settlement correction references are assigned by the authorized API."))
    if doc.get("custom_settlement_operation") or (old and old.get("custom_settlement_operation")):
        if method in ("before_cancel", "on_trash"):
            frappe.throw(_("Use the authorized settlement correction API for this collection."))
        if old and any(doc.get(f) != old.get(f) for f in ("custom_settlement_operation", "pos_credit_invoice",
                "pos_branch", "pos_cashier_shift", "pos_counter_session", "mode_of_payment", "paid_to", "paid_from",
                "paid_amount", "received_amount")):
            frappe.throw(_("Use the authorized settlement correction API for this collection."))

        if old and old.docstatus == 1:
            allocations = lambda d: [(r.reference_doctype, r.reference_name, flt(r.allocated_amount)) for r in d.references]
            if allocations(doc) != allocations(old):
                frappe.throw(_("Use the authorized settlement correction API to change collection allocations."))
