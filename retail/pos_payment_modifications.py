"""Additive same-reference payment revisions for the existing POS sale APIs.

The original sale receipt and payload remain immutable. Native accounting reposts,
credit reconciliation and append-only source movements share one transaction.
"""
import json

import frappe
from frappe.utils import cint, escape_html, flt, get_datetime, getdate, now_datetime

from retail import pos_operations as operations
from retail import pos_settlements as settlements

KIND = "Bill Settlement Correction"
META = {"modified", "modification_type", "operation_reference", "expected_payment_revision",
        "payment_revision", "modified_at", "reason"}
SETTLEMENT = {"payments", "credit_sale_amount", "credit_note_redemptions", "loyalty_redemption"}


def is_modification(payload):
    value = payload.get("modified")
    if value in (None, False, 0, "0", "false", "False", ""):
        return False
    if value in (True, 1, "1", "true", "True"):
        return True
    frappe.throw("modified must be a boolean.")


def revision(value, field):
    if isinstance(value, bool) or not str(value).isdigit():
        frappe.throw(f"{field} must be a non-negative integer.")
    return int(value)


def validate_request(payload):
    from retail.pos_external_refs import validate_reference
    for field in ("external_pos_reference", "operation_reference"):
        validate_reference(payload.get(field), field)
    if payload.get("modification_type") not in (None, "", "PaymentCorrection"):
        frappe.throw("Only PaymentCorrection is supported by modified sale requests.")
    expected = (revision(payload.expected_payment_revision, "expected_payment_revision")
                if payload.get("expected_payment_revision") is not None else None)
    next_revision = (revision(payload.payment_revision, "payment_revision")
                     if payload.get("payment_revision") is not None else None)
    if expected is not None and next_revision is not None and next_revision != expected + 1:
        frappe.throw("payment_revision must be expected_payment_revision plus one.")
    if payload.get("reason") is not None and not isinstance(payload.reason, str):
        frappe.throw("reason must be text when supplied.")
    if payload.get("modified_at"):
        get_datetime(payload.modified_at)
    if not isinstance(payload.get("payments"), list):
        frappe.throw("Send the complete final payments list, including [] for credit-only settlement.")
    for row in payload.payments:
        if not isinstance(row, dict):
            frappe.throw("Each payment must be an object.")
        if settlements.payment_mode(row) in ("Customer", "Voucher", "Cancelled"):
            frappe.throw("Customer, Voucher and Cancelled are not monetary payment rows; use their existing payload fields.")
        value = settlements.amount(row.get("amount"))
        if float(row["amount"]) != value:
            frappe.throw("Payment correction amounts must use at most two decimal places.")


def correct(payload):
    """Return the existing API's Success/Failed envelope; roll back every failed effect."""
    from retail.api import pos_sync as api
    from retail.pos_external_refs import authorize, echo
    from retail.pos_day_corrections import POSDayClosed
    frappe.db.savepoint("pos_payment_modification")
    try:
        validate_request(payload)
        counter = authorize("Sales Invoice", payload)  # Reauthorize exact retries too.
        request = {"company": counter.company, "counter": counter.name, "payload": dict(payload)}

        def action():
            # Same lock order as completed-sale recovery: branch, customer, acceptance.
            frappe.db.get_value("Branch", counter.branch, "name", for_update=True)
            name = frappe.db.get_value("POS Accepted Transaction", {
                "external_pos_reference": payload.external_pos_reference}, "name")
            if not name:
                frappe.throw("Original accepted POS sale was not found. Sync it before correcting payment.")
            identity = frappe.db.get_value("POS Accepted Transaction", name, ["customer", "counter", "branch", "company"], as_dict=True)
            if identity.counter != counter.name or identity.branch != counter.branch or identity.company != counter.company:
                frappe.throw("Original sale belongs to another counter, branch or company.", frappe.PermissionError)
            frappe.db.get_value("Customer", identity.customer, "name", for_update=True)
            transaction = frappe.get_doc("POS Accepted Transaction", name, for_update=True)
            # Generate defaults only inside the claimed operation, after locking the
            # invoice. The receipt compares the original request on every retry.
            effective = frappe._dict(payload)
            current = cint(frappe.db.get_value("POS Invoice", transaction.pos_invoice,
                "custom_payment_revision", for_update=True)) if transaction.pos_invoice else 0
            if effective.get("expected_payment_revision") is None:
                effective.expected_payment_revision = current
            if effective.get("payment_revision") is None:
                effective.payment_revision = current + 1
            effective.reason = (effective.get("reason") or "").strip() or "POS payment correction"
            return apply(transaction, effective, counter)

        return echo(payload, operations.execute(KIND, payload.operation_reference, request, action))
    except Exception as exc:
        frappe.db.rollback(save_point="pos_payment_modification")
        api._sync_log(KIND, payload.get("operation_reference"), payload,
                      status="Failed", error_message=frappe.get_traceback())
        result = {"status": "Failed", "error": str(exc)}
        if isinstance(exc, POSDayClosed):
            result["error_code"] = "DayClosed"
        return result


