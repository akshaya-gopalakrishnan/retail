"""Atomic cancellation of a single completed POS sale; references remain permanent."""
from contextlib import contextmanager

import frappe
from frappe.utils import cint, escape_html, flt, now_datetime

from retail import pos_operations


@contextmanager
def cancellation_context(invoice):
    previous = frappe.flags.get("retail_pos_cancellation")
    frappe.flags.retail_pos_cancellation = invoice.name
    try:
        yield
    finally:
        frappe.flags.retail_pos_cancellation = previous


def cancel(payload):
    from retail.api import pos_sync as api
    from retail.pos_external_refs import validate_reference

    api._assert_pos_user()
    validate_reference(payload.get("operation_reference"), "operation_reference")
    if payload.get("pos_invoice_name"):
        validate_reference(payload.pos_invoice_name, "pos_invoice_name")
    else:
        validate_reference(payload.get("pos_bill_no"), "pos_bill_no")
        validate_reference(payload.get("original_external_pos_reference"), "original_external_pos_reference")
    if payload.get("reason") is not None and not isinstance(payload.reason, str):
        frappe.throw("Cancellation reason must be text when supplied.")
    counter = api._counter(payload.get("branch"), payload.get("counter_code"), completed=True)
    resolve_target(payload, counter)  # Reauthorize invoice identity before stored retries.

    def action():
        # The branch lock serializes this lookup with sale posting and recovery.
        frappe.db.get_value("Branch", counter.branch, "name", for_update=True)
        identity = resolve_target(payload, counter, for_update=True)
        reference = identity.external_pos_reference if identity else payload.original_external_pos_reference
        transaction_identity = frappe.db.get_value("POS Accepted Transaction",
            {"external_pos_reference": reference}, ["name", "customer", "company", "branch", "counter"],
            as_dict=True, for_update=True)
        if transaction_identity and (transaction_identity.company != counter.company
                or transaction_identity.branch != counter.branch or transaction_identity.counter != counter.name):
            frappe.throw("Original sale belongs to another company, branch or counter.", frappe.PermissionError)
        customer = identity.customer if identity else (transaction_identity.customer if transaction_identity else None)
        if customer:
            frappe.db.get_value("Customer", customer, "name", for_update=True)
        transaction = (frappe.get_doc("POS Accepted Transaction", transaction_identity.name, for_update=True)
            if transaction_identity else None)
        bill_no = identity.pos_bill_no if identity else payload.pos_bill_no
        target_request = {"company": counter.company, "counter": counter.name,
            "payload": {"branch": counter.branch, "counter_code": counter.counter_code,
                "pos_bill_no": bill_no, "original_external_pos_reference": reference}}

        def apply():
            if not identity:
                return cancel_unposted(payload, transaction, counter)
            invoice = frappe.get_doc("POS Invoice", identity.name, for_update=True)
            return cancel_posted(invoice, transaction, counter, payload)

        result = pos_operations.execute("POS Cancelled Sale", reference, target_request, apply,
            log_type="POS Cancellation")
        if result.get("duplicate"):
            result["already_cancelled"] = True
        return result

    # Roll back all reversals and the claimed receipt even when called by Python.
    frappe.db.savepoint("pos_cancel_request")
    try:
        return pos_operations.execute("POS Cancellation", payload.operation_reference,
            {"actor": frappe.session.user, "company": counter.company,
             "counter": counter.name, "payload": dict(payload)}, action)
    except Exception:
        frappe.db.rollback(save_point="pos_cancel_request")
        raise


def resolve_target(payload, counter, for_update=False):
    filters = payload.pos_invoice_name if payload.get("pos_invoice_name") else {
        "external_pos_reference": payload.original_external_pos_reference}
    identity = frappe.db.get_value("POS Invoice", filters,
        ["name", "company", "customer", "pos_branch", "pos_counter", "external_pos_reference", "pos_bill_no"],
        as_dict=True, for_update=for_update)
    if not identity:
        if payload.get("pos_invoice_name"):
            frappe.throw("POS Invoice not found.")
        return None
    if (identity.company != counter.company or identity.pos_branch != counter.branch
            or identity.pos_counter != counter.name):
        frappe.throw("Invoice belongs to another company, branch or counter.", frappe.PermissionError)
    if payload.get("original_external_pos_reference") and payload.original_external_pos_reference != identity.external_pos_reference:
        frappe.throw("Original external reference does not match the POS Invoice.")
    if payload.get("pos_bill_no") and payload.pos_bill_no != identity.pos_bill_no:
        frappe.throw("POS bill number does not match the original external reference.")
    return identity


