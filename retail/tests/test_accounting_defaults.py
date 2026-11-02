"""Run against retail-test.localhost; all business fixtures are rolled back."""

import unittest
from unittest.mock import patch

import frappe

from erpnext.setup.doctype.company.company import Company
from retail import accounting_defaults as defaults


class TestAccountingDefaults(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# Department tree provisioning is independent of accounting and the local
		# development site's historical Department tree is incomplete.
		self.departments = patch.object(Company, "create_default_departments")
		self.departments.start()
		self.addCleanup(self.departments.stop)
		self.addCleanup(frappe.db.rollback)
		self.addCleanup(frappe.clear_cache)

	def company(self, abbr="_RAD"):
		return frappe.get_doc({
			"doctype": "Company", "company_name": "_Test Retail Defaults " + abbr,
			"abbr": abbr, "default_currency": "AED", "country": "United Arab Emirates",
			"chart_of_accounts": "Standard", "create_chart_of_accounts_based_on": "Standard Template",
		}).insert(ignore_permissions=True)

	def test_new_company_defaults_and_separate_tenders_are_idempotent(self):
		company = self.company()
		self.assertEqual(company.get(defaults.VERSION_FIELD), 1)
		self.assertEqual(frappe.db.get_value("Account", company.default_income_account, "account_name"), "Sales")
		for field, spec in defaults.DEFAULTS.items():
			self.assertTrue(defaults._valid_account(company.get(field), company, spec), field)
		rows = frappe.get_all("Mode of Payment Account", filters={"company": company.name},
			fields=["parent", "default_account"])
		accounts = {r.parent: r.default_account for r in rows}
		self.assertEqual(accounts["Cash"], company.default_cash_account)
		self.assertNotEqual(accounts["Cash"], accounts["Card"])
		self.assertNotEqual(company.default_bank_account, accounts["Card"])
		for mode, spec in defaults.PAYMENT_ACCOUNT_SPECS.items():
			self.assertEqual(frappe.db.get_value("Account", accounts[mode], "account_name"), spec[0])
			self.assertTrue(defaults._valid_account(accounts[mode], company, spec))
		self.assertEqual(accounts["Wire Transfer"], company.default_bank_account)
		self.assertEqual(len(set(accounts.values())), 6)
		count = frappe.db.count("Account", {"company": company.name})
		company.save()
		defaults.initialize_company(company)
		defaults._initialize_payment_modes(company)
		self.assertEqual(frappe.db.count("Account", {"company": company.name}), count)
		self.assertEqual(frappe.db.count("Mode of Payment Account", {"company": company.name}), 6)

	def test_main_safe_is_preferred_only_when_it_is_a_usable_cash_account(self):
		original = Company.set_default_accounts
		for account_type, abbr in (("Cash", "_RADM"), ("Bank", "_RADB")):
			with self.subTest(account_type=account_type):
				def add_main_safe(company):
					original(company)
					defaults._create_account(company, "Main Safe", "Asset", account_type)

				with patch.object(Company, "set_default_accounts", add_main_safe):
					company = self.company(abbr)
				label = frappe.db.get_value("Account", company.default_cash_account, "account_name")
				self.assertEqual(label, "Main Safe" if account_type == "Cash" else "Cash")
				self.assertEqual(frappe.db.get_value("Mode of Payment Account",
					{"parent": "Cash", "company": company.name}, "default_account"), company.default_cash_account)

	def test_payment_mapping_overrides_are_preserved_without_extra_ledgers(self):
		company = self.company()
		own_card = defaults._create_account(company, "My Card Processor", "Asset", "Bank")
		row = frappe.db.get_value("Mode of Payment Account", {"parent": "Card", "company": company.name})
		frappe.db.set_value("Mode of Payment Account", row, "default_account", own_card)
		count = frappe.db.count("Account", {"company": company.name})
		defaults._initialize_payment_modes(company)
		self.assertEqual(frappe.db.get_value("Mode of Payment Account", row, "default_account"), own_card)
		self.assertEqual(frappe.db.count("Account", {"company": company.name}), count)

	def test_wire_transfer_does_not_inherit_an_auto_selected_card_clearing_account(self):
		original = Company.set_default_accounts

		def select_card_as_bank(company):
			original(company)
			card = defaults._create_account(company, "Manual Visa & Master Cards", "Asset", "Bank")
			company.db_set("default_bank_account", card, update_modified=False)

		with patch.object(Company, "set_default_accounts", select_card_as_bank):
			company = self.company()
		accounts = {r.parent: r.default_account for r in frappe.get_all("Mode of Payment Account",
			filters={"company": company.name}, fields=["parent", "default_account"])}
		self.assertEqual(accounts["Wire Transfer"], company.default_bank_account)
		self.assertNotEqual(accounts["Wire Transfer"], accounts["Card"])
		self.assertEqual(frappe.db.get_value("Account", accounts["Wire Transfer"], "account_name"), "Bank")

	def test_arbitrary_native_income_selection_does_not_become_sales_default(self):
		original = Company.set_default_accounts

		def select_other_income(company):
			original(company)
			other = defaults._create_account(company, "Other Income", "Income", "Income Account")
			company.db_set("default_income_account", other, update_modified=False)

		with patch.object(Company, "set_default_accounts", select_other_income):
			company = self.company()
		self.assertEqual(frappe.db.get_value("Account", company.default_income_account, "account_name"), "Sales")

	def test_site_owned_defaults_and_existing_companies_are_preserved(self):
		company = self.company()
		own_sales = defaults._create_account(company, "My Shop Sales", "Income", "Income Account")
		company.default_income_account = own_sales
		company.save()
		self.assertEqual(company.default_income_account, own_sales)
		# Simulate an existing company without the new-company marker.
		company.db_set(defaults.VERSION_FIELD, 0, update_modified=False)
		defaults.initialize_company(company)
		company.reload()
		self.assertEqual(company.get(defaults.VERSION_FIELD), 0)
		self.assertEqual(company.default_income_account, own_sales)
		profile = frappe.new_doc("POS Profile")
		profile.company = company.name
		defaults.set_pos_profile_defaults(profile)
		self.assertFalse(profile.income_account)

	def test_new_profile_inherits_defaults_but_preserves_its_own_choices(self):
		company = self.company()
		profile = frappe.new_doc("POS Profile")
		profile.company = company.name
		defaults.set_pos_profile_defaults(profile)
		self.assertEqual(profile.income_account, company.default_income_account)
		self.assertEqual(profile.expense_account, company.default_expense_account)
		self.assertEqual(profile.account_for_change_amount, company.default_cash_account)
		own_sales = defaults._create_account(company, "My Counter Sales", "Income", "Income Account")
		profile.income_account = own_sales
		defaults.set_pos_profile_defaults(profile)
		self.assertEqual(profile.income_account, own_sales)
		profile.set("__islocal", False)
		profile.income_account = None
		defaults.set_pos_profile_defaults(profile)
		self.assertIsNone(profile.income_account)

	def test_new_company_does_not_change_another_company_payment_accounts(self):
		first = self.company()
		before = frappe.get_all("Mode of Payment Account", filters={"company": first.name},
			fields=["name", "parent", "default_account"], order_by="name")
		second = self.company("_RAD2")
		after = frappe.get_all("Mode of Payment Account", filters={"company": first.name},
			fields=["name", "parent", "default_account"], order_by="name")
		self.assertEqual(before, after)
		self.assertNotEqual(first.default_income_account, second.default_income_account)
		self.assertTrue(second.default_income_account.endswith(" - _RAD2"))

	def test_all_six_payment_modes_post_to_correct_accounts_with_real_stock(self):
		company = self.company()
		warehouse = frappe.db.get_value("Warehouse", {"company": company.name, "is_group": 0})
		# Explicit zero-rate fixture avoids the development site's company-specific
		# Item custom-field tax defaults. Tax policy is outside ledger initialization.
		tax_account = defaults._create_account(company, "Test VAT", "Liability", "Tax")
		tax_template = frappe.get_doc({"doctype": "Item Tax Template", "title": "_Test Ledger Zero",
			"company": company.name, "taxes": [{"tax_type": tax_account, "tax_rate": 0}],
		}).insert(ignore_permissions=True)
		item = frappe.get_doc({"doctype": "Item", "item_code": "_Test Retail Ledger Routing",
			"item_name": "_Test Retail Ledger Routing", "item_group": "Products", "stock_uom": "Nos",
			"is_stock_item": 1, "valuation_rate": 10, "custom_tax": tax_template.name,
			"custom_purchase_tax_template": tax_template.name,
		}).insert(ignore_permissions=True)
		customer = frappe.get_doc({"doctype": "Customer", "customer_name": "_Test Retail Ledger Routing",
			"customer_type": "Individual", "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}),
			"territory": frappe.db.get_value("Territory", {"is_group": 0}),
		}).insert(ignore_permissions=True)
		# Existing site-wide auto-enrollment belongs to another test company.
		customer.db_set("loyalty_program", None, update_modified=False)
		stock = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
			"company": company.name, "items": [{"item_code": item.name, "qty": 6,
			"t_warehouse": warehouse, "basic_rate": 10, "expense_account": company.stock_adjustment_account,
			"cost_center": company.cost_center}],
		}).insert(ignore_permissions=True)
		stock.submit()
		for mode in ("Cash", "Card", "Credit Card", "Cheque", "Bank Draft", "Wire Transfer"):
			account = frappe.db.get_value("Mode of Payment Account", {"parent": mode, "company": company.name}, "default_account")
			invoice = frappe.get_doc({"doctype": "Sales Invoice", "company": company.name,
				"customer": customer.name, "currency": "AED", "conversion_rate": 1,
				"is_pos": 1, "update_stock": 1, "debit_to": company.default_receivable_account,
				"items": [{"item_code": item.name, "qty": 1, "rate": 20,
					"warehouse": warehouse, "cost_center": company.cost_center}],
				"payments": [{"mode_of_payment": mode, "account": account, "amount": 20}],
			}).insert(ignore_permissions=True)
			invoice.submit()
			gl = frappe.get_all("GL Entry", filters={"voucher_type": "Sales Invoice", "voucher_no": invoice.name,
				"is_cancelled": 0}, fields=["account", "debit", "credit"])
			self.assertAlmostEqual(sum(r.debit - r.credit for r in gl), 0, places=2)
			self.assertAlmostEqual(sum(r.credit for r in gl if r.account == company.default_income_account), 20)
			self.assertAlmostEqual(sum(r.debit for r in gl if r.account == account), 20)
			self.assertAlmostEqual(sum(r.debit for r in gl if r.account == company.default_expense_account), 10)
			self.assertAlmostEqual(sum(r.credit for r in gl if r.account == company.default_inventory_account), 10)