def unchanged_sale(original, payload):
    """Accept the full original sale or omitted sale detail; never silently ignore edits."""
    for field, value in payload.items():
        if field in META or field in SETTLEMENT:
            continue
        previous = original.get(field)
        # Optional empty legacy redemption fields are harmless but cannot introduce a discount.
        if value in (None, [], {}) and previous in (None, [], {}):
            continue
        if operations.canonical(value) != operations.canonical(previous):
            frappe.throw(f"Payment correction cannot change {field}. Keep the original sale details.")
    return frappe._dict({**original, **{field: payload.get(field) for field in SETTLEMENT}})


def native_signature(doc):
    return sorted((row.mode_of_payment, row.account, flt(row.amount, 2))
                  for row in doc.payments if flt(row.amount))


def validate_pair(transaction, payload, counter):
    from retail import pos_day_corrections as days
    from retail.pos_admin_recovery import effective_payload
    from retail.pos_settlement_corrections import collections
    if transaction.sync_type not in ("Sales Invoice", "Credit Sales Invoice") or not transaction.pos_invoice or not transaction.sales_invoice:
        frappe.throw("A posted POS sale is required for payment correction.")
    pos = frappe.get_doc("POS Invoice", transaction.pos_invoice, for_update=True)
    si = frappe.get_doc("Sales Invoice", transaction.sales_invoice, for_update=True)
    currency = frappe.get_cached_value("Company", counter.company, "default_currency")
    for doc in (pos, si):
        if (doc.docstatus != 1 or doc.is_return or doc.company != counter.company
                or doc.customer != transaction.customer or doc.currency != currency
                or flt(doc.conversion_rate) != 1 or flt(doc.change_amount) or flt(doc.write_off_amount)
                or doc.get("advances")):
            frappe.throw("Returns, change, write-offs, advances or foreign currency require accounts review.")
        if frappe.db.exists(doc.doctype, {"return_against": doc.name, "docstatus": 1}):
            frappe.throw("Invoices with submitted returns require accounts review.")
        days.check_period(doc.company, doc.posting_date)
    if (pos.consolidated_invoice != si.name or pos.pos_counter != counter.name
            or frappe.db.count("POS Invoice", {"consolidated_invoice": si.name, "docstatus": 1}) != 1):
        frappe.throw("Combined or mismatched accounting invoices require accounts review.")
    if native_signature(pos) != native_signature(si) or flt(pos.paid_amount, 2) != flt(si.paid_amount, 2):
        frappe.throw("POS and accounting payment amounts do not match.")
    if collections(si):
        frappe.throw("This invoice has later collections. Correct those through the collection workflow first.")
    days.check_bank_settlement(si.name, pos.name)
    current_revision = cint(pos.get("custom_payment_revision"))
    if current_revision != cint(si.get("custom_payment_revision")) or current_revision != int(payload.expected_payment_revision):
        frappe.throw("Bill payments changed. Refresh the payment revision before correcting it.")
    if int(payload.payment_revision) != current_revision + 1:
        frappe.throw("payment_revision must be the current server revision plus one.")
    from retail.api.pos_sync import _assert_day_not_closed
    _assert_day_not_closed(transaction.branch, transaction.business_date)
    current = effective_payload(transaction)
    wanted = unchanged_sale(current, payload)
    # Legacy voucher_redemptions represent invoice discounts, not tender. Preserve them.
    customer, allocation_rows = settlements.validate_payload(transaction.sync_type, wanted, counter)
    if customer != transaction.customer:
        frappe.throw("Payment correction cannot change the customer.")
    total = flt(pos.rounded_total if current.get("rounded_total") is not None else pos.grand_total, 2)
    if flt(wanted.get("rounded_total", wanted.get("grand_total")), 2) != total:
        frappe.throw("Payment correction must retain the posted invoice total.")
    from retail.pos_mixed_payments import loyalty_amount
    from retail import pos_offline_promotions as promotions
    tender = sum(settlements.amount(row.get("amount")) for row in settlements.cash_payments(wanted))
    value = tender + promotions.total(wanted) + loyalty_amount(wanted) + sum(r["requested_amount"] for r in allocation_rows)
    if flt(value, 2) != total:
        frappe.throw("Final payments, redemptions and customer credit must equal the invoice total.")
    credit = sum(r["requested_amount"] for r in allocation_rows if r["settlement_type"] == "Credit Sale")
    if credit > flt(si.outstanding_amount):
        from retail.api.pos_sync import _validate_credit_customer
        _validate_credit_customer(pos.customer, pos.company, credit - max(0, flt(si.outstanding_amount)))
    for row in wanted.payments:
        if not isinstance(row, dict):
            frappe.throw("Each payment must be an object.")
        settlements.amount(row.get("amount"))
    si.validate_for_repost()
    return pos, si, current, wanted, allocation_rows


