import frappe
from frappe.model.document import Document


class VanExpenseType(Document):
	def validate(self):
		account = frappe.get_doc("Account", self.expense_account)
		if account.company != self.company or account.is_group or account.disabled or account.root_type != "Expense":
			frappe.throw("Select an enabled expense ledger belonging to this company.")
