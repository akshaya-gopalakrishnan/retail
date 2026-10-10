import unittest
from unittest.mock import Mock, patch

import frappe
from retail.api import pos_sync


class TestPOSInvoiceReference(unittest.TestCase):
    def test_new_sale_without_legacy_sales_invoice_column(self):
        db = Mock(has_column=Mock(return_value=False), get_value=Mock(return_value=None))
        with patch.object(frappe, 'db', db):
            self.assertIsNone(pos_sync._existing_invoice('SALE-1'))
        self.assertEqual(db.get_value.call_count, 1)
        self.assertEqual(db.get_value.call_args.args[0], 'POS Invoice')

    def test_legacy_sales_invoice_reference_is_preserved(self):
        db = Mock(has_column=Mock(return_value=True))
        db.get_value.side_effect = [None, frappe._dict(name='SI-1', docstatus=1)]
        with patch.object(frappe, 'db', db):
            result = pos_sync._existing_invoice('SALE-1')
        self.assertEqual(result.name, 'SI-1')
        self.assertEqual(result.doctype, 'Sales Invoice')
        self.assertEqual(db.get_value.call_args.args[0], 'Sales Invoice')

    def test_cancelled_pos_invoice_still_reserves_reference(self):
        db = Mock(get_value=Mock(return_value=frappe._dict(name='POS-1', docstatus=2)))
        with patch.object(frappe, 'db', db):
            result = pos_sync._existing_invoice('SALE-1')
        self.assertEqual(result.docstatus, 2)
        self.assertEqual(result.doctype, 'POS Invoice')
        self.assertEqual(db.get_value.call_args.args[1], {'external_pos_reference': 'SALE-1'})
        db.has_column.assert_not_called()