def allocation_snapshot(transaction):
    return [frappe.get_doc("POS Settlement Allocation", name, for_update=True) for name in
            frappe.get_all("POS Settlement Allocation", filters={"transaction": transaction.name},
                           pluck="name", order_by="creation asc, name asc")]


def reverse_allocations(transaction, si, allocations):
    owned = set()
    for row in allocations:
        owned.update(json.loads(row.reconciliation_reference or "[]"))
    # A manual JE/reconciliation must never be silently undone by a terminal.
    external = frappe.get_all("Journal Entry Account", filters={"reference_type": "Sales Invoice",
        "reference_name": si.name, "docstatus": 1}, pluck="parent")
    if set(external) - owned:
        frappe.throw("This invoice has other accounting settlements requiring accounts review.")
    for name in sorted(owned):
        journal = frappe.get_doc("Journal Entry", name, for_update=True)
        if journal.docstatus != 1 or journal.company != transaction.company:
            frappe.throw("Credit-note reconciliation changed; accounts review is required.")
        journal.flags.ignore_permissions = True
        journal.cancel()
    for row in allocations:
        row.update(dict(requested_amount=0, applied_amount=0, unresolved_amount=0,
                   reconciliation_reference=None, status="Reconciled", exception_reason=None))
        row.flags.pos_settlement_write = True
        row.save(ignore_permissions=True)


def previous_loyalty_movements(pos, si):
    """Net bucket movements include prior positive corrections without deleting history."""
    entries = frappe.get_all("Loyalty Point Entry", filters={"invoice_type": "POS Invoice", "invoice": pos.name},
        fields=["name", "loyalty_program", "loyalty_program_tier", "loyalty_points", "redeem_against", "expiry_date"])
    return entries


def restore_loyalty(pos, si, entries):
    # Original earning roots remain untouched. Restoration has its own invoice type
    # so offline redemption's same-invoice earning exclusion still sees the credit.
    restored = frappe.get_all("Loyalty Point Entry", filters={"invoice_type": "Sales Invoice", "invoice": si.name,
        "redeem_against": ["is", "set"]}, fields=["redeem_against", "loyalty_points"])
    totals, examples = {}, {}
    for row in entries:
        if row.loyalty_points < 0:
            if not row.redeem_against:
                frappe.throw("An unallocated loyalty overdraft requires accounts review before correction.")
            totals[row.redeem_against] = totals.get(row.redeem_against, 0) + cint(row.loyalty_points)
            examples[row.redeem_against] = row
    for row in restored:
        totals[row.redeem_against] = totals.get(row.redeem_against, 0) + cint(row.loyalty_points)
    for bucket, value in totals.items():
        if value > 0:
            frappe.throw("Loyalty restoration history requires accounts review.")
        if value:
            row = examples[bucket]
            frappe.get_doc(dict(doctype="Loyalty Point Entry", company=pos.company, customer=pos.customer,
                loyalty_program=row.loyalty_program, loyalty_program_tier=row.loyalty_program_tier,
                invoice_type="Sales Invoice", invoice=si.name, redeem_against=bucket,
                loyalty_points=-value, purchase_amount=0, posting_date=pos.posting_date,
                expiry_date=row.expiry_date)).insert(ignore_permissions=True)


