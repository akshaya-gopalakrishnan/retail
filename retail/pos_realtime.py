"""Post each POS receipt atomically; closing only reconciles posted receipts."""
import frappe
from frappe import _
from frappe.utils import flt, get_datetime

from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import POSClosingEntry


def post_invoice(doc, method=None):
    """One standard merge per receipt, with no background job or internal commit."""
    if doc.docstatus != 1:
        frappe.throw(_("Only submitted POS invoices can be posted."))
    # Current locking read makes repeated/concurrent posting idempotent.
    linked = frappe.db.get_value("POS Invoice", doc.name, "consolidated_invoice", for_update=True)
    if linked:
        if frappe.db.get_value("Sales Invoice", linked, "docstatus") != 1:
            frappe.throw(_("Linked accounting invoice {0} is not submitted.").format(linked))
        doc.consolidated_invoice = linked
        return linked
    for ledger in ("GL Entry", "Stock Ledger Entry"):
        if frappe.db.exists(ledger, {"voucher_type": "POS Invoice", "voucher_no": doc.name,
                "is_cancelled": 0}):
            frappe.throw(_("POS receipt {0} already has direct ledger entries; reconcile these before posting.").format(doc.name))
    if doc.is_return and doc.return_against:
        original = frappe.get_doc("POS Invoice", doc.return_against, for_update=True)
        post_invoice(original)
    merge = frappe.new_doc("POS Invoice Merge Log")
    merge.company = doc.company
    merge.customer = doc.customer
    merge.merge_invoices_based_on = "Customer"
    merge.posting_date = doc.posting_date
    merge.posting_time = doc.posting_time
    merge.append("pos_invoices", {
        "pos_invoice": doc.name, "customer": doc.customer,
        "posting_date": doc.posting_date, "grand_total": doc.grand_total,
    })
    new_invoice = merge.get_new_sales_invoice

    def make_accounting_invoice():
        invoice = new_invoice()
        # Permission bypass is limited to accounting for this authorized receipt.
        invoice.flags.ignore_permissions = True
        invoice.flags.allow_external_pos_sales_invoice = True
        invoice.due_date = doc.due_date
        invoice.flags.completed_pos_accounting = bool(doc.get("custom_pos_completed_payload"))
        return invoice

    merge.get_new_sales_invoice = make_accounting_invoice
    if doc.is_return and not doc.return_against:
        # Core looks up a POS Invoice with a None filter here, which can select
        # an unrelated receipt. A singleton standalone return has no original.
        merge.distinguish_return_pos_invoices = lambda receipts, sales_invoice_doc=None: {None: receipts}
    map_invoice = merge.merge_pos_invoice_into

    def map_receipt(invoice, receipts):
        invoice = map_invoice(invoice, receipts)
        # Core replaces this flag with the current POS Profile setting. For
        # a single-receipt posting, preserve the receipt's rounding policy so
        # accounting uses the same payable total as the completed sale.
        from retail.pos_completed_sale import payload_for
        completed_payload = payload_for(doc)
        if completed_payload:
            invoice.disable_rounded_total = int(completed_payload.get("rounded_total") is None)
        # POS totals may allocate a fraction of a cent to the final line. Core
        # compares unrounded return rates, although accounting rounds amounts.
        # Normalize only when the returned monetary amount is exactly unchanged.
        if invoice.is_return:
            # Every return owns its credit. Debt reduction is a separate allocation,
            # so the same credit cannot also reduce the original automatically.
            if completed_payload:
                invoice.update_outstanding_for_self = 1
            for item in invoice.items:
                if not item.sales_invoice_item:
                    continue
                original_rate = frappe.db.get_value("Sales Invoice Item", item.sales_invoice_item, "rate")
                if original_rate is None or flt(item.rate) <= flt(original_rate):
                    continue
                precision = item.precision("amount")
                if flt(item.rate * item.qty, precision) == flt(original_rate * item.qty, precision):
                    item.rate = original_rate
        return invoice

    merge.merge_pos_invoice_into = map_receipt
    merge.insert(ignore_permissions=True)
    merge.submit()
    linked = frappe.db.get_value("POS Invoice", doc.name, "consolidated_invoice")
    if not linked:
        frappe.throw(_("POS accounting could not be posted."))
    accounting = frappe.get_doc("Sales Invoice", linked)
    for field in ("grand_total", "net_total", "total_taxes_and_charges", "paid_amount", "outstanding_amount"):
        precision = accounting.precision(field)
        if flt(doc.get(field), precision) != flt(accounting.get(field), precision):
            frappe.throw(_("Accounting {0} does not match POS receipt {1}; posting was not completed.").format(field, doc.name))
    # Do not reload: the sync response/audit still needs the original flags.
    doc.consolidated_invoice = linked
    doc.status = "Consolidated"
    frappe.db.savepoint("pos_posted_closing_refresh")
    try:
        refresh_closed_reconciliation(doc)
    except Exception as exc:
        frappe.db.rollback(save_point="pos_posted_closing_refresh")
        from retail.pos_completed_sale import note_mismatch
        note_mismatch(doc, f"Closing totals need recovery: {exc}. Completed accounting retained.")
    return linked


