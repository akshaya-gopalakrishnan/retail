"""Durable POS acceptance and recoverable native accounting allocations.

These records audit terminal facts; GL/Payment Ledger remain the financial ledger.
No helper commits. Receipt, acceptance and every successful effect commit together.
"""
import json
import math
from contextlib import contextmanager

import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, nowdate

from retail.pos_operations import canonical

FINANCIAL_TYPES = ("Sales Invoice", "Credit Sales Invoice", "Return")
NON_CASH = ("Credit Sale", "Credit Note", "Credit Note Redeemed")
RETURN_TYPES = ("Cash Refund", "Card Refund", "Reusable Customer Credit", "Original Debt Reduction")


class SettlementDocument(Document):
    def validate(self):
        if not self.flags.pos_settlement_write:
            frappe.throw("POS settlement records are maintained by the settlement service.")
        previous = self.get_doc_before_save()
        if previous and self.doctype == "POS Accepted Transaction":
            for field in ("payload_json", "external_pos_reference", "company", "customer", "sync_type"):
                if previous.get(field) != self.get(field):
                    frappe.throw("Accepted POS facts are immutable.")

    def on_trash(self):
        frappe.throw("POS acceptance and settlement audit records must be retained.")


def insert(values):
    doc = frappe.get_doc(values)
    doc.flags.pos_settlement_write = True
    return doc.insert(ignore_permissions=True)


