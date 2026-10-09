import frappe
from frappe.model.document import Document


class POSSyncLog(Document):
	def validate(self):
		from retail.pos_list_settings import set_log_metadata
		if self.is_new():
			set_log_metadata(self)
		previous = self.get_doc_before_save()
		if self.get("operation_key") or (previous and previous.get("operation_key")):
			if not self.is_new() or not self.flags.allow_operation_write:
				frappe.throw("Operation receipts are immutable and can only be created by the POS service.")

	def on_trash(self):
		if self.get("operation_key"):
			frappe.throw("Operation receipts must be retained for idempotency.")
