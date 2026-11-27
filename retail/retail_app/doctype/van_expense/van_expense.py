import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class VanExpense(Document):
	def validate(self):
		from retail.api.van_sales import _context, _amount, _mode_account, _settings, _manager
		driver = frappe.db.get_value("Van Session", self.van_session, "driver")
		ctx = _context(frappe._dict(sessionid=self.van_session, driverid=driver), active=True, lock=True)
		if self.company != ctx.company:
			frappe.throw("Expense company must match the van session.")
		self.amount = _amount(self.amount, "Expense amount")
		_mode_account(ctx, self.mode_of_payment)
		_settings(ctx)
		kind = frappe.get_doc("Van Expense Type", self.expense_type)
		kind.check_permission("read")
		if not kind.enabled or kind.company != self.company:
			frappe.throw("Expense type must be enabled in the session company.")
		account = frappe.get_doc("Account", kind.expense_account)
		if account.company != self.company or account.is_group or account.disabled or account.root_type != "Expense" or account.account_currency != ctx.currency:
			frappe.throw("Expense type requires an enabled expense ledger in company currency.")
		if kind.proof_required and not self.proof_url:
			frappe.throw("Receipt proof is required for this expense type.")
		if self.proof_url:
			files = frappe.get_all("File", filters={"file_url": self.proof_url, "is_private": 1}, fields=["name", "owner", "attached_to_doctype", "attached_to_name"], limit=2)
			if len(files) != 1:
				frappe.throw("Upload a private receipt file first.")
			file = files[0]
			if not _manager() and file.owner != frappe.session.user:
				frappe.throw("Receipt must belong to the authenticated user.", frappe.PermissionError)
			if file.attached_to_name and (file.attached_to_doctype != self.doctype or file.attached_to_name != self.name):
				frappe.throw("Receipt is already attached to another document.")
		if self.accounting_reference and (self.is_new() or self.has_value_changed("accounting_reference")):
			frappe.throw("Accounting Reference is assigned by ERP.")
		old = self.get_doc_before_save()
		if old and (old.van_session != self.van_session or old.company != self.company):
			frappe.throw("Expense session and company cannot be changed.")

	def on_submit(self):
		from retail.api.van_sales import _context, _mode_account, _settings
		driver = frappe.db.get_value("Van Session", self.van_session, "driver")
		ctx = _context(frappe._dict(sessionid=self.van_session, driverid=driver), active=True, lock=True)
		kind = frappe.get_doc("Van Expense Type", self.expense_type)
		settings = _settings(ctx)
		journal = frappe.new_doc("Journal Entry")
		journal.update(dict(company=self.company, posting_date=getdate(self.posting_date),
			voucher_type="Journal Entry", user_remark=f"Van expense {self.name}: {self.remarks or self.expense_type}"))
		journal.append("accounts", dict(account=kind.expense_account, debit_in_account_currency=self.amount, cost_center=settings.cost_center))
		journal.append("accounts", dict(account=_mode_account(ctx, self.mode_of_payment), credit_in_account_currency=self.amount, cost_center=settings.cost_center))
		# This tightly scoped service posts only configured accounts and a balanced amount.
		# It does not grant van drivers unrestricted Journal Entry permissions.
		journal.flags.ignore_permissions = True
		journal.insert()
		journal.submit()
		self.db_set("accounting_reference", journal.name)
		if self.proof_url:
			file = frappe.get_doc("File", {"file_url": self.proof_url, "is_private": 1})
			file.db_set({"attached_to_doctype": self.doctype, "attached_to_name": self.name})


def permission_query(user=None):
	from retail.van_assignment import is_operator
	if is_operator(user):
		return "`tabVan Expense`.van_session in (select name from `tabVan Session` where custom_salesperson=" + frappe.db.escape(user or frappe.session.user) + ")"
	return ""


def has_permission(doc, ptype=None, user=None):
	from retail.van_assignment import is_operator
	if is_operator(user) and frappe.db.get_value("Van Session", doc.van_session, "custom_salesperson") != (user or frappe.session.user):
		return False
