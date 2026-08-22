import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from retail.promotions.scheme_builder import validate_active_dates


class GiftVoucherPromotion(Document):
	def validate(self):
		validate_active_dates(self)
		if flt(self.min_sales_value) <= 0:
			frappe.throw(_("Min Sales Value must be greater than zero."))
		if flt(self.voucher_amount) <= 0:
			frappe.throw(_("Voucher Amount must be greater than zero."))
		if flt(self.expiry_days) < 0:
			frappe.throw(_("Expiry Days cannot be negative."))
