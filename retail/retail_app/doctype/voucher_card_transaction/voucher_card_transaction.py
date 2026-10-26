import frappe
from frappe.model.document import Document


class VoucherCardTransaction(Document):
    def validate(self):
        if not self.is_new() or not self.flags.card_service:
            frappe.throw('Voucher card history is written only by voucher operations.')

    def on_trash(self):
        frappe.throw('Voucher card history cannot be deleted.')
