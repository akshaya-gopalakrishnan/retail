"""Atomically split one completed exchange receipt into standard ERP documents.

Gross tenders offset in the same configured account; their sum is the actual
net collection/refund. There is no synthetic payment mode or internal commit.
"""
import copy
import hashlib

import frappe
from frappe.utils import cint, flt


def _money_equal(left, right):
    """Compare monetary values at cents without changing either amount."""
    return flt(left, 2) == flt(right, 2)


def split(payload):
    """Validate monetary facts before any document is posted."""
    if payload.get("issued_vouchers") or payload.get("voucher_redemption"):
        frappe.throw("Gift vouchers in exchange receipts are not supported yet.")
    if payload.get("taxes"):
        frappe.throw("Exchange receipts must send VAT per item instead of taxes[].")
    sales, returns = [], {}
    for source in payload.get("items") or []:
        row = copy.deepcopy(source)
        qty = flt(row.get("qty"))
        if not qty:
            frappe.throw("Exchange item quantity must not be zero.")
        sign = -1 if qty < 0 else 1
        rate = abs(flt(row.get("rate")))
        row["rate"] = rate
        discount = abs(flt(row.get("discount_amount")))
        gross = (rate - discount) * abs(qty)
        vat_rate = flt(row.get("vat_rate"))
        if vat_rate < 0:
            frappe.throw("Exchange VAT rate must not be negative.")
        inclusive = bool(cint(row.get("rate_includes_vat")))
        derived_net = gross / (1 + vat_rate / 100) if inclusive else gross
        row["net_amount"] = sign * abs(flt(row.get("net_amount", derived_net)))
        row["amount"] = sign * abs(flt(row.get("amount", derived_net)))
        row["vat_amount"] = sign * abs(flt(row.get("vat_amount", abs(row["net_amount"]) * vat_rate / 100)))
        if qty > 0:
            sales.append(row)
        else:
            # An explicit empty item reference opts out of a header reference.
            original = (row.get("original_external_pos_reference")
                        if "original_external_pos_reference" in row
                        else payload.get("original_external_pos_reference")) or None
            if original == payload.get("external_pos_reference"):
                frappe.throw("An exchange reference must differ from the original sale reference.")
            returns.setdefault(original, []).append(row)
    if flt(payload.get("discount_amount")) and not all(
            row.get("net_amount") is not None for row in payload.get("items") or []):
        frappe.throw("Exchange receipts with invoice discounts must supply final net_amount for every item.")
    rows = sales + [row for group in returns.values() for row in group]
    total = flt(sum(row["net_amount"] + row["vat_amount"] for row in rows), 2)
    vat = flt(sum(row["vat_amount"] for row in rows), 2)
    for field, expected in (("grand_total", total),
                            ("net_total", sum(row["net_amount"] for row in rows)),
                            ("vat_amount", vat)):
        if payload.get(field) is not None and not _money_equal(payload[field], expected):
            frappe.throw(f"Exchange {field} does not match the signed item totals.")
    if payload.get("rounded_total") is not None and not _money_equal(payload["rounded_total"], total):
        frappe.throw("Exchange rounded_total must match the signed item totals.")
    payments = copy.deepcopy(payload.get("payments") or [])
    # Accept either a positive refund magnitude or an explicitly signed refund.
    for payment in payments:
        amount = flt(payment.get("amount"))
        if total < 0:
            payment["amount"] = -abs(amount)
        elif flt(amount, 2) < 0:
            frappe.throw("Positive/zero exchange bills cannot have negative payment amounts.")
    if not _money_equal(sum(flt(p.get("amount")) for p in payments), total):
        frappe.throw("Exchange payments must equal the net bill (collection or refund).")
    mode = payload.get("exchange_mode_of_payment") or (
        payments[0].get("mode_of_payment") or payments[0].get("mode") if payments else None)
    if not mode:
        frappe.throw("Send exchange_mode_of_payment for a zero bill with no payments.")
    return sales, returns, payments, mode, total


