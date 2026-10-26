import unittest
from unittest.mock import patch

import frappe
from retail.report_display_names import enrich_result


class TestReportDisplayNames(unittest.TestCase):
    def names(self, doctype, values):
        mapping = {'Employee': {'E-1': 'Ak Employee'}, 'Item': {'I-48': 'Current Item Name'},
                   'POS Branch Counter': {'C-1': 'Main Counter'}}
        return {key: value for key, value in mapping.get(doctype, {}).items() if key in values}

    def enrich(self, result):
        with patch('retail.report_display_names.names_for', side_effect=self.names), \
             patch('retail.report_display_names.user_names', return_value={'cashier@example.com': 'Cashier User'}):
            return enrich_result(result)

    def test_names_preserve_ids_facts_saved_description_and_idempotency(self):
        result = dict(columns=[
            dict(fieldname='pos_cashier', label='Cashier', fieldtype='Data'),
            dict(fieldname='item_code', label='Item', fieldtype='Link', options='Item'),
            dict(fieldname='counter', label='Counter', fieldtype='Data')],
            result=[dict(pos_cashier='E-1', item_code='I-48', item_name='Sold Packing Name',
                         counter='C-1', quantity=2, sales_amount=17.14)])
        self.enrich(result)
        row = result['result'][0]
        self.assertEqual(row['cashier_name'], 'Ak Employee')
        self.assertEqual(row['item_name'], 'Sold Packing Name')
        self.assertEqual(row['counter_name'], 'Main Counter')
        self.assertEqual((row['pos_cashier'], row['item_code'], row['quantity'], row['sales_amount']),
                         ('E-1', 'I-48', 2, 17.14))
        count = len(result['columns'])
        self.enrich(result)
        self.assertEqual(len(result['columns']), count)

    def test_employee_and_user_cashiers_and_missing_names(self):
        result = dict(columns=[
            dict(fieldname='cashier_employee', label='Cashier Employee', fieldtype='Link', options='Employee'),
            dict(fieldname='cashier', label='Cashier', fieldtype='Data')],
            result=[dict(cashier_employee='E-1', cashier='cashier@example.com'),
                    dict(cashier='cashier@example.com'), dict(cashier='UNKNOWN'), dict(cashier=None)])
        self.enrich(result)
        self.assertEqual([r['cashier_name'] for r in result['result']],
                         ['Ak Employee', 'Cashier User', 'UNKNOWN', None])
        self.assertEqual(sum(c['fieldname'] == 'cashier_name' for c in result['columns']), 1)

    def test_existing_name_columns_are_not_duplicated(self):
        result = dict(columns=[dict(fieldname='item_code', fieldtype='Link', options='Item'),
                               dict(fieldname='item_name', fieldtype='Data')],
                      result=[dict(item_code='I-48', item_name='Recorded Name')])
        self.enrich(result)
        self.assertEqual(len(result['columns']), 2)
        self.assertEqual(result['result'][0]['item_name'], 'Recorded Name')

