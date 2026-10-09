import unittest
from unittest.mock import Mock, call, patch

import frappe
from retail.promotions import gift_voucher


class TestGiftVoucherPermissions(unittest.TestCase):
	def setUp(self):
		self.patch(frappe.local, "flags", new=frappe._dict(in_test=True), create=True)
		self.database = Mock()
		self.database.exists.return_value = False
		self.database.get_value.return_value = None
		self.get_doc = self.patch(frappe, "get_doc")
		self.get_all = self.patch(frappe, "get_all", return_value=[])
		self.patch(frappe, "db", new=self.database)
		self.patch(frappe, "throw", side_effect=frappe.ValidationError)
		self.patch(gift_voucher, "_", side_effect=lambda text: text)
		self.get_promotions = self.patch(gift_voucher, "get_active_promotions", return_value=[])
		self.create_voucher = self.patch(gift_voucher, "create_voucher")

	def patch(self, target, attribute, **kwargs):
		patcher = patch.object(target, attribute, **kwargs)
		self.addCleanup(patcher.stop)
		return patcher.start()

	def invoice(self, doctype="Sales Invoice", docstatus=1, **fields):
		doc = frappe._dict(doctype=doctype, name="INVOICE-TEST", docstatus=docstatus, **fields)
		doc.check_permission = Mock()
		self.get_doc.return_value = doc
		return doc

	def assert_no_issuance_or_disclosure(self):
		self.database.exists.assert_not_called()
		self.get_promotions.assert_not_called()
		self.create_voucher.assert_not_called()
		self.get_all.assert_not_called()

	def test_other_document_types_are_rejected_before_loading(self):
		for doctype in ("Purchase Invoice", "Gift Voucher Ledger", "User", ""):
			with self.subTest(doctype=doctype), self.assertRaises(frappe.ValidationError):
				gift_voucher.issue_for_invoice(doctype, "INVOICE-TEST")

		self.get_doc.assert_not_called()
		self.assert_no_issuance_or_disclosure()

	def test_unreadable_invoice_cannot_issue_or_disclose_vouchers(self):
		doc = self.invoice()
		doc.check_permission.side_effect = frappe.PermissionError

		with self.assertRaises(frappe.PermissionError):
			gift_voucher.issue_for_invoice(doc.doctype, doc.name)

		doc.check_permission.assert_called_once_with("read")
		self.assert_no_issuance_or_disclosure()

	def test_read_access_without_submit_access_cannot_issue_or_disclose_vouchers(self):
		doc = self.invoice()
		doc.check_permission.side_effect = [None, frappe.PermissionError]

		with self.assertRaises(frappe.PermissionError):
			gift_voucher.issue_for_invoice(doc.doctype, doc.name)

		self.assertEqual(doc.check_permission.call_args_list, [call("read"), call("submit")])
		self.assert_no_issuance_or_disclosure()

	def test_explicit_issuance_rejects_draft_and_cancelled_invoices(self):
		for doctype in sorted(gift_voucher.SALES_DOCTYPES):
			for docstatus in (0, 2):
				with self.subTest(doctype=doctype, docstatus=docstatus):
					doc = self.invoice(doctype, docstatus)
					with self.assertRaises(frappe.ValidationError):
						gift_voucher.issue_for_invoice(doctype, doc.name)
					self.assert_no_issuance_or_disclosure()

	def test_authorized_submitted_sales_and_pos_invoices_issue_and_return_vouchers(self):
		promotion = frappe._dict(min_sales_value=100, voucher_amount=10, multiply_with_sales_amount=0)
		self.get_promotions.return_value = [promotion]
		vouchers = [frappe._dict(voucher_code="GV-TEST", voucher_amount=10)]
		self.get_all.return_value = vouchers

		for doctype in sorted(gift_voucher.SALES_DOCTYPES):
			with self.subTest(doctype=doctype):
				doc = self.invoice(doctype, grand_total=100)
				self.assertEqual(gift_voucher.issue_for_invoice(doctype, doc.name), vouchers)
				self.assertEqual(doc.check_permission.call_args_list, [call("read"), call("submit")])
				self.create_voucher.assert_called_with(doc, promotion, 10)
				self.assertEqual(
					self.get_all.call_args.kwargs["filters"],
					{"issued_against_type": doctype, "issued_against": doc.name},
				)

	def test_submit_hook_cannot_issue_for_draft_cancelled_or_unsupported_documents(self):
		for doctype, docstatus in (
			("Sales Invoice", 0),
			("Sales Invoice", 2),
			("POS Invoice", 0),
			("POS Invoice", 2),
			("Purchase Invoice", 1),
		):
			with self.subTest(doctype=doctype, docstatus=docstatus):
				gift_voucher.issue_gift_vouchers(self.invoice(doctype, docstatus), "on_submit")
				self.assert_no_issuance_or_disclosure()

	def test_submit_hook_preserves_automatic_issuance(self):
		promotion = frappe._dict(min_sales_value=100, voucher_amount=10, multiply_with_sales_amount=0)
		self.get_promotions.return_value = [promotion]
		for doctype in sorted(gift_voucher.SALES_DOCTYPES):
			with self.subTest(doctype=doctype):
				doc = self.invoice(doctype, grand_total=100)
				gift_voucher.issue_gift_vouchers(doc, "on_submit")
				self.create_voucher.assert_called_with(doc, promotion, 10)
				doc.check_permission.assert_not_called()

	def test_returns_and_voucher_redemptions_do_not_issue_new_vouchers(self):
		for fields in ({"is_return": 1}, {"custom_gift_voucher_code": "GV-EXISTING"}):
			with self.subTest(fields=fields):
				gift_voucher.issue_gift_vouchers(self.invoice(**fields), "on_submit")
				self.assert_no_issuance_or_disclosure()

	def test_repeated_issuance_returns_existing_vouchers_without_creating_more(self):
		doc = self.invoice()
		self.database.exists.return_value = True
		self.database.get_value.return_value = "GV-EXISTING"
		vouchers = [frappe._dict(voucher_code="GV-EXISTING", voucher_amount=10)]
		self.get_all.return_value = vouchers

		self.assertEqual(gift_voucher.issue_for_invoice(doc.doctype, doc.name), vouchers)
		self.get_promotions.assert_not_called()
		self.create_voucher.assert_not_called()


if __name__ == "__main__":
	unittest.main()
