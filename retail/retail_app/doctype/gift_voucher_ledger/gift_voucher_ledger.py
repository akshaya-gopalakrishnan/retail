import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class GiftVoucherLedger(Document):
	def validate(self):
		self.voucher_kind = "Voucher Card" if self.get("voucher_card_batch") else "Promotion Voucher"
		previous = self.get_doc_before_save()
		if self.get("voucher_card_batch") or (previous and previous.get("voucher_card_batch")):
			if self.is_new() and not self.flags.card_service:
				frappe.throw("Generate voucher cards from their batch.")
			if not self.is_new():
				frappe.throw("Use the voucher card actions to update a card; its history is protected.")
		if flt(self.voucher_amount) <= 0:
			frappe.throw(_("Voucher Amount must be greater than zero."))
		if flt(self.balance_amount) < 0:
			frappe.throw(_("Balance Amount cannot be negative."))
		if flt(self.balance_amount) > flt(self.voucher_amount):
			frappe.throw(_("Balance Amount cannot be more than Voucher Amount."))

	def on_trash(self):
		if self.get("voucher_card_batch"):
			frappe.throw("Voucher cards cannot be deleted. Archive expired or fully used cards instead.")