def cancellation_reason(payload):
    reason = f"POS cancellation {payload.operation_reference} by {frappe.session.user}"
    supplied_reason = (payload.get("reason") or "").strip()
    return f"{reason}: {supplied_reason}" if supplied_reason else reason


def retain_cancelled_transaction(transaction, allocations, reason):
    if not transaction:
        return
    frappe.db.set_value(transaction.doctype, transaction.name, {
        "status": "Cancelled", "resolved_at": now_datetime(), "exception_reason": reason})
    transaction.status = "Cancelled"
    for allocation in allocations:
        frappe.db.set_value(allocation.doctype, allocation.name, {
            "status": "Cancelled", "unresolved_amount": 0, "resolved_at": now_datetime()})
    from retail.pos_settlements import audit, refresh_day
    audit(transaction, reason)
    refresh_day(transaction)


def cancel_unposted(payload, transaction, counter):
    if frappe.db.has_column("Sales Invoice", "external_pos_reference") and frappe.db.exists(
            "Sales Invoice", {"external_pos_reference": payload.original_external_pos_reference}):
        frappe.throw("This reference belongs to legacy Sales Invoice accounting; accounts review is required.")
    approvals = frappe.db.sql("""select external_reference from `tabPOS Sync Log`
        where sync_type='Voucher Redemption' and status='Success'
        and json_unquote(json_extract(request_json, '$.external_pos_reference'))=%s""",
        payload.original_external_pos_reference, pluck=True)
    if any(not pos_operations.find("Voucher Reversal", reference) for reference in approvals):
        frappe.throw("Reverse the bill's voucher redemption approvals before cancelling it.")
    if frappe.db.exists("POS Settlement Allocation", {
            "source_external_reference": payload.original_external_pos_reference, "status": ["!=", "Cancelled"]}):
        frappe.throw("Another accepted transaction depends on this bill; resolve it first.")
    for pending in frappe.get_all("POS Accepted Transaction", filters={"company": counter.company,
            "status": ["!=", "Cancelled"], "pos_invoice": ["is", "not set"]},
            fields=["name", "payload_json", "correction_payload_json"]):
        if transaction and pending.name == transaction.name:
            continue
        data = frappe.parse_json(pending.correction_payload_json or pending.payload_json)
        if any(row.get("original_external_pos_reference") == payload.original_external_pos_reference
                for row in [data] + (data.get("items") or [])):
            frappe.throw("An accepted return/exchange depends on this bill; resolve it first.")
    if transaction:
        data = frappe.parse_json(transaction.get("correction_payload_json") or transaction.payload_json)
        if (transaction.pos_invoice or transaction.sales_invoice
                or transaction.sync_type not in ("Sales Invoice", "Credit Sales Invoice")
                or data.get("pos_bill_no") != payload.pos_bill_no
                or any(flt(row.get("qty")) < 0 for row in data.get("items") or [])):
            frappe.throw("Accepted transaction does not match an unposted ordinary sale with this bill number.")
        from retail.pos_offline_promotions import rows
        if rows(data) or data.get("loyalty_redemption") or data.get("voucher_redemption") or data.get("voucher_redemptions"):
            frappe.throw("Voucher/loyalty redemptions require accounts review before cancellation.")
        allocations = [frappe.get_doc("POS Settlement Allocation", name, for_update=True)
            for name in frappe.get_all("POS Settlement Allocation", filters={"transaction": transaction.name}, pluck="name")]
        if any(row.applied_amount or row.reconciliation_reference for row in allocations):
            frappe.throw("This accepted transaction has accounting allocations; accounts review is required.")
        retain_cancelled_transaction(transaction, allocations, cancellation_reason(payload))
    return {"status": "Success", "cancellation_status": "Cancelled Before Sync",
        "pos_invoice_name": None, "invoice_name": None, "sales_invoice": None, "docstatus": None,
        "original_external_pos_reference": payload.original_external_pos_reference,
        "pos_bill_no": payload.pos_bill_no, "already_cancelled": False}


