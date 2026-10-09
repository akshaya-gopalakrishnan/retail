"""Sales Invoice loyalty rules owned by Retail; ERPNext remains unchanged."""
from collections import defaultdict
from math import floor

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today


def ledger_entries(customer, program, company, lock=False):
    return frappe.db.sql(
        """select name, loyalty_points, redeem_against, expiry_date, posting_date,
            invoice_type, invoice, loyalty_program_tier
        from `tabLoyalty Point Entry`
        where customer=%s and loyalty_program=%s and company=%s
        order by expiry_date, posting_date, name""" + (" for update" if lock else ""),
        (customer, program, company), as_dict=True,
    )


def available_buckets(entries, posting_date=None, exclude_invoice=None):
    posting_date = getdate(posting_date or today())
    expiry_cutoff = max(posting_date, getdate(today()))
    movements = defaultdict(int)
    for entry in entries:
        if entry.redeem_against:
            movements[entry.redeem_against] += cint(entry.loyalty_points)
    result = []
    for entry in entries:
        if entry.redeem_against or cint(entry.loyalty_points) < 0:
            continue
        if exclude_invoice and entry.invoice_type == "Sales Invoice" and entry.invoice == exclude_invoice:
            continue
        if not entry.expiry_date or getdate(entry.expiry_date) < expiry_cutoff:
            continue
        if not entry.posting_date or getdate(entry.posting_date) > posting_date:
            continue
        balance = cint(entry.loyalty_points) + movements[entry.name]
        if balance > 0:
            result.append((entry, balance))
    return result


def get_program(customer, program, company):
    enrolled = frappe.db.get_value("Customer", customer, "loyalty_program")
    program = program or enrolled
    if not program:
        return None
    if enrolled != program:
        frappe.throw(_("The customer is not enrolled in the selected Loyalty Program."))
    doc = frappe.get_doc("Loyalty Program", program)
    if doc.company != company:
        frappe.throw(_("The Loyalty Program is not valid for this company."))
    return doc


@frappe.whitelist()
def get_available_points(customer, company, loyalty_program=None, posting_date=None):
    if not frappe.has_permission("Sales Invoice", "create") and not frappe.has_permission("Sales Invoice", "read"):
        frappe.throw(_("Not permitted to access Sales Invoice loyalty balances."), frappe.PermissionError)
    frappe.get_doc("Customer", customer).check_permission("read")
    frappe.get_doc("Company", company).check_permission("read")
    program = get_program(customer, loyalty_program, company)
    if not program:
        return {"available_points": 0, "conversion_factor": 0, "loyalty_program": None}
    # Return only the aggregate, never unrestricted ledger documents.
    buckets = available_buckets(ledger_entries(customer, program.name, company), posting_date)
    return {
        "available_points": sum(balance for _, balance in buckets),
        "conversion_factor": flt(program.conversion_factor),
        "loyalty_program": program.name,
    }


def lock_customer(doc):
    # A stable lock also serializes two redemptions when no ledger rows exist yet.
    frappe.db.sql("select name from `tabCustomer` where name=%s for update", doc.customer)


def return_entitlement(original_points, original_total, returned_total, already_restored=0):
    if flt(original_total) <= 0:
        return 0
    ratio = min(1, abs(flt(returned_total)) / flt(original_total))
    return max(0, floor(cint(original_points) * ratio + 1e-9) - cint(already_restored))