def post_exchange(payload):
    from retail.api import pos_sync as api
    from retail.pos_external_refs import MissingPOSDependency
    sales, returns, payments, mode, total = split(payload)
    counter = api._counter(payload.get("branch"), payload.get("counter_code"))
    customer = payload.get("customer") or counter.default_customer
    reference = payload.external_pos_reference
    if api._existing_invoice(reference):
        frappe.throw("Reference conflict: this receipt already belongs to an invoice; use a new exchange reference.")
    originals = {}
    # Lock and validate originals before posting any component.
    for original_ref, rows in returns.items():
        if original_ref is None:
            continue
        name = frappe.db.get_value("POS Invoice", {"external_pos_reference": original_ref}, "name")
        if not name:
            frappe.throw("Original sale must sync before the exchange.", MissingPOSDependency)
        original = frappe.get_doc("POS Invoice", name, for_update=True)
        if (original.docstatus != 1 or original.is_return or original.customer != customer
                or original.company != counter.company or original.pos_branch != counter.branch):
            frappe.throw("Exchange return requires a submitted original sale for the same customer, company and branch.")
        for row in rows:
            matches = [item for item in original.items if item.item_code == api._resolve_item(frappe._dict(row))
                       and (not row.get("uom") or item.uom == row.get("uom"))]
            if not matches:
                frappe.throw("Returned item/UOM is not present on the original sale.")
        originals[original_ref] = original.name
    return_total = sum(abs(row["net_amount"] + row["vat_amount"]) for rows in returns.values() for row in rows)
    sale_total = sum(row["net_amount"] + row["vat_amount"] for row in sales)
    # Positive bill: actual tender + gross return offset on sale, refund offset
    # on return. Negative bill: gross sale offset on both sides + actual refund.
    offset = min(sale_total, return_total)
    sale_payments = payments if total > 0 else []
    refund_payments = payments if total < 0 else []
    offset_row = {"mode_of_payment": mode, "amount": offset}
    sale_payments = copy.deepcopy(sale_payments) + ([offset_row] if offset else [])
    refund_payments = copy.deepcopy(refund_payments) + ([{**offset_row, "amount": -offset}] if offset else [])
    documents, audits = [], []

    def post(rows, child_ref, is_return=False, original_ref=None, tender=None):
        if api._existing_invoice(child_ref):
            frappe.throw("Reference conflict: an exchange component reference is already used.")
        part = frappe._dict(copy.deepcopy(dict(payload)))
        part.update(items=rows, external_pos_reference=child_ref, payments=tender or [],
                    discount_amount=0, vat_amount=sum(r["vat_amount"] for r in rows),
                    grand_total=sum(r["net_amount"] + r["vat_amount"] for r in rows))
        for field in ("rounded_total", "rounding_adjustment", "taxes", "original_pos_invoice",
                      "original_external_pos_reference", "exchange_mode_of_payment"):
            part.pop(field, None)
        if is_return and original_ref is not None:
            part.original_pos_invoice = originals[original_ref]
            part.original_external_pos_reference = original_ref
        doc = api._base_invoice(part, counter, is_return=is_return)
        api._append_invoice_items(doc, part, counter, is_return=is_return)
        if is_return and doc.return_against:
            api._link_return_items_to_original(doc)
        api._set_profile_taxes(doc, counter)
        if not tender:
            doc.set_missing_values()
            for payment in doc.payments:
                payment.amount = payment.base_amount = 0
        api._append_invoice_payments(doc, part, counter, is_return=is_return)
        doc.insert(ignore_permissions=True)
        doc.submit()
        if not _money_equal(doc.outstanding_amount, 0):
            frappe.throw("Exchange component has an unsettled balance.")
        audits.extend(api.create_for_pos_invoice(doc, part, counter))
        documents.append(doc)
        return doc

    if sales:
        post(sales, reference, tender=sale_payments)
    # Allocate signed gross refund tenders across return invoices deterministically.
    remaining = copy.deepcopy(refund_payments)
    for index, (original_ref, rows) in enumerate(returns.items()):
        needed = sum(abs(r["net_amount"] + r["vat_amount"]) for r in rows)
        allocated = []
        for payment in remaining:
            amount = min(needed, abs(flt(payment["amount"])))
            if amount:
                allocated.append({**payment, "amount": -amount})
                payment["amount"] += amount
                needed -= amount
        if flt(needed, 2) > 0:
            frappe.throw("Exchange refund allocation does not match returned items.")
        digest = hashlib.sha256(f"{reference}:{index}:{original_ref}".encode()).hexdigest()
        child_ref = f"exchange-return-{digest}" if sales or index else reference
        post(rows, child_ref, is_return=True, original_ref=original_ref, tender=allocated)
    primary = documents[0]
    return {"status": "Success", "doctype": "POS Invoice", "docstatus": 1,
            "invoice_name": primary.name, "pos_invoice_name": primary.name,
            "is_exchange": True, "grand_total": total, "outstanding_amount": 0,
            "sale_invoice": next((d.name for d in documents if not d.is_return), None),
            "return_invoices": [d.name for d in documents if d.is_return],
            "accounting_invoices": [d.consolidated_invoice for d in documents],
            "net_payments": payments, "rate_audit_rows": audits}
