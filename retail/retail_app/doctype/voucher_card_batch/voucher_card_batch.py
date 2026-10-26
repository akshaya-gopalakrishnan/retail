import frappe
from frappe.model.document import Document
from frappe.utils import cint, getdate, get_time


class VoucherCardBatch(Document):
    def validate(self):
        from retail.voucher_cards import card_money
        self.voucher_amount = card_money(self.voucher_amount)
        if cint(self.card_count) < 1 or float(self.card_count) != cint(self.card_count):
            frappe.throw('Number of Cards must be a positive whole number.')
        if getdate(self.expiry_date) < getdate(self.valid_from):
            frappe.throw('Expiry Date cannot be before Valid From.')
        hours = [self.get(field) is not None and self.get(field) != '' for field in ('active_from_time', 'active_to_time')]
        if self.use_redemption_hours and not all(hours):
            frappe.throw('Enter both activation times, or turn off Set Activation Times to use whole dates.')
        if self.use_redemption_hours:
            for field in ('active_from_time', 'active_to_time'):
                self.set(field, str(get_time(self.get(field))))
            if getdate(self.valid_from) == getdate(self.expiry_date) and get_time(self.active_to_time) < get_time(self.active_from_time):
                frappe.throw('Active To date and time cannot be before Active From date and time.')
        if frappe.get_cached_value('Company', self.company, 'default_currency') != self.currency:
            frappe.throw('Use the company currency for voucher cards.')
        if not self.all_products and not self.restrictions:
            frappe.throw('Select eligible items, brands or categories, or enable All Products.')
        for row in self.restrictions:
            if sum(bool(row.get(k)) for k in ('item_code', 'brand', 'item_group')) != 1:
                frappe.throw('Each eligibility row must select exactly one item, brand or category.')
        for field in ('label_width', 'label_height'):
            if not 20 <= float(self.get(field) or 0) <= 300:
                frappe.throw('Label dimensions must be between 20 and 300 mm.')
        if self.print_from < 1 or self.print_to < self.print_from or self.print_to - self.print_from >= 500:
            frappe.throw('Choose a print range of 1 to 500 cards.')
        if self.is_new() and (self.generation_status != 'Draft' or self.generated_count or self.generation_error):
            frappe.throw('New batches must start in Draft without generated cards.')
        previous = self.get_doc_before_save()
        if previous:
            for field in ('generation_status', 'generated_count', 'generation_error'):
                if (self.get(field) or '') != (previous.get(field) or ''):
                    frappe.throw('Generation progress is managed by the system.')
        if previous and previous.generation_status != 'Draft':
            for field in ('company', 'currency', 'voucher_amount', 'card_count', 'valid_from', 'expiry_date', 'use_redemption_hours', 'active_from_time', 'active_to_time', 'all_products'):
                current, old = self.get(field), previous.get(field)
                if field in ('valid_from', 'expiry_date'):
                    current, old = getdate(current), getdate(old)
                if field in ('active_from_time', 'active_to_time'):
                    if not self.use_redemption_hours and not previous.use_redemption_hours:
                        continue
                    current = get_time(current) if current is not None and current != '' else None
                    old = get_time(old) if old is not None and old != '' else None
                if current != old:
                    frappe.throw('Batch value, quantity, dates, hours and eligibility are locked after generation starts.')
            keys = ('item_code', 'brand', 'item_group')
            if [[r.get(k) for k in keys] for r in self.restrictions] != [[r.get(k) for k in keys] for r in previous.restrictions]:
                frappe.throw('Eligibility is locked after generation starts.')

    def on_update(self):
        previous = self.get_doc_before_save()
        if previous and not previous.activate_all_cards and self.activate_all_cards:
            from retail.voucher_cards import activate_batch
            activate_batch(self.name)

    def on_trash(self):
        if self.generation_status != 'Draft' or frappe.db.exists('Gift Voucher Ledger', {'voucher_card_batch': self.name}):
            frappe.throw('Generated voucher batches must be retained for audit.')
