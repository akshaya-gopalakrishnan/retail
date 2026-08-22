import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class GiftVoucherLedger(Document):
	def validate(self):
		if flt(self.voucher_amount) <= 0:
			frappe.throw(_("Voucher Amount must be greater than zero."))
		if flt(self.balance_amount) < 0:
			frappe.throw(_("Balance Amount cannot be negative."))
		if flt(self.balance_amount) > flt(self.voucher_amount):
			frappe.throw(_("Balance Amount cannot be more than Voucher Amount."))

