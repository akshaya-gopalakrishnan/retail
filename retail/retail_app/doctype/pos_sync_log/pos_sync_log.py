import frappe
from frappe.model.document import Document


class POSSyncLog(Document):
	def onload(self):
		from retail.pos_admin_recovery import load_correction
		load_correction(self)

	def validate(self):
		from retail.pos_list_settings import set_log_metadata
		if self.is_new():
			set_log_metadata(self)
		previous = self.get_doc_before_save()
		if previous:
			from retail.pos_admin_recovery import validate_save
			validate_save(self)
			return
		if self.get("operation_key") or (previous and previous.get("operation_key")):
			if not self.is_new() or not self.flags.allow_operation_write:
				frappe.throw("Operation receipts are immutable and can only be created by the POS service.")

	def on_trash(self):
		if self.get("operation_key"):
			frappe.throw("Operation receipts must be retained for idempotency.")