def prepare_return(doc):
    if not doc.return_against:
        doc.redeem_loyalty_points = 0
        doc.loyalty_points = doc.loyalty_amount = 0
        return
    original = frappe.get_doc("Sales Invoice", doc.return_against)
    if original.docstatus != 1 or original.customer != doc.customer or original.company != doc.company:
        frappe.throw(_("Loyalty returns must reference a submitted invoice for the same customer and company."))
    doc.loyalty_program = original.loyalty_program
    previous = frappe.db.sql(
        """select coalesce(sum(abs(grand_total)), 0) as total,
            coalesce(sum(abs(loyalty_points)), 0) as points,
            coalesce(sum(abs(loyalty_amount)), 0) as amount
        from `tabSales Invoice` where return_against=%s and is_return=1
            and docstatus=1 and name!=%s""" + (" for update" if doc.docstatus == 1 else ""),
        (original.name, doc.name or ""), as_dict=True,
    )[0]
    points = return_entitlement(original.loyalty_points, original.grand_total,
                               previous.total + abs(flt(doc.grand_total)), previous.points)
    amount = flt(points * flt(original.loyalty_amount) / original.loyalty_points,
                 doc.precision("loyalty_amount")) if original.loyalty_points else 0
    # The last return restores the exact remaining monetary amount, including rounding.
    if points and points + cint(previous.points) == cint(original.loyalty_points):
        amount = flt(abs(original.loyalty_amount) - previous.amount, doc.precision("loyalty_amount"))
    doc.redeem_loyalty_points = int(bool(points))
    doc.loyalty_points = -points
    doc.loyalty_amount = -amount
    doc.loyalty_redemption_account = original.loyalty_redemption_account
    doc.loyalty_redemption_cost_center = original.loyalty_redemption_cost_center


def validate_redemption(doc, method=None):
    if doc.is_consolidated:
        return
    old_amount = flt(doc.loyalty_amount)
    if doc.is_return:
        prepare_return(doc)
        entries = ledger_entries(doc.customer, doc.loyalty_program, doc.company,
                                 lock=doc.docstatus == 1) if doc.loyalty_program else []
        doc.custom_available_loyalty_points = sum(n for _, n in available_buckets(entries, doc.posting_date))
    else:
        program = get_program(doc.customer, doc.loyalty_program, doc.company) if doc.customer else None
        doc.loyalty_program = program.name if program else None
        entries = ledger_entries(doc.customer, program.name, doc.company, lock=doc.docstatus == 1) if program else []
        balance = sum(n for _, n in available_buckets(entries, doc.posting_date, doc.name))
        doc.custom_available_loyalty_points = balance
        if not doc.redeem_loyalty_points:
            doc.loyalty_points = doc.loyalty_amount = 0
        else:
            points = flt(doc.loyalty_points)
            if points < 0 or points != cint(points):
                frappe.throw(_("Loyalty points to redeem must be a non-negative whole number."))
            if not program or flt(program.conversion_factor) <= 0:
                frappe.throw(_("Select a valid Loyalty Program with a positive conversion factor."))
            if getdate(doc.posting_date) < getdate(program.from_date) or (
                program.to_date and getdate(doc.posting_date) > getdate(program.to_date)
            ):
                frappe.throw(_("The Loyalty Program is not active on the invoice date."))
            if points > balance:
                frappe.throw(_("Only {0} loyalty points are available.").format(balance))
            doc.loyalty_amount = flt(points * program.conversion_factor, doc.precision("loyalty_amount"))
            doc.loyalty_redemption_account = program.expense_account
            doc.loyalty_redemption_cost_center = program.cost_center
            total = doc.grand_total if doc.is_rounded_total_disabled() else doc.rounded_total
            maximum = (flt(total) - flt(doc.total_advance) - flt(doc.write_off_amount)) * flt(doc.conversion_rate)
            if doc.loyalty_amount > max(0, flt(maximum, doc.precision("loyalty_amount"))):
                frappe.throw(_("The loyalty redemption amount exceeds the remaining invoice amount."))
    if old_amount != flt(doc.loyalty_amount):
        doc.calculate_taxes_and_totals()
    if doc.is_return and doc.is_pos and doc.loyalty_amount:
        total = doc.grand_total if doc.is_rounded_total_disabled() else doc.rounded_total
        max_refund = max(0, abs(flt(total)) - abs(flt(doc.loyalty_amount) / flt(doc.conversion_rate)))
        refund = -sum(flt(payment.amount) for payment in doc.get("payments", []))
        if flt(refund, doc.precision("paid_amount")) > flt(max_refund, doc.precision("paid_amount")):
            frappe.throw(_("The cash refund cannot exceed {0} after restoring loyalty points.").format(max_refund))


