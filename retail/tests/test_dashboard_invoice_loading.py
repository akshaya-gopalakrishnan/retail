"""Dashboard input loading retains parent/child identity and normal fallback."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from retail.retail_app.report import profitability as p


class TestDashboardInvoiceLoading(unittest.TestCase):
    def test_only_calculation_children_are_loaded_with_exact_parent_identity(self):
        for doctype in ('Sales Invoice', 'POS Invoice'):
            with self.subTest(doctype=doctype):
                parent = frappe._dict(name='INV', company='Company', docstatus=1, custom_branch='Branch')
                items = [frappe._dict(name='ROW', idx=1, base_net_amount=-25)]
                taxes = [frappe._dict(name='TAX', idx=1, base_tax_amount_after_discount_amount=-1.25)]
                db = Mock()
                db.get_value.return_value = parent
                db.get_values.side_effect = [items, taxes]
                meta = Mock()
                meta.get_field.side_effect = lambda field: SimpleNamespace(options=field + ' Child')
                with patch.object(frappe, 'db', db), patch.object(frappe, 'get_meta', return_value=meta), patch.object(
                    frappe, 'get_doc', side_effect=lambda data: data
                ):
                    doc = p.load_dashboard_invoice(doctype, 'INV')
                self.assertEqual(doc['items'], items)
                self.assertEqual(doc['taxes'], taxes)
                self.assertEqual(doc.custom_branch, 'Branch')
                self.assertEqual(doc.doctype, doctype)
                self.assertEqual(db.get_values.call_count, 2)
                for call, field in zip(db.get_values.call_args_list, ('items', 'taxes')):
                    self.assertEqual(call.args[1], dict(parent='INV', parenttype=doctype, parentfield=field))
                    self.assertEqual(call.kwargs['order_by'], 'idx asc')

    def test_missing_invoice_uses_standard_error_path(self):
        db = Mock()
        db.get_value.return_value = None
        with patch.object(frappe, 'db', db), patch.object(frappe, 'get_doc', side_effect=RuntimeError('missing')) as load:
            with self.assertRaisesRegex(RuntimeError, 'missing'):
                p.load_dashboard_invoice('Sales Invoice', 'DELETED')
        load.assert_called_once_with('Sales Invoice', 'DELETED')
        db.get_values.assert_not_called()

    def test_permission_filtered_selection_is_unchanged(self):
        for enabled in (False, True):
            with patch.object(frappe, 'get_list', return_value=[]) as select, patch.object(p, 'load_dashboard_invoice') as load:
                self.assertEqual(p.profitability_rows({'company': 'Allowed', 'from_date': '2026-10-01', 'to_date': '2026-10-21'}, dashboard=enabled), [])
                self.assertEqual(select.call_args.kwargs['filters']['company'], 'Allowed')
                load.assert_not_called()
