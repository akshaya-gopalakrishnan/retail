"""Missing invoice accounts use native precedence without changing business values."""
import unittest
from unittest.mock import Mock, patch

import frappe
from retail.domains.sales import invoice_accounts as policy


class TestSalesInvoiceAccounts(unittest.TestCase):
    def setUp(self):
        self.item = {}
        self.group = {}
        self.brand = {}
        for target, replacement in (
            ('get_item_defaults', lambda *args: self.item),
            ('get_item_group_defaults', lambda *args: self.group),
            ('get_brand_defaults', lambda *args: self.brand),
        ):
            context = patch.object(policy, target, side_effect=replacement)
            context.start()
            self.addCleanup(context.stop)
        context = patch.object(frappe, 'get_cached_value', return_value='Company Sales')
        context.start()
        self.addCleanup(context.stop)

    def doc(self, **values):
        return frappe._dict(doctype='Sales Invoice', company='Company', docstatus=0,
                            items=[frappe._dict(name='ROW', item_code='SKU', qty=3, rate=7, **values)])

    def test_native_precedence(self):
        for item, group, brand, expected in (
            ('Item Sales', 'Group Sales', 'Brand Sales', 'Item Sales'),
            (None, 'Group Sales', 'Brand Sales', 'Group Sales'),
            (None, None, 'Brand Sales', 'Brand Sales'),
            (None, None, None, 'Company Sales'),
        ):
            with self.subTest(expected=expected):
                self.item = dict(income_account=item)
                self.group = dict(income_account=group)
                self.brand = dict(income_account=brand)
                doc = self.doc()
                policy.set_missing_income_accounts(doc)
                row = doc.get('items')[0]
                self.assertEqual(row.income_account, expected)
                self.assertEqual((row.qty, row.rate), (3, 7))

    def test_existing_manual_accounts_and_complete_invoices_need_no_reads(self):
        doc = self.doc(income_account='Selected Account')
        with patch.object(policy, 'get_item_defaults', side_effect=AssertionError('No lookup needed')), \
                patch.object(frappe, 'get_cached_value', side_effect=AssertionError('No lookup needed')):
            policy.set_missing_income_accounts(doc)
        self.assertEqual(doc.get('items')[0].income_account, 'Selected Account')

    def test_duplicate_rows_read_once_and_unnamed_server_rows_do_not_collide(self):
        doc = self.doc()
        doc['items'] = [frappe._dict(item_code=code) for code in ['A', 'A', 'B']]
        with patch.object(policy, 'get_item_defaults', side_effect=lambda code, company: {'income_account':code}) as read:
            policy.set_missing_income_accounts(doc)
        self.assertEqual(read.call_count, 2)
        self.assertEqual([row.income_account for row in doc.get('items')], ['A', 'A', 'B'])

    def test_submitted_pos_consolidated_and_van_documents_unchanged(self):
        for field in ('docstatus', 'is_pos', 'is_consolidated', 'custom_is_van_sale'):
            doc = self.doc()
            doc[field] = 1
            with patch.object(policy, 'resolve_missing', side_effect=AssertionError('Must not touch this invoice')):
                policy.set_missing_income_accounts(doc)

    def test_draft_to_submit_can_fill_missing_accounts(self):
        doc = self.doc()
        doc.update(docstatus=1, _action='submit')
        policy.set_missing_income_accounts(doc)
        self.assertEqual(doc.get('items')[0].income_account, 'Company Sales')

    def test_no_default_leaves_native_validation_in_charge(self):
        doc = self.doc()
        with patch.object(frappe, 'get_cached_value', return_value=None):
            policy.set_missing_income_accounts(doc)
        self.assertIsNone(doc.get('items')[0].income_account)

    def test_rpc_checks_document_company_and_item_permissions(self):
        doc = self.doc()
        doc.is_new = Mock(return_value=True)
        doc.check_permission = Mock()
        company = Mock()
        item = Mock()
        with patch.object(frappe.local, 'flags', frappe._dict(in_test=True), create=True), \
                patch.object(frappe, 'get_doc', return_value=doc), \
                patch.object(frappe, 'parse_json', return_value={}), \
                patch.object(frappe, 'get_cached_doc', side_effect=lambda dt, name: company if dt=='Company' else item):
            result = policy.get_missing_income_accounts('{}')
        doc.check_permission.assert_called_once_with('create')
        company.check_permission.assert_called_once_with('read')
        item.check_permission.assert_called_once_with('read')
        self.assertEqual(result[0]['income_account'], 'Company Sales')