def insert_movement(doc, bucket, points):
    frappe.get_doc({
        "doctype": "Loyalty Point Entry", "customer": doc.customer,
        "loyalty_program": doc.loyalty_program, "company": doc.company,
        "invoice_type": "Sales Invoice", "invoice": doc.name,
        "redeem_against": bucket.name, "loyalty_program_tier": bucket.loyalty_program_tier,
        "loyalty_points": points, "purchase_amount": 0,
        "posting_date": doc.posting_date, "expiry_date": bucket.expiry_date,
    }).insert(ignore_permissions=True)


def redeem(doc):
    entries = ledger_entries(doc.customer, doc.loyalty_program, doc.company, lock=True)
    buckets = available_buckets(entries, doc.posting_date, doc.name)
    remaining = cint(doc.loyalty_points)
    if remaining > sum(n for _, n in buckets):
        frappe.throw(_("The loyalty balance changed. Refresh the invoice and try again."))
    for bucket, balance in buckets:
        points = min(remaining, balance)
        if points:
            insert_movement(doc, bucket, -points)
        remaining -= points
        if not remaining:
            break


def restore_return(doc):
    entries = ledger_entries(doc.customer, doc.loyalty_program, doc.company, lock=True)
    roots = {e.name: e for e in entries if not e.redeem_against}
    debits = defaultdict(int)
    restored = defaultdict(int)
    return_names = set(frappe.get_all("Sales Invoice", filters={"return_against": doc.return_against,
                            "docstatus": 1}, pluck="name"))
    for e in entries:
        if e.invoice_type != "Sales Invoice" or not e.redeem_against:
            continue
        if e.invoice == doc.return_against and e.loyalty_points < 0:
            debits[e.redeem_against] -= e.loyalty_points
        elif e.invoice in return_names and e.loyalty_points > 0:
            restored[e.redeem_against] += e.loyalty_points
    remaining = abs(cint(doc.loyalty_points))
    for name, spent in debits.items():
        points = min(remaining, max(0, spent - restored[name]))
        if points:
            if name not in roots:
                frappe.throw(_("The original loyalty ledger entry is missing."))
            insert_movement(doc, roots[name], points)
            remaining -= points
    if remaining:
        frappe.throw(_("The original invoice does not have enough redeemed ledger points to reverse."))


def remove_invoice_entries(doc):
    entries = ledger_entries(doc.customer, doc.loyalty_program, doc.company, lock=True)
    removed = {e.name for e in entries if e.invoice_type == "Sales Invoice" and e.invoice == doc.name}
    movements = defaultdict(int)
    for e in entries:
        if e.name not in removed and e.redeem_against:
            movements[e.redeem_against] += cint(e.loyalty_points)
    for e in entries:
        if e.redeem_against:
            continue
        if e.name in removed and any(x.redeem_against == e.name and x.name not in removed for x in entries):
            frappe.throw(_("Cancel linked loyalty redemptions and returns before cancelling this invoice."))
        if e.name not in removed and cint(e.loyalty_points) + movements[e.name] < 0:
            frappe.throw(_("The restored loyalty points have already been spent. Cancel those redemptions first."))
    frappe.db.delete("Loyalty Point Entry", {"invoice_type": "Sales Invoice", "invoice": doc.name})


@frappe.whitelist()
def get_return_preview(return_against, grand_total, invoice=None):
    original = frappe.get_doc("Sales Invoice", return_against)
    original.check_permission("read")
    if not frappe.has_permission("Sales Invoice", "create"):
        frappe.throw(_("Not permitted to create Sales Invoices."), frappe.PermissionError)
    if invoice:
        saved = frappe.get_doc("Sales Invoice", invoice)
        saved.check_permission("write")
        if saved.docstatus != 0 or saved.return_against != return_against:
            frappe.throw(_("Select a draft return for the original invoice."))
    preview = frappe.new_doc("Sales Invoice")
    preview.update({"name": invoice, "customer": original.customer, "company": original.company,
                    "return_against": original.name, "is_return": 1, "grand_total": grand_total})
    prepare_return(preview)
    return {key: preview.get(key) for key in ("loyalty_program", "loyalty_points", "loyalty_amount",
                "redeem_loyalty_points", "loyalty_redemption_account", "loyalty_redemption_cost_center")}