def restore_promotion_vouchers(pos, current, reference):
    from retail import pos_offline_promotions as promotions
    for _, row in promotions.rows(current):
        if promotions.mode(row) == "Loyalty" or not flt(row.get("amount")):
            continue
        code = row.get("reference_no")
        if not code or not frappe.db.exists("Gift Voucher Ledger", code):
            frappe.throw("Original voucher source is missing; accounts review is required.")
        # Completed offline posting deliberately accepts source mismatches. Such an
        # audited bill cannot be assumed to have debited a source that appeared later.
        if frappe.db.exists("External POS Rate Audit", {"pos_invoice": pos.name,
                "reason": ["like", "%Voucher source was not found%"]}):
            frappe.throw("Original voucher movement needs accounts review.")
        voucher = frappe.get_doc("Gift Voucher Ledger", code, for_update=True)
        if voucher.company != pos.company or voucher.status == "Cancelled":
            frappe.throw("Original voucher source requires accounts review.")
        value = flt(voucher.balance_amount + flt(row["amount"]), 2)
        if value > flt(voucher.voucher_amount):
            frappe.throw("Voucher restoration would exceed its issued value.")
        status = "Unused" if value == flt(voucher.voucher_amount) else "Partially Used"
        if voucher.expiry_date and getdate(voucher.expiry_date) < getdate(frappe.utils.today()):
            status = "Expired"
        frappe.db.set_value(voucher.doctype, voucher.name, {"balance_amount": value, "status": status})
        if voucher.get("voucher_card_batch"):
            from retail.voucher_cards import record
            voucher.balance_amount = value
            record(voucher, "Reversed", row["amount"], reference)


def apply_sources(pos, wanted, reference):
    from retail import loyalty, pos_offline_promotions as promotions
    from retail.api import gift_vouchers as vouchers
    from retail.pos_mixed_payments import set_loyalty, validate_loyalty
    for index, row in promotions.rows(wanted):
        mode = promotions.mode(row)
        if mode == "Loyalty":
            # Use strict current-source checks before the existing bucket allocator.
            program_name = row.get("reference_no") or promotions._assigned_active_program(pos.customer, pos.company, pos.posting_date)
            program = loyalty.get_program(pos.customer, program_name, pos.company)
            if not program:
                frappe.throw("A valid enrolled loyalty program is required.")
            if (flt(program.conversion_factor) <= 0 or getdate(pos.posting_date) < getdate(program.from_date)
                    or (program.to_date and getdate(pos.posting_date) > getdate(program.to_date))):
                frappe.throw("The loyalty program must be active on the sale date with a positive conversion factor.")
            points = flt(row.get("points")) if row.get("points") is not None else flt(row["amount"]) / (flt(program.conversion_factor) or 1)
            if points <= 0 or points != int(points) or flt(points * program.conversion_factor, 2) != flt(row["amount"], 2):
                frappe.throw("Loyalty points and amount must match the program conversion.")
            balance = sum(n for _, n in loyalty.available_buckets(loyalty.ledger_entries(pos.customer, program.name, pos.company, lock=True), pos.posting_date, pos.name, pos.doctype))
            if points > balance:
                frappe.throw("Insufficient loyalty points for the correction.")
            promotions._loyalty(pos, index, row)
        else:
            voucher = vouchers.read_voucher(row.get("reference_no"), pos.company, lock=True)
            expected_mode = "Voucher Card" if voucher.get("voucher_card_batch") else "Promotion Voucher"
            if mode != expected_mode or (voucher.customer and voucher.customer != pos.customer) or (voucher.warehouse and voucher.warehouse != pos.set_warehouse):
                frappe.throw("Voucher type, customer or warehouse does not match this sale.")
            vouchers.debit(voucher.name, row["amount"], pos.company, pos.currency,
                           items=pos.items, bill_total=pos.grand_total, reference=reference)
    if wanted.get("loyalty_redemption"):
        if any(promotions.mode(row) == "Loyalty" for _, row in promotions.rows(wanted)):
            frappe.throw("Send loyalty once, in payments or loyalty_redemption.")
        set_loyalty(pos, wanted)
        validate_loyalty(pos, wanted)
        loyalty.redeem(pos)