def assert_not_cancelled(reference):
    if pos_operations.find("POS Cancelled Sale", reference):
        frappe.throw("This original POS sale was cancelled. Post its replacement with a new external_pos_reference.")


def cancel_posted(invoice, transaction, counter, payload):
    from retail.api import pos_sync as api
    if invoice.docstatus == 2:
        return response(invoice, transaction, already_cancelled=True)
    accounting, allocations = validate_sale(invoice, transaction, counter)
    with cancellation_context(invoice):
        invoice.flags.ignore_permissions = True
        invoice.cancel()  # Retail reverses the singleton merge and native SI first.
    if frappe.db.get_value("Sales Invoice", accounting.name, "docstatus") != 2:
        frappe.throw("Accounting cancellation did not complete.")
    reason = cancellation_reason(payload)
    invoice.add_comment("Info", text=escape_html(reason))
    accounting.add_comment("Info", text=escape_html(reason))
    retain_cancelled_transaction(transaction, allocations, reason)
    if invoice.get("pos_cashier_shift"):
        totals = api._refresh_cashier_shift_cash_totals(invoice.pos_cashier_shift)
        shift = frappe.get_doc("POS Cashier Shift", invoice.pos_cashier_shift)
        frappe.db.set_value(shift.doctype, shift.name, "variance", flt(shift.closing_amount) - totals.expected_cash)
    return response(invoice, transaction, accounting.name)


def response(invoice, transaction, accounting=None, already_cancelled=False):
    return {"status": "Success", "cancellation_status": "Cancelled", "doctype": "POS Invoice", "pos_invoice_name": invoice.name,
        "invoice_name": invoice.name, "docstatus": 2, "already_cancelled": already_cancelled,
        "sales_invoice": accounting or (transaction.sales_invoice if transaction else None),
        "original_external_pos_reference": invoice.external_pos_reference,
        "pos_bill_no": invoice.get("pos_bill_no")}