def refresh_closed_reconciliation(invoice):
    """Refresh derived closing totals after a receipt posts; retain counted tenders."""
    session = invoice.get("pos_counter_session")
    if not session:
        return
    name = frappe.db.get_value("POS Counter Session", session, "pos_closing_entry")
    if not name:
        return
    closing = frappe.get_doc("POS Closing Entry", name, for_update=True)
    if closing.docstatus != 1:
        return
    populate_closing(closing, closing_invoices(closing.period_start_date, closing.period_end_date,
        closing.pos_profile, closing.user, closing.name, session))
    from retail.pos_list_settings import set_closing_summary
    set_closing_summary(closing)
    # Persist only reconciliation data. Do not resubmit or merge posted receipts.
    for row in closing.get_all_children():
        row.docstatus = closing.docstatus
    closing.db_update()
    closing.update_children()
    shift_name = invoice.get("pos_cashier_shift")
    if shift_name:
        from retail.api.pos_sync import _refresh_cashier_shift_cash_totals
        totals = _refresh_cashier_shift_cash_totals(shift_name)
        shift = frappe.get_doc("POS Cashier Shift", shift_name)
        if shift.status == "Closed":
            frappe.db.set_value("POS Cashier Shift", shift.name,
                "variance", flt(shift.closing_amount) - totals.expected_cash)
        from retail.pos_day_corrections import recalculate
        for day_name in frappe.get_all("POS Branch Day Closing", filters={
                "branch": shift.branch, "business_date": get_datetime(shift.opening_time).date(),
                "docstatus": ["in", [0, 1]]}, pluck="name"):
            day = frappe.get_doc("POS Branch Day Closing", day_name, for_update=True)
            day.flags.ignore_validate_update_after_submit = True
            recalculate(day)


def cancel_invoice_posting(doc):
    """Reverse only the single-receipt posting; retain core dependency checks."""
    if not doc.consolidated_invoice:
        return
    names = frappe.db.sql("""
        select m.name from `tabPOS Invoice Merge Log` m
        join `tabPOS Invoice Reference` r on r.parent=m.name
            and r.parenttype='POS Invoice Merge Log'
        where r.pos_invoice=%s and m.docstatus=1
            and coalesce(m.pos_closing_entry, '')=''
    """, doc.name, pluck=True)
    if len(names) != 1:
        return  # Legacy shift postings still use the original cancellation flow.
    merge = frappe.get_doc("POS Invoice Merge Log", names[0], for_update=True)
    if len(merge.pos_invoices) != 1:
        return
    merge.flags.ignore_permissions = True
    merge.cancel()
    doc.consolidated_invoice = None


@frappe.whitelist()
def get_pos_invoices(start, end, pos_profile, user):
    if not frappe.has_permission("POS Closing Entry", "read"):
        frappe.throw(_("Not permitted to read POS closing receipts."), frappe.PermissionError)
    return closing_invoices(start, end, pos_profile, user)