def payment_rows(pos, wanted, counter):
    from retail.api import pos_sync as api
    from retail import pos_offline_promotions as promotions
    rows = []
    for row in settlements.cash_payments(wanted):
        mode = settlements.payment_mode(row)
        mop = frappe.get_doc("Mode of Payment", mode)
        if not mop.enabled or mode not in {r.mode_of_payment for r in frappe.get_doc("POS Profile", pos.pos_profile).payments}:
            frappe.throw("The payment method is disabled or not configured in the POS Profile.")
        account = api._payment_account(counter, {"mode_of_payment": mode})
        if not account:
            account = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": pos.company}, "default_account")
        if row.get("account") and row["account"] != account:
            frappe.throw("Payment account must match the configured company/counter account.")
        rows.append({**row, "mode_of_payment": mode, "account": account})
    rows.extend(promotions.native_payments(wanted, counter))
    for row in rows:
        account = frappe.get_doc("Account", row.get("account"))
        if account.company != pos.company or account.is_group or account.disabled or account.account_currency != pos.currency:
            frappe.throw("Payment account must be enabled and belong to this company and currency.")
    return rows


def persist_payments(doc, rows, wanted, revision_number, reference):
    # The operation receipt retains before/after rows. GL history is reversed by
    # native repost, never deleted; commercial fields and stock are untouched.
    frappe.db.delete("Sales Invoice Payment", {"parenttype": doc.doctype, "parent": doc.name})
    doc.set("payments", [])
    for row in rows:
        child = doc.append("payments", {key: row.get(key) for key in ("mode_of_payment", "amount", "account", "reference_no")})
        child.base_amount = flt(child.amount)
        child.type = frappe.get_cached_value("Mode of Payment", child.mode_of_payment, "type")
        child.docstatus = 1
        child.db_insert()
    loyalty = wanted.get("loyalty_redemption") or {}
    paid = sum(flt(row["amount"]) for row in rows) + flt(loyalty.get("amount"))
    from retail.pos_mixed_payments import voucher_rows
    from retail.pos_offline_promotions import rows as promotion_rows, mode
    voucher_amount = sum(flt(row.get("amount")) for row in voucher_rows(wanted)) + sum(
        flt(row.get("amount")) for _, row in promotion_rows(wanted) if mode(row) in ("Promotion Voucher", "Voucher Card"))
    values = dict(paid_amount=paid, base_paid_amount=paid,
        loyalty_amount=flt(loyalty.get("amount")), loyalty_points=cint(loyalty.get("points")),
        custom_gift_voucher_amount=voucher_amount,
        redeem_loyalty_points=1 if loyalty else 0, custom_payment_revision=revision_number,
        custom_pos_modified=1, custom_pos_payment_modified_at=now_datetime(),
        custom_pos_payment_modification_reference=reference)
    if loyalty:
        from retail.pos_mixed_payments import set_loyalty
        set_loyalty(doc, wanted)
        values.update({field: doc.get(field) for field in ("loyalty_program", "loyalty_redemption_account", "loyalty_redemption_cost_center")})
    frappe.db.set_value(doc.doctype, doc.name, values)
    frappe.clear_document_cache(doc.doctype, doc.name)