def validate_sale(invoice, transaction, counter):
    from retail.pos_completed_sale import payload_for
    from retail.pos_day_corrections import check_period, check_bank_settlement
    from retail.pos_settlement_corrections import collections
    from retail.pos_offline_promotions import rows

    if (invoice.docstatus != 1 or invoice.is_return or not payload_for(invoice)
            or invoice.company != counter.company or invoice.pos_counter != counter.name):
        frappe.throw("A submitted completed POS sale from this counter is required.")
    if cint(invoice.get("custom_payment_revision")):
        frappe.throw("This bill has payment corrections; use a return or accounts review.")
    payload = payload_for(invoice)
    if any(flt(item.get("qty")) < 0 for item in payload.get("items") or []):
        frappe.throw("Exchange receipts require a return or accounts review.")
    if (rows(payload) or payload.get("loyalty_redemption") or invoice.get("redeem_loyalty_points")
            or payload.get("voucher_redemption") or payload.get("voucher_redemptions")
            or flt(invoice.get("custom_gift_voucher_amount"))):
        frappe.throw("Voucher/loyalty redemptions require a return or accounts review before cancellation.")
    if not invoice.consolidated_invoice:
        frappe.throw("The bill must have its own posted accounting invoice before cancellation.")
    accounting = frappe.get_doc("Sales Invoice", invoice.consolidated_invoice, for_update=True)
    if (accounting.docstatus != 1 or not accounting.is_consolidated
            or accounting.company != invoice.company or accounting.customer != invoice.customer
            or frappe.db.count("POS Invoice", {"consolidated_invoice": accounting.name, "docstatus": 1}) != 1):
        frappe.throw("Combined or mismatched accounting requires accounts review.")
    merge_names = frappe.db.sql("""select m.name from `tabPOS Invoice Merge Log` m
        join `tabPOS Invoice Reference` r on r.parent=m.name and r.parenttype='POS Invoice Merge Log'
        where r.pos_invoice=%s and m.docstatus=1 and coalesce(m.pos_closing_entry, '')=''
        """, invoice.name, pluck=True)
    if len(merge_names) != 1:
        frappe.throw("Cancellation requires a single-receipt accounting merge.")
    merge = frappe.get_doc("POS Invoice Merge Log", merge_names[0], for_update=True)
    if len(merge.pos_invoices) != 1 or merge.consolidated_invoice != accounting.name:
        frappe.throw("Combined accounting requires accounts review.")
    for doc in (invoice, accounting):
        check_period(doc.company, doc.posting_date)
        if frappe.db.exists(doc.doctype, {"return_against": doc.name, "docstatus": 1}):
            frappe.throw("This bill has a submitted return; resolve it before cancellation.")
    business_date = transaction.business_date if transaction else invoice.posting_date
    if frappe.db.exists("POS Branch Day Closing", {
            "branch": counter.branch, "business_date": business_date, "docstatus": 1}):
        frappe.throw("Reopen the business day before cancelling this bill.")
    if frappe.db.sql("""select c.name from `tabPOS Closing Entry` c
            join `tabPOS Invoice Reference` r on r.parent=c.name and r.parenttype='POS Closing Entry'
            where r.pos_invoice=%s and c.docstatus=1 limit 1""", invoice.name):
        frappe.throw("Reopen the POS closing before cancelling this bill.")
    if invoice.get("pos_counter_session"):
        closing = frappe.db.get_value("POS Counter Session", invoice.pos_counter_session, "pos_closing_entry")
        if closing and frappe.db.get_value("POS Closing Entry", closing, "docstatus") == 1:
            frappe.throw("Reopen the POS closing before cancelling this bill.")
    if collections(accounting):
        frappe.throw("This bill has later collections; resolve them before cancellation.")
    expected_outstanding = (flt(accounting.rounded_total or accounting.grand_total)
        - flt(accounting.paid_amount) - flt(accounting.write_off_amount))
    if accounting.get("advances") or flt(accounting.outstanding_amount, 2) != flt(expected_outstanding, 2):
        frappe.throw("This bill has later accounting allocations; resolve them before cancellation.")
    check_bank_settlement(accounting.name, invoice.name)
    allocations = []
    if transaction:
        if transaction.pos_invoice != invoice.name or transaction.sales_invoice != accounting.name:
            frappe.throw("Accepted transaction accounting does not match this invoice.")
        allocations = [frappe.get_doc("POS Settlement Allocation", name, for_update=True)
            for name in frappe.get_all("POS Settlement Allocation", filters={"transaction": transaction.name}, pluck="name")]
        if any(row.settlement_type != "Credit Sale" or row.reconciliation_reference for row in allocations):
            frappe.throw("Credit-note allocations require a return or accounts review before cancellation.")
    # Include accepted-but-not-yet-posted returns and debt reductions.
    if frappe.db.exists("POS Settlement Allocation", {
            "source_external_reference": invoice.external_pos_reference, "status": ["!=", "Cancelled"]}):
        frappe.throw("Another accepted transaction depends on this bill; resolve it first.")
    for pending in frappe.get_all("POS Accepted Transaction", filters={
            "company": invoice.company, "customer": invoice.customer, "status": ["!=", "Cancelled"]},
            fields=["name", "payload_json", "correction_payload_json"]):
        if transaction and pending.name == transaction.name:
            continue
        data = frappe.parse_json(pending.correction_payload_json or pending.payload_json)
        references = [data] + (data.get("items") or [])
        if any(row.get("original_external_pos_reference") == invoice.external_pos_reference
               or row.get("original_pos_invoice") == invoice.name for row in references):
            frappe.throw("An accepted return/exchange depends on this bill; resolve it first.")
    return accounting, allocations
