"""Keep accounting in ERPNext and extend only Sales Invoice loyalty behavior."""
import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from erpnext.accounts.doctype.loyalty_program.loyalty_program import get_loyalty_program_details_with_points
from retail import loyalty


class RetailSalesInvoice(SalesInvoice):
    def check_credit_limit(self):
        if self.flags.get("completed_pos_accounting"):
            from retail.pos_completed_sale import note_mismatch
            try:
                return super().check_credit_limit()
            except frappe.ValidationError as exc:
                note_mismatch(self, f"Credit limit changed after completed POS sale: {exc}")
                return
        return super().check_credit_limit()

    def validate_max_discount(self):
        if not self.is_consolidated:
            return super().validate_max_discount()

    def validate_selling_price(self):
        if not self.is_consolidated:
            return super().validate_selling_price()

    def calculate_taxes_and_totals(self):
        from retail.promotions.gift_voucher import calculate_invoice_totals
        return calculate_invoice_totals(self, super().calculate_taxes_and_totals)

    def validate(self):
        if self.is_consolidated:
            return super().validate()
        if self.docstatus == 1 and self.customer:
            loyalty.lock_customer(self)
        if self.is_return:
            loyalty.prepare_return(self)
        elif self.redeem_loyalty_points:
            program = loyalty.get_program(self.customer, self.loyalty_program, self.company)
            if not program:
                frappe.throw(_("The customer is not enrolled in a Loyalty Program."))
            self.loyalty_program = program.name
            self.loyalty_amount = flt(flt(self.loyalty_points) * flt(program.conversion_factor),
                                      self.precision("loyalty_amount"))
            self.loyalty_redemption_account = program.expense_account
            self.loyalty_redemption_cost_center = program.cost_center
        else:
            self.loyalty_points = self.loyalty_amount = 0
        # Core performs the accounting validation. Retail validates ledger points
        # separately, including signed return amounts and company-currency limits.
        points = self.loyalty_points
        self.loyalty_points = 0
        try:
            super().validate()
        finally:
            self.loyalty_points = points
        loyalty.validate_redemption(self)

    def before_submit(self):
        if not self.is_consolidated and self.loyalty_program:
            loyalty.lock_customer(self)
            loyalty.validate_redemption(self)
        super().before_submit()

    def before_cancel(self):
        if self.is_consolidated and frappe.db.exists("POS Invoice", {
                "consolidated_invoice": self.name, "pos_sync_source": "Offline POS"}):
            frappe.throw("Accounting for a completed POS bill cannot be cancelled; use a return.")
        if not self.is_consolidated and self.loyalty_program:
            loyalty.lock_customer(self)
        super().before_cancel()

    def apply_loyalty_points(self):
        if self.is_return:
            loyalty.restore_return(self)
        else:
            loyalty.redeem(self)

    def delete_loyalty_point_entry(self):
        # Core calls this on the ORIGINAL submitted invoice when a return changes.
        # Preserve that invoice's redemptions and stable earning-entry references.
        if self.docstatus == 2:
            loyalty.remove_invoice_entries(self)
            self.set_loyalty_program_tier()

    def make_loyalty_point_entry(self):
        details = get_loyalty_program_details_with_points(
            self.customer, company=self.company, loyalty_program=self.loyalty_program,
            expiry_date=self.posting_date, include_expired_entry=True,
            current_transaction_amount=flt(self.base_grand_total) - flt(self.loyalty_amount),
        )
        if not details or getdate(self.posting_date) < getdate(details.from_date) or (
            details.to_date and getdate(self.posting_date) > getdate(details.to_date)
        ):
            return
        returned = self.get_returned_amount()
        proportion = min(1, returned / flt(self.grand_total)) if flt(self.grand_total) > 0 else 0
        eligible = max(0, (flt(self.base_grand_total) - flt(self.loyalty_amount)) * (1 - proportion))
        points = cint(eligible / (flt(details.collection_factor) or 1))
        entries = loyalty.ledger_entries(self.customer, self.loyalty_program, self.company, lock=True)
        existing = next((e for e in entries if e.invoice_type == "Sales Invoice" and
                         e.invoice == self.name and not e.redeem_against), None)
        if existing:
            used = sum(cint(e.loyalty_points) for e in entries if e.redeem_against == existing.name)
            if points + used < 0:
                frappe.throw(_("Points earned on this invoice have been spent. Reverse those redemptions before returning it."))
            frappe.db.set_value("Loyalty Point Entry", existing.name,
                                {"loyalty_points": points, "purchase_amount": eligible})
        else:
            frappe.get_doc({
                "doctype": "Loyalty Point Entry", "company": self.company,
                "customer": self.customer, "loyalty_program": self.loyalty_program,
                "loyalty_program_tier": details.tier_name, "invoice_type": self.doctype,
                "invoice": self.name, "loyalty_points": points, "purchase_amount": eligible,
                "posting_date": self.posting_date,
                "expiry_date": add_days(self.posting_date, details.expiry_duration),
            }).insert(ignore_permissions=True)
        self.set_loyalty_program_tier()

    def on_cancel(self):
        super().on_cancel()
        if self.is_return and self.loyalty_program and not self.is_consolidated:
            loyalty.remove_invoice_entries(self)
            self.set_loyalty_program_tier()

    def get_returned_amount(self):
        # A locking read sees returns committed while this transaction was waiting.
        rows = frappe.db.sql(
            """select grand_total from `tabSales Invoice` where docstatus=1
               and is_return=1 and return_against=%s for update""", self.name,
        )
        return abs(sum(flt(row[0]) for row in rows))

    def make_loyalty_point_redemption_gle(self, gl_entries):
        start = len(gl_entries)
        super().make_loyalty_point_redemption_gle(gl_entries)
        if not self.is_consolidated and flt(self.conversion_rate) > 0:
            for entry in gl_entries[start:]:
                for side in ("debit", "credit"):
                    entry[f"{side}_in_transaction_currency"] = flt(
                        flt(entry.get(side)) / self.conversion_rate, self.precision("grand_total")
                    )
