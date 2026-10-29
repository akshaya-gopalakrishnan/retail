"""New batches opt in; existing valuation facts remain protected."""

import unittest
from unittest.mock import patch
from uuid import uuid4

import frappe

from retail.batch import RetailBatch


class TestBatchValuation(unittest.TestCase):
    def setUp(self):
        self.user = frappe.session.user
        frappe.set_user('Administrator')
        frappe.db.savepoint('batch_valuation_test')
        self.item = frappe.get_doc({
            'doctype': 'Item', 'name': 'batch-default-' + uuid4().hex,
            'item_name': 'Batch default test', 'stock_uom': 'Nos',
            'is_stock_item': 1, 'has_batch_no': 1, 'has_expiry_date': 0,
            'valuation_method': 'FIFO',
        })
        self.item.db_insert()

    def tearDown(self):
        frappe.db.rollback(save_point='batch_valuation_test')
        frappe.set_user(self.user)

    def batch(self, **values):
        return RetailBatch(dict(doctype='Batch', batch_id='batch-default-' + uuid4().hex,
            item=self.item.name, **values))

    def test_default_remains_unchecked_after_insert(self):
        doc = self.batch()
        doc.insert()
        self.assertEqual(doc.use_batchwise_valuation, 0)
        self.assertEqual(frappe.db.get_value('Batch', doc.name, 'use_batchwise_valuation'), 0)

    def test_explicit_opt_in_and_existing_batches(self):
        for value in (0, 1):
            doc = self.batch(use_batchwise_valuation=value)
            doc.insert()
            doc.reload()
            doc.save()
            self.assertEqual(doc.use_batchwise_valuation, value)
            doc.use_batchwise_valuation = 1 - value
            with self.assertRaises(frappe.ValidationError):
                doc.save()

    def test_native_moving_average_restriction_is_preserved(self):
        doc = self.batch(use_batchwise_valuation=1)
        doc.set("__islocal", 1)
        with patch('erpnext.stock.utils.get_valuation_method', return_value='Moving Average'), \
             patch.object(frappe.db, 'get_single_value', return_value=1):
            doc.set_batchwise_valuation()
        self.assertEqual(doc.use_batchwise_valuation, 0)