def apply(transaction, payload, counter):
    from retail import pos_day_corrections as days
    from retail.pos_settlement_corrections import repost
    pos, si, current, wanted, allocation_rows = validate_pair(transaction, payload, counter)
    allocations = allocation_snapshot(transaction)
    before = {"payments": days.payment_rows(pos), "paid_amount": pos.paid_amount,
        "outstanding_amount": si.outstanding_amount, "payload": current,
        "allocations": [row.as_dict() for row in allocations]}
    with days.correction_context():
        pos.flags.payment_correction_payload = wanted
        reverse_allocations(transaction, si, allocations)
        restore_loyalty(pos, si, previous_loyalty_movements(pos, si))
        restore_promotion_vouchers(pos, current, payload.operation_reference)
        apply_sources(pos, wanted, payload.operation_reference)
        rows = payment_rows(pos, wanted, counter)
        for doc in (pos, si):
            persist_payments(doc, rows, wanted, payload.payment_revision, payload.operation_reference)
        si.reload()
        repost_name = repost(si)
        for values in allocation_rows:
            common = {field: transaction.get(field) for field in ("company", "branch", "counter", "business_date", "customer", "cashier", "external_pos_reference")}
            allocation = settlements.insert(dict(common, **values, doctype="POS Settlement Allocation", transaction=transaction.name,
                applied_amount=0, unresolved_amount=values["requested_amount"], status="Accepted", created_at=now_datetime()))
            settlements.resolve_allocation(transaction, allocation)
            if allocation.status != "Reconciled":
                frappe.throw("Credit-note settlement could not be fully applied; no correction was saved.")
            allocation.flags.pos_settlement_write = True
            allocation.save(ignore_permissions=True)
        encoded = operations.canonical(wanted)
        frappe.db.set_value(transaction.doctype, transaction.name, {"correction_payload_json": encoded,
            "correction_reason": payload.reason, "status": "Reconciled", "exception_reason": None})
        transaction.reload()
        si.reload()
        frappe.db.set_value("POS Invoice", pos.name, "outstanding_amount", si.outstanding_amount)
        pos.reload()
        if pos.loyalty_program:
            pos.make_loyalty_point_entry()
        credit = sum(r["requested_amount"] for r in allocation_rows if r["settlement_type"] == "Credit Sale")
        if flt(si.outstanding_amount, 2) != flt(credit, 2):
            frappe.throw("Accounting balance does not match the final customer credit; no correction was saved.")
        from retail.pos_transaction_display import transaction_type
        frappe.db.set_value("POS Invoice", pos.name, "custom_pos_transaction_type", transaction_type(pos))
        for doc in (pos, si, transaction):
            doc.add_comment("Info", text=escape_html(f"Modified — Payment Corrected. Revision {payload.payment_revision}. "
                f"By {frappe.session.user}. Reference: {payload.operation_reference}. Reason: {payload.reason}"))
        # Refresh every affected aggregate synchronously; never return Success with stale closing totals.
        from retail.api.pos_sync import _refresh_cashier_shift_cash_totals
        if pos.pos_cashier_shift:
            totals = _refresh_cashier_shift_cash_totals(pos.pos_cashier_shift)
            shift = frappe.get_doc("POS Cashier Shift", pos.pos_cashier_shift)
            if shift.status == "Closed":
                frappe.db.set_value(shift.doctype, shift.name, "variance", flt(shift.closing_amount) - totals.expected_cash)
        from retail.pos_realtime import refresh_closed_reconciliation
        refresh_closed_reconciliation(pos)
        for name in frappe.get_all(days.DAY, filters={"branch": transaction.branch, "business_date": transaction.business_date, "docstatus": 0}, pluck="name"):
            days.recalculate(frappe.get_doc(days.DAY, name, for_update=True))
        settlements.refresh_day(transaction)
    return dict(status="Success", accepted=True, settlement_status=transaction.status,
        doctype="POS Invoice", docstatus=pos.docstatus, invoice_name=pos.name, pos_invoice_name=pos.name,
        pos_invoice=pos.name, accounting_invoice=si.name, accepted_transaction=transaction.name,
        external_pos_reference=payload.external_pos_reference, operation_reference=payload.operation_reference,
        modified=True, modification_type="PaymentCorrection", payment_revision=payload.payment_revision,
        modified_at=str(pos.custom_pos_payment_modified_at), reason=payload.reason,
        grand_total=pos.grand_total, paid_amount=pos.paid_amount, outstanding_amount=si.outstanding_amount,
        accounting_outstanding_amount=si.outstanding_amount, previous_payments=before["payments"],
        payments=days.payment_rows(pos), before_settlement=before, accounting_repost=repost_name)


def status_details(name):
    doc = frappe.get_doc("POS Invoice", name)
    from retail.pos_day_corrections import payment_rows
    return dict(modified=bool(doc.get("custom_pos_modified")), payment_revision=cint(doc.get("custom_payment_revision")),
        modification_type="PaymentCorrection" if doc.get("custom_pos_modified") else None,
        operation_reference=doc.get("custom_pos_payment_modification_reference"),
        modified_at=doc.get("custom_pos_payment_modified_at"), payments=payment_rows(doc))


def install():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    fields = [dict(fieldname="custom_pos_modified", label="Modified", fieldtype="Check", default="0",
                   read_only=1, no_copy=1, in_list_view=1, in_standard_filter=1, insert_after="custom_payment_revision"),
              dict(fieldname="custom_pos_payment_modified_at", label="Payment Corrected At", fieldtype="Datetime",
                   read_only=1, no_copy=1, insert_after="custom_pos_modified"),
              dict(fieldname="custom_pos_payment_modification_reference", label="Payment Correction Reference", fieldtype="Data",
                   read_only=1, no_copy=1, insert_after="custom_pos_payment_modified_at")]
    create_custom_fields({doctype: fields for doctype in ("POS Invoice", "Sales Invoice")}, update=True, ignore_validate=True)
