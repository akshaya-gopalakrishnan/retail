import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class POSCashMovement(Document):
	def validate(self):
		if not self.branch:
			frappe.throw(_("Branch is required."))
		if not self.counter:
			frappe.throw(_("Counter is required."))
		if not self.cashier_employee:
			frappe.throw(_("Cashier Employee is required."))
		if not self.cashier_shift:
			frappe.throw(_("Cashier Shift is required."))
		if not self.counter_session:
			frappe.throw(_("Counter Session is required."))
		if self.movement_type not in ("Cash In", "Cash Out"):
			frappe.throw(_("Movement Type must be Cash In or Cash Out."))
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero."))

		shift = frappe.get_doc("POS Cashier Shift", self.cashier_shift)
		if shift.cashier_employee != self.cashier_employee:
			frappe.throw(_("Cashier does not match the cashier shift."))
		if shift.branch != self.branch:
			frappe.throw(_("Branch does not match the cashier shift."))

		session = frappe.get_doc("POS Counter Session", self.counter_session)
		if session.cashier_shift != self.cashier_shift or session.cashier_employee != self.cashier_employee:
			frappe.throw(_("Counter session does not match the cashier shift."))
		if session.counter != self.counter:
			frappe.throw(_("Counter session belongs to another counter."))

		if not self.counter_code:
			self.counter_code = frappe.db.get_value("POS Branch Counter", self.counter, "counter_code")
		if not self.terminal_id:
			self.terminal_id = session.terminal_id