def closing_invoices(start, end, pos_profile, user, closing_name=None, counter_session=None):
    names = frappe.db.sql("""
        select p.name from `tabPOS Invoice` p
        where p.owner=%s and p.pos_profile=%s and p.docstatus=1
            and ((%s is not null and p.pos_counter_session=%s)
                or (%s is null and timestamp(p.posting_date,p.posting_time) between %s and %s))
            and not exists (
                select 1 from `tabPOS Invoice Reference` r
                join `tabPOS Closing Entry` c on c.name=r.parent
                where r.parenttype='POS Closing Entry' and r.pos_invoice=p.name
                    and c.docstatus=1 and c.name != %s
            )
        order by p.posting_date,p.posting_time,p.creation
    """, (user, pos_profile, counter_session, counter_session, counter_session,
        get_datetime(start), get_datetime(end), closing_name or ""), pluck=True)
    return [frappe.get_doc("POS Invoice", name).as_dict() for name in names]



def closing_tax_rows(invoice, tax):
    """Use reported POS rates for fixed-amount taxes without recalculating VAT."""
    from retail.pos_completed_sale import payload_for
    payload = payload_for(invoice)
    weights = {}
    if payload and tax.charge_type == "Actual" and not flt(tax.rate):
        reported = [row for row in payload.get("taxes", []) or []
            if row.get("account_head") == tax.account_head]
        for row in reported:
            rate = row.get("rate", row.get("tax_rate"))
            if rate is not None:
                weights[flt(rate)] = weights.get(flt(rate), 0) + abs(flt(row.get("tax_amount")))
        # Item VAT belongs to the single aggregate VAT row; never assign it
        # to an unrelated tax account when an invoice has multiple tax rows.
        if not weights and len(invoice.taxes) == 1:
            for item in payload.get("items", []) or []:
                if item.get("vat_rate") is not None and flt(item.get("vat_amount")):
                    rate = flt(item["vat_rate"])
                    weights[rate] = weights.get(rate, 0) + abs(flt(item["vat_amount"]))
    total_weight = sum(weights.values())
    if not total_weight:
        return [(flt(tax.rate), flt(tax.tax_amount))]
    rows, remaining = [], flt(tax.tax_amount)
    for index, (rate, weight) in enumerate(weights.items()):
        amount = remaining if index == len(weights) - 1 else flt(
            flt(tax.tax_amount) * weight / total_weight, 2)
        rows.append((rate, amount))
        remaining -= amount
    return rows


def populate_closing(closing, invoices):
    actuals = {p.mode_of_payment: p.closing_amount for p in closing.payment_reconciliation}
    opening = frappe.get_doc("POS Opening Entry", closing.pos_opening_entry)
    payments = {p.mode_of_payment: frappe._dict(mode_of_payment=p.mode_of_payment,
        opening_amount=flt(p.opening_amount), expected_amount=flt(p.opening_amount))
        for p in opening.balance_details}
    taxes = {}
    closing.set("pos_transactions", [])
    closing.grand_total = closing.net_total = closing.total_quantity = 0
    for invoice in invoices:
        closing.append("pos_transactions", {"pos_invoice": invoice.name,
            "posting_date": invoice.posting_date, "grand_total": invoice.grand_total,
            "customer": invoice.customer})
        closing.grand_total += flt(invoice.grand_total)
        closing.net_total += flt(invoice.net_total)
        closing.total_quantity += flt(invoice.total_qty)
        change = flt(invoice.change_amount)
        for p in invoice.payments:
            payment = payments.setdefault(p.mode_of_payment, frappe._dict(
                mode_of_payment=p.mode_of_payment, opening_amount=0, expected_amount=0))
            amount = flt(p.amount)
            if p.account == invoice.account_for_change_amount and change:
                amount -= change
                change = 0
            payment.expected_amount += amount
        for t in invoice.taxes:
            for rate, amount in closing_tax_rows(invoice, t):
                key = (t.account_head, rate)
                tax = taxes.setdefault(key, frappe._dict(account_head=t.account_head, rate=rate, amount=0))
                tax.amount += amount
    for payment in payments.values():
        payment.closing_amount = flt(actuals.get(payment.mode_of_payment, payment.expected_amount))
        payment.difference = payment.closing_amount - payment.expected_amount
    closing.set("payment_reconciliation", list(payments.values()))
    closing.set("taxes", list(taxes.values()))