def amount(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        frappe.throw("Settlement amounts must be numbers.")
    if not math.isfinite(number) or number < 0:
        frappe.throw("Settlement amounts must be finite and non-negative.")
    return flt(number, 2)


def payment_mode(row):
    return row.get("mode_of_payment") or row.get("mode")


def cash_payments(payload):
    return [r for r in payload.get("payments") or [] if payment_mode(r) not in NON_CASH]


def settlements(payload, is_return=False):
    """Normalize separately; never rewrite the terminal snapshot."""
    rows = []
    notes = list(payload.get("credit_note_redemptions") or [])
    credit_sale = payload.get("credit_sale_amount")
    for payment in payload.get("payments") or []:
        mode = payment_mode(payment)
        if mode == "Credit Sale":
            if credit_sale is not None:
                frappe.throw("Send Credit Sale once, either as credit_sale_amount or a payment descriptor.")
            credit_sale = amount(payment.get("amount"))
        elif mode in ("Credit Note", "Credit Note Redeemed"):
            notes.append(payment)
    for note in notes:
        ref = note.get("credit_note_external_reference") or note.get("source_external_reference")
        from retail.pos_external_refs import validate_reference
        validate_reference(ref, "credit_note_external_reference")
        rows.append(dict(settlement_type="Credit Note Redeemed", source_external_reference=ref,
                         requested_amount=amount(note.get("amount"))))
    if is_return:
        if notes or credit_sale is not None:
            frappe.throw("A return cannot also redeem customer credit or create a credit sale.")
        typ = payload.get("return_settlement_type") or (
            "Cash Refund" if cash_payments(payload) else "Reusable Customer Credit")
        if typ not in RETURN_TYPES:
            frappe.throw("Invalid return_settlement_type.")
        paid = sum(abs(float(p.get("amount", 0))) for p in cash_payments(payload))
        total = abs(float(payload.get("rounded_total", payload.get("grand_total", paid))))
        if typ in ("Reusable Customer Credit", "Original Debt Reduction") and paid:
            frappe.throw("A credit return cannot also have refund payment rows.")
        if typ in ("Cash Refund", "Card Refund") and flt(paid, 2) != flt(total, 2):
            frappe.throw("Refund payments must equal the return total.")
        if typ == "Original Debt Reduction" and not (
                payload.get("original_external_pos_reference") or payload.get("original_pos_invoice")):
            frappe.throw("Original Debt Reduction requires the original sale reference.")
        rows = [dict(settlement_type={"Reusable Customer Credit": "Credit Note Issued"}.get(typ, typ),
                     source_external_reference=payload.get("original_external_pos_reference"),
                     requested_amount=amount(total))]
    else:
        total = payload.get("rounded_total", payload.get("grand_total"))
        paid = sum(amount(p.get("amount")) for p in cash_payments(payload))
        redeemed = sum(r["requested_amount"] for r in rows)
        if total is not None:
            balance = flt(float(total) - paid - redeemed, 2)
            if balance < 0 or (credit_sale is not None and flt(credit_sale, 2) != balance):
                frappe.throw("POS settlement values do not match the completed bill total.")
            if credit_sale is None:
                credit_sale = balance
        if credit_sale is None and not rows:
            credit_sale = 0  # Legacy totals are resolved after native posting.
        if credit_sale is not None and (amount(credit_sale) or total is None):
            rows.append(dict(settlement_type="Credit Sale", requested_amount=amount(credit_sale)))
    return rows


def validate_payload(kind, payload, counter):
    """Reject uninterpretable identities/facts before granting durable acceptance."""
    from retail.api import pos_sync as api
    from retail.pos_external_refs import validate_reference, resolve_completed
    validate_reference(payload.get("external_pos_reference"), "external_pos_reference")
    if payload.get("company") and payload["company"] != counter.company:
        frappe.throw("Payload company differs from the configured counter company.")
    customer = payload.get("customer") or counter.default_customer
    if not customer or not frappe.db.exists("Customer", customer):
        frappe.throw("A valid customer is required.")
    if payload.get("currency") and payload["currency"] != frappe.get_cached_value("Company", counter.company, "default_currency"):
        frappe.throw("Offline settlement currency must equal the company currency.")
    api._cashier_employee(payload)
    resolve_completed(payload)
    for field in ("posting_date", "business_date"):
        if payload.get(field):
            frappe.utils.getdate(payload[field])
    for field in ("grand_total", "rounded_total", "vat_amount", "net_total"):
        if payload.get(field) is not None:
            amount(abs(float(payload[field])))
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        frappe.throw("At least one item is required.")
    for row in items:
        if not isinstance(row, dict) or not math.isfinite(float(row.get("qty", 0))) or not float(row.get("qty", 0)):
            frappe.throw("Item quantities must be finite and non-zero.")
        api._resolve_item(frappe._dict(row))
        for field in ("rate", "amount", "net_amount", "vat_amount"):
            if row.get(field) is not None:
                amount(abs(float(row[field])))
    for payment in cash_payments(payload):
        mode = payment_mode(payment)
        if not mode or not frappe.db.exists("Mode of Payment", mode):
            frappe.throw("A valid Mode of Payment is required for cash/card tenders.")
        account = payment.get("account") or api._payment_account(counter, {**payment, "mode_of_payment": mode})
        if account and frappe.get_cached_value("Account", account, "company") != counter.company:
            frappe.throw("Payment account belongs to another company.")
        amount(abs(float(payment.get("amount", 0))))
    original_ref = payload.get("original_external_pos_reference")
    if original_ref:
        validate_reference(original_ref, "original_external_pos_reference")
        if original_ref == payload.external_pos_reference:
            frappe.throw("Return reference must differ from its original sale.")
    original_name = payload.get("original_pos_invoice") or (
        frappe.db.get_value("POS Invoice", {"external_pos_reference": original_ref}, "name") if original_ref else None)
    if original_name:
        original = frappe.get_doc("POS Invoice", original_name)
        if original.company != counter.company or original.customer != customer or original.is_return or original.docstatus != 1:
            frappe.throw("Original invoice identity/company/customer is invalid.")
        if original_ref and original.external_pos_reference != original_ref:
            frappe.throw("Original external reference conflicts with the original invoice.")
    if kind != "Return" and any(float(r["qty"]) < 0 for r in items):
        from retail.pos_exchange import split
        split(payload)
        return customer, []
    return customer, settlements(payload, kind == "Return")


def audit(transaction, reason, severity="Info", allocation=None):
    """Deduplicate repeated worker findings, retaining later resolution events."""
    import hashlib
    event = hashlib.sha256(f"{transaction.name}:{getattr(allocation, 'name', '')}:{reason}".encode()).hexdigest()
    if frappe.db.exists("POS Settlement Exception", {"event_key": event}):
        return
    values = {field: transaction.get(field) for field in (
        "company", "branch", "business_date", "counter", "cashier", "customer", "external_pos_reference")}
    values.update(doctype="POS Settlement Exception", transaction=transaction.name,
                  allocation=allocation.name if allocation else None, event_key=event,
                  severity=severity, exception_reason=reason, details=reason, created_at=now_datetime(),
                  destination_erp_document=transaction.sales_invoice, status=transaction.status)
    if allocation:
        for field in ("source_external_reference", "source_erp_document", "destination_erp_document"):
            values[field] = allocation.get(field)
        journals = json.loads(allocation.reconciliation_reference or "[]")
        values["reconciliation_reference"] = journals[-1] if journals else None
    frappe.db.savepoint("pos_settlement_audit")
    try:
        insert(values)
    except Exception as exc:
        frappe.db.rollback(save_point="pos_settlement_audit")
        # Keep the finding durably on the acceptance if the detailed audit store
        # is unavailable. The bill and native accounting must survive.
        fallback = f"{reason}. Exception log unavailable: {type(exc).__name__}: {exc}"
        transaction.exception_reason = fallback
        frappe.db.set_value(transaction.doctype, transaction.name, "exception_reason", fallback)


def accept(kind, payload, counter, handler):
    from retail.api.pos_sync import _cashier_employee
    customer, rows = validate_payload(kind, payload, counter)
    frappe.db.get_value("Customer", customer, "name", for_update=True)
    # Unique external reference spans sale AND return operation namespaces.
    previous = frappe.db.get_value("POS Accepted Transaction", {"external_pos_reference": payload.external_pos_reference}, "name", for_update=True)
    if previous:
        frappe.throw("Reference conflict: this POS reference already belongs to an accepted transaction.")
    values = dict(doctype="POS Accepted Transaction", sync_type=kind, payload_json=canonical(dict(payload)),
                  external_pos_reference=payload.external_pos_reference, company=counter.company,
                  branch=counter.branch, counter=counter.name, business_date=payload.get("business_date") or payload.get("posting_date") or nowdate(),
                  customer=customer, cashier=_cashier_employee(payload) or payload.get("cashier") or frappe.session.user,
                  status="Accepted", created_at=now_datetime())
    transaction = insert(values)
    for doctype, field in (("POS Cashier Shift", "external_shift_reference"), ("POS Counter Session", "external_session_reference")):
        if payload.get(field) and not frappe.db.exists(doctype, {field: payload[field]}):
            audit(transaction, f"{field} opening has not synced yet; completed bill accepted.", "Warning")
    for index, row in enumerate(rows):
        allocation = {k: values[k] for k in ("company", "branch", "counter", "business_date", "customer", "cashier", "external_pos_reference")}
        allocation.update(row, doctype="POS Settlement Allocation", transaction=transaction.name,
                          applied_amount=0, unresolved_amount=row["requested_amount"], status="Accepted", created_at=now_datetime())
        insert(allocation)
    previous_flag = frappe.flags.get("pos_completed_acceptance")
    frappe.flags.pos_completed_acceptance = True
    try:
        result = post(transaction, handler)
    finally:
        frappe.flags.pos_completed_acceptance = previous_flag
    # Posting state can evolve; this acceptance receipt is stable on exact retry.
    result.update(status="Success", accepted=True, accepted_transaction=transaction.name,
                  settlement_status=transaction.status)
    try:
        frappe.enqueue("retail.pos_settlements.recover", enqueue_after_commit=True)
    except Exception as exc:
        audit(transaction, f"Recovery queue unavailable; scheduled recovery will retry: {exc}", "Technical Error")
    return result


def post(transaction, handler):
    from retail.pos_external_refs import MissingPOSDependency
    frappe.db.savepoint("pos_accepted_post")
    try:
        result = handler()
        if result.get("status") not in ("Success", "Duplicate"):
            frappe.throw("Accounting posting did not complete.")
    except Exception as exc:
        frappe.db.rollback(save_point="pos_accepted_post")
        transaction.status = "Pending Dependency" if isinstance(exc, MissingPOSDependency) else "Reconciliation Exception"
        transaction.exception_reason = str(exc)
        frappe.db.set_value(transaction.doctype, transaction.name, {
            "status": transaction.status, "exception_reason": str(exc)})
        for name in frappe.get_all("POS Settlement Allocation", filters={"transaction": transaction.name}, pluck="name"):
            frappe.db.set_value("POS Settlement Allocation", name, {
                "status": transaction.status, "exception_reason": str(exc)})
        audit(transaction, str(exc), "Warning" if isinstance(exc, MissingPOSDependency) else "Technical Error")
        return {}
    transaction.pos_invoice = result.get("pos_invoice_name") or result.get("return_invoice") or result.get("invoice_name")
    transaction.sales_invoice = frappe.db.get_value("POS Invoice", transaction.pos_invoice, "consolidated_invoice")
    transaction.status = "Posted"
    frappe.db.set_value(transaction.doctype, transaction.name, dict(status="Posted", exception_reason=None,
        pos_invoice=transaction.pos_invoice, sales_invoice=transaction.sales_invoice, posting_response=canonical(result)))
    if transaction.pos_invoice:
        doc = frappe.get_doc("POS Invoice", transaction.pos_invoice)
        reasons = frappe.get_all("External POS Rate Audit", filters={"pos_invoice": doc.name}, pluck="reason")
        for reason in reasons + (result.get("audit_warnings") or []):
            audit(transaction, str(reason), "Requires Review")
    resolve_transaction(transaction)
    refresh_day(transaction)
    result["accounting_outstanding_amount"] = flt(frappe.db.get_value("Sales Invoice", transaction.sales_invoice, "outstanding_amount"))
    return result


def resolve_transaction(transaction):
    allocations = frappe.get_all("POS Settlement Allocation", filters={"transaction": transaction.name}, pluck="name", order_by="creation asc")
    statuses = []
    for name in allocations:
        allocation = frappe.get_doc("POS Settlement Allocation", name, for_update=True)
        frappe.db.savepoint("pos_credit_allocation")
        try:
            resolve_allocation(transaction, allocation)
        except Exception as exc:
            frappe.db.rollback(save_point="pos_credit_allocation")
            allocation.reload()
            allocation.status = "Reconciliation Exception"
            allocation.exception_reason = str(exc)
            audit(transaction, str(exc), "Technical Error", allocation)
        allocation.flags.pos_settlement_write = True
        allocation.save(ignore_permissions=True)
        statuses.append(allocation.status)
    status = next((s for s in ("Reconciliation Exception", "Pending Dependency", "Pending Reconciliation") if s in statuses), "Reconciled")
    from retail.pos_external_refs import resolve_completed
    payload = frappe._dict(json.loads(transaction.payload_json))
    resolved = resolve_completed(payload)
    missing_lifecycle = False
    for doctype, external, internal, target in (
        ("POS Cashier Shift", "external_shift_reference", "cashier_shift", "pos_cashier_shift"),
        ("POS Counter Session", "external_session_reference", "counter_session", "pos_counter_session"),
    ):
        if not payload.get(external):
            continue
        name = frappe.db.get_value(doctype, {external: payload[external]}, "name")
        if not name:
            missing_lifecycle = True
        elif transaction.pos_invoice and frappe.db.get_value("POS Invoice", transaction.pos_invoice, target) != name:
            frappe.db.set_value("POS Invoice", transaction.pos_invoice, target, name)
            audit(transaction, f"Dependency resolved later: {external} = {payload[external]}.", "Info")
    if resolved.get("pos_shift_no") and transaction.pos_invoice:
        frappe.db.set_value("POS Invoice", transaction.pos_invoice, "pos_shift_no", resolved.pos_shift_no)
    if status == "Reconciled" and missing_lifecycle:
        status = "Pending Dependency"
    transaction.status = status
    frappe.db.set_value(transaction.doctype, transaction.name, {"status": status,
        "resolved_at": now_datetime() if status == "Reconciled" else None})
    from retail.pos_transaction_display import payload_transaction_type
    display_type = payload_transaction_type(transaction.sync_type, payload)
    if transaction.pos_invoice:
        frappe.db.set_value("POS Invoice", transaction.pos_invoice, "custom_pos_transaction_type",
            display_type, update_modified=False)
    for log in frappe.get_all("POS Sync Log", filters={
            "external_reference": transaction.external_pos_reference,
            "sync_type": ["in", ["POS Sale", "Sales Invoice", "Credit Sales Invoice", "POS Return", "Return"]]}, pluck="name"):
        frappe.db.set_value("POS Sync Log", log, "custom_pos_transaction_type", display_type, update_modified=False)


def resolve_allocation(transaction, row):
    if row.status == "Reconciled":
        return
    row.destination_pos_bill = transaction.pos_invoice
    row.destination_erp_document = transaction.sales_invoice
    typ = row.settlement_type
    if typ in ("Credit Note Issued", "Original Debt Reduction") and not row.requested_amount:
        row.requested_amount = abs(flt(frappe.get_doc("Sales Invoice", transaction.sales_invoice).grand_total))
    if typ == "Credit Sale" and not row.requested_amount:
        row.requested_amount = max(0, flt(frappe.get_doc("Sales Invoice", transaction.sales_invoice).outstanding_amount))
    if typ in ("Credit Sale", "Credit Note Issued", "Cash Refund", "Card Refund"):
        if typ == "Credit Note Issued":
            row.source_erp_document = transaction.sales_invoice
        row.applied_amount = row.requested_amount
        row.unresolved_amount = 0
    else:
        if typ == "Original Debt Reduction":
            source = transaction.sales_invoice
            original = frappe.get_doc("POS Invoice", transaction.pos_invoice).return_against
            destination = frappe.db.get_value("POS Invoice", original, "consolidated_invoice")
        else:
            accepted = frappe.db.get_value("POS Accepted Transaction", {
                "external_pos_reference": row.source_external_reference}, ["name", "company", "customer", "sales_invoice", "sync_type"], as_dict=True, for_update=True)
            if accepted and (accepted.company != transaction.company or accepted.customer != transaction.customer):
                frappe.throw("Credit note belongs to another company/customer.")
            if accepted and not frappe.db.exists("POS Settlement Allocation", {"transaction": accepted.name, "settlement_type": "Credit Note Issued"}):
                frappe.throw("Referenced return is not reusable customer credit.")
            source = accepted.sales_invoice if accepted else None
            if not accepted:
                source = frappe.db.get_value("POS Invoice", {
                    "external_pos_reference": row.source_external_reference, "is_return": 1, "docstatus": 1}, "consolidated_invoice")
            destination = transaction.sales_invoice
        if not source or not destination:
            row.status = "Pending Dependency"
            row.exception_reason = "Referenced credit note/original invoice has not synced yet."
            audit(transaction, row.exception_reason, "Warning", row)
            return
        row.source_erp_document = source
        row.destination_erp_document = destination
        applied, journal = reconcile(source, destination, flt(row.requested_amount - row.applied_amount, 2), transaction)
        row.applied_amount = flt(row.applied_amount + applied, 2)
        row.unresolved_amount = flt(row.requested_amount - row.applied_amount, 2)
        if journal:
            references = json.loads(row.reconciliation_reference or "[]")
            references.append(journal)
            row.reconciliation_reference = canonical(references)
            audit(transaction, f"Dependency resolved; applied {applied} through {journal}.", "Info", row)
    row.status = "Pending Reconciliation" if row.unresolved_amount else "Reconciled"
    row.exception_reason = "Current ERP credit/outstanding is less than the POS-requested settlement." if row.unresolved_amount else None
    if row.unresolved_amount:
        audit(transaction, row.exception_reason, "Requires Review", row)
    else:
        row.resolved_at = now_datetime()
        audit(transaction, "Settlement eventually reconciled.", "Info", row)


def reconcile(source_name, destination_name, requested, transaction):
    """Standard ERPNext credit-note reconciliation: paired native receivable JE rows.

    Customer lock serializes this worker; invoice locks and native JE validation
    protect against competing ordinary accounting operations as well.
    """
    frappe.db.get_value("Customer", transaction.customer, "name", for_update=True)
    documents = {name: frappe.get_doc("Sales Invoice", name, for_update=True)
                 for name in sorted({source_name, destination_name})}
    source, destination = documents[source_name], documents[destination_name]
    if source_name == destination_name or not source.is_return or destination.is_return:
        frappe.throw("Credit settlement requires a return and a distinct sale.")
    for doc in (source, destination):
        if doc.docstatus != 1 or doc.company != transaction.company or doc.customer != transaction.customer:
            frappe.throw("Settlement invoices must be submitted for the same company/customer.")
    if source.debit_to != destination.debit_to or source.currency != destination.currency:
        frappe.throw("Settlement account/currency mismatch requires accounting review.")
    account_currency = frappe.get_cached_value("Account", source.debit_to, "account_currency")
    company_currency = frappe.get_cached_value("Company", source.company, "default_currency")
    if source.currency != company_currency or account_currency != company_currency:
        frappe.throw("Foreign currency settlement requires accounting review.")
    applied = flt(min(requested, max(0, -flt(source.outstanding_amount)), max(0, flt(destination.outstanding_amount))), 2)
    if applied <= 0:
        return 0, None
    common = dict(account=source.debit_to, party_type="Customer", party=source.customer,
                  cost_center=destination.cost_center, exchange_rate=1)
    journal = frappe.get_doc(dict(doctype="Journal Entry", voucher_type="Credit Note",
        company=source.company, posting_date=nowdate(), user_remark=f"Offline POS settlement {transaction.external_pos_reference}",
        accounts=[dict(common, debit_in_account_currency=applied, reference_type="Sales Invoice", reference_name=source.name),
                  dict(common, credit_in_account_currency=applied, reference_type="Sales Invoice", reference_name=destination.name)]))
    journal.flags.ignore_permissions = True
    journal.insert(ignore_permissions=True)
    journal.submit()
    return applied, journal.name


@contextmanager
def recovery_context():
    previous = frappe.flags.get("pos_settlement_recovery")
    frappe.flags.pos_settlement_recovery = True
    try:
        yield
    finally:
        frappe.flags.pos_settlement_recovery = previous


def recover(limit=100):
    """Safe repeated scheduler/after-commit processing, including reversed arrivals."""
    from retail.api import pos_sync as api
    names = frappe.get_all("POS Accepted Transaction", filters={"status": ["!=", "Reconciled"]},
                          fields=["name", "branch", "customer"], order_by="modified asc", limit_page_length=int(limit))
    with recovery_context():
        # Two passes let a later-created original resolve earlier returns/redemptions.
        for _ in range(2):
            for pending in names:
                frappe.db.get_value("Branch", pending.branch, "name", for_update=True)
                frappe.db.get_value("Customer", pending.customer, "name", for_update=True)
                transaction = frappe.get_doc("POS Accepted Transaction", pending.name, for_update=True)
                frappe.db.savepoint("pos_recovery_transaction")
                try:
                    if transaction.status == "Reconciled":
                        continue
                    if transaction.pos_invoice:
                        resolve_transaction(transaction)
                        refresh_day(transaction)
                        continue
                    payload = frappe._dict(json.loads(transaction.payload_json))
                    endpoint = api.create_pos_return_invoice if transaction.sync_type == "Return" else api.create_pos_invoice
                    post(transaction, lambda: endpoint(payload))
                except Exception as exc:
                    frappe.db.rollback(save_point="pos_recovery_transaction")
                    transaction.reload()
                    transaction.status = "Reconciliation Exception"
                    frappe.db.set_value(transaction.doctype, transaction.name, {
                        "status": transaction.status, "exception_reason": str(exc)})
                    audit(transaction, f"Recovery attempt requires review: {exc}", "Technical Error")
    return {"processed": len(names)}


def refresh_day(transaction):
    if transaction.pos_invoice:
        invoice = frappe.get_doc("POS Invoice", transaction.pos_invoice)
        shift = invoice.get("pos_cashier_shift")
        session = invoice.get("pos_counter_session")
        closing = frappe.db.get_value("POS Counter Session", session, "pos_closing_entry") if session else None
        # Aggregate accepted bill records, retaining requested historical values.
        for doctype, name, filters in (
            ("POS Cashier Shift", shift, {"company": transaction.company, "cashier": transaction.cashier, "business_date": transaction.business_date}),
            ("POS Closing Entry", closing, {"counter": transaction.counter, "cashier": transaction.cashier, "business_date": transaction.business_date}),
        ):
            if name:
                totals = summary(filters)
                frappe.db.set_value(doctype, name, {"pos_" + field: totals[field] for field in (
                    "credit_sales", "credit_notes_issued", "credit_notes_redeemed", "credit_notes_applied", "credit_notes_unresolved")})
    from retail.pos_day_corrections import recalculate
    for name in frappe.get_all("POS Branch Day Closing", filters={"branch": transaction.branch,
            "business_date": transaction.business_date, "docstatus": ["in", [0, 1]]}, pluck="name"):
        frappe.db.savepoint("pos_late_day_refresh")
        try:
            day = frappe.get_doc("POS Branch Day Closing", name, for_update=True)
            day.flags.ignore_validate_update_after_submit = True
            recalculate(day)
        except Exception as exc:
            frappe.db.rollback(save_point="pos_late_day_refresh")
            audit(transaction, f"Closing totals require refresh: {exc}", "Requires Review")


SUMMARY_FIELDS = {
    "Credit Sale": "credit_sales",
    "Credit Note Issued": "credit_notes_issued",
    "Credit Note Redeemed": "credit_notes_redeemed",
    "Original Debt Reduction": "original_debt_reduction",
}


def summary(filters):
    result = dict.fromkeys(tuple(SUMMARY_FIELDS.values()) + (
        "credit_notes_applied", "credit_notes_unresolved", "pending_credit_allocations", "unresolved_settlement_amount"), 0.0)
    for row in frappe.get_all("POS Settlement Allocation", filters=filters,
            fields=["settlement_type", "requested_amount", "applied_amount", "unresolved_amount", "status"]):
        field = SUMMARY_FIELDS.get(row.settlement_type)
        if field:
            result[field] += flt(row.requested_amount)
        if row.settlement_type == "Credit Note Redeemed":
            result["credit_notes_applied"] += flt(row.applied_amount)
            result["credit_notes_unresolved"] += flt(row.unresolved_amount)
            if row.unresolved_amount:
                result["pending_credit_allocations"] += 1
        if row.settlement_type in ("Credit Note Redeemed", "Original Debt Reduction"):
            result["unresolved_settlement_amount"] += flt(row.unresolved_amount)
    return result


def add_customer_summaries(rows, company, customer_field):
    if not rows:
        return
    from retail.customer_balances import _CustomerReceivables
    names = list({row[customer_field] for row in rows})
    parties = frappe.get_all("Customer", filters={"name": ["in", names]}, fields=["name", "customer_name"])
    report = _CustomerReceivables({"company": company, "party_type": "Customer", "party": names,
        "report_date": nowdate(), "group_by_party": 1})
    report.list_parties = {row.name: row for row in parties}
    report.run({"account_type": "Receivable", "naming_by": ["Selling Settings", "cust_master_name"]})
    current_balances = {name: flt(report.total_row_map.get(name, {}).get("outstanding")) for name in names}
    for row in rows:
        row.update(summary({"company": company, "customer": row[customer_field]}))
        row["current_receivable"] = current_balances.get(row[customer_field], 0)
        available = flt(row.get("unused_credit_note_amount", 0))
        if "unused_credit_notes" not in row:
            reserved = frappe.get_all("POS Settlement Allocation", filters={
                "company": company, "customer": row[customer_field], "settlement_type": "Original Debt Reduction"},
                pluck="source_erp_document")
            for name in set(reserved) - {None, ""}:
                available -= max(0, -flt(frappe.db.get_value("Sales Invoice", name, "outstanding_amount")))
        row["available_credit"] = max(0, available)


def report_columns():
    return [dict(fieldname=field, label=label, fieldtype="Currency", width=155) for field, label in (
        ("credit_sales", "Credit Sales"), ("credit_notes_issued", "Credit Note Issued"),
        ("credit_notes_redeemed", "Credit Note Redeemed"), ("credit_notes_applied", "Credit Note Applied"),
        ("credit_notes_unresolved", "Credit Note Unresolved"), ("current_customer_outstanding", "Current Customer Outstanding"))]


def add_report_summaries(rows):
    """Attach bill measures once to item rows; native accounting balance is live."""
    seen = set()
    customers = {row.get("customer") for row in rows if row.get("customer")}
    company = next((row.get("company") for row in rows if row.get("company")), None)
    balances = {}
    if company and customers:
        from retail.customer_balances import _CustomerReceivables
        report = _CustomerReceivables({"company": company, "party_type": "Customer", "party": list(customers),
            "report_date": nowdate(), "group_by_party": 1})
        report.list_parties = {r.name: r for r in frappe.get_all("Customer", filters={"name": ["in", list(customers)]}, fields=["name", "customer_name"])}
        report.run({"account_type": "Receivable", "naming_by": ["Selling Settings", "cust_master_name"]})
        balances = {name: flt(report.total_row_map.get(name, {}).get("outstanding")) for name in customers}
    seen_customers = set()
    for row in rows:
        name = row.get("invoice_no")
        row.update(dict.fromkeys([c["fieldname"] for c in report_columns()], 0.0))
        if not name or name in seen:
            continue
        seen.add(name)
        transaction = frappe.db.get_value("POS Accepted Transaction", {"pos_invoice": name},
            ["name", "sales_invoice"], as_dict=True)
        if transaction:
            row.update(summary({"transaction": transaction.name}))
        customer = row.get("customer")
        if customer and customer not in seen_customers:
            # Current net native position, attached once per customer in this report.
            row.current_customer_outstanding = balances.get(customer, 0)
            seen_customers.add(customer)


def reusable_credit(accounting_name):
    accepted = frappe.db.get_value("POS Accepted Transaction", {"sales_invoice": accounting_name}, "name")
    return not accepted or bool(frappe.db.exists("POS Settlement Allocation", {
        "transaction": accepted, "settlement_type": "Credit Note Issued"}))
