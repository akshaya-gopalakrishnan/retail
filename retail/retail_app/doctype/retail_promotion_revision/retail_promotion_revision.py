import frappe
from frappe.model.document import Document


class RetailPromotionRevision(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw("Promotion revisions are immutable.")

    def on_trash(self):
        frappe.throw("Promotion revisions are retained for sale history.")