def make_closing_entry_from_opening(opening):
    closing = frappe.new_doc("POS Closing Entry")
    closing.update({"pos_opening_entry": opening.name, "period_start_date": opening.period_start_date,
        "period_end_date": frappe.utils.now_datetime(), "pos_profile": opening.pos_profile,
        "user": opening.user, "company": opening.company})
    populate_closing(closing, closing_invoices(closing.period_start_date, closing.period_end_date,
        closing.pos_profile, closing.user))
    return closing


class RetailPOSClosingEntry(POSClosingEntry):
    def validate(self):
        # Serialize overlapping closes for the same opening.
        opening = frappe.get_doc("POS Opening Entry", self.pos_opening_entry, for_update=True)
        if (self.pos_profile, self.user, self.company) != (opening.pos_profile, opening.user, opening.company):
            frappe.throw(_("Closing profile, cashier and company must match the opening."))
        if get_datetime(self.period_end_date) < get_datetime(self.period_start_date):
            frappe.throw(_("Closing end must follow its start."))
        populate_closing(self, closing_invoices(self.period_start_date, self.period_end_date,
            self.pos_profile, self.user, self.name, self.get("pos_counter_session")))
        super().validate()

    def validate_pos_invoices(self):
        # Core validates profile/owner/docstatus but rejects consolidated receipts.
        # Apply it to unposted receipts; independently verify all posted receipts.
        rows = self.pos_transactions
        pending = []
        for row in rows:
            invoice = frappe.get_doc("POS Invoice", row.pos_invoice)
            if not invoice.consolidated_invoice:
                pending.append(row)
                continue
            if (invoice.docstatus != 1 or invoice.pos_profile != self.pos_profile
                    or invoice.owner != self.user or invoice.company != self.company):
                frappe.throw(_("Invalid POS receipt {0}.").format(invoice.name))
            if frappe.db.get_value("Sales Invoice", invoice.consolidated_invoice, "docstatus") != 1:
                frappe.throw(_("Accounting invoice for {0} is not submitted.").format(invoice.name))
        self.pos_transactions = pending
        try:
            super().validate_pos_invoices()
        finally:
            self.pos_transactions = rows

    def on_submit(self):
        # Old pending receipts are posted individually in this transaction too.
        # Never attach these merges to closing: cancelling reconciliation must
        # not reverse sales that were already completed.
        for row in self.pos_transactions:
            post_invoice(frappe.get_doc("POS Invoice", row.pos_invoice))
        self.set_status(update=True, status="Submitted")
        self.db_set("error_message", "")
        self.update_opening_entry()
        frappe.publish_realtime(f"poe_{self.pos_opening_entry}_closed", self,
            docname=f"POS Opening Entry/{self.pos_opening_entry}", after_commit=True)
        frappe.publish_realtime("closing_process_complete", user=frappe.session.user, after_commit=True)

    def on_cancel(self):
        # Preserve reversal behavior for historical shift-owned merge logs only.
        for name in frappe.get_all("POS Invoice Merge Log", filters={
                "pos_closing_entry": self.name, "docstatus": 1}, pluck="name"):
            merge = frappe.get_doc("POS Invoice Merge Log", name)
            merge.flags.ignore_permissions = True
            merge.cancel()
        self.set_status(update=True, status="Cancelled")
        self.update_opening_entry(for_cancel=True)

    @frappe.whitelist()
    def retry(self):
        self.check_permission("submit")
        if self.docstatus != 1 or self.status != "Failed":
            frappe.throw(_("Only a failed submitted closing can be retried."))
        self.on_submit()
