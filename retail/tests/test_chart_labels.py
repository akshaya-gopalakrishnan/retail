import unittest
from unittest.mock import patch
from retail.chart_labels import report_labels, relabel


class TestChartLabels(unittest.TestCase):
    def test_names_preserve_duplicate_titles_and_values(self):
        result = {'columns': [{'fieldtype': 'Link', 'options': 'Item', 'fieldname': 'item_code'}],
                  'result': [{'item_code': 'ID1'}, {'item_code': 'ID2'}],
                  'chart': {'data': {'labels': ['ID1', 'ID2'], 'datasets': [{'name': 'Quantity', 'values': [5, 9]}]}}}
        with patch('retail.chart_labels.names_for', return_value={'ID1': 'Water', 'ID2': 'Water'}):
            report_labels(result)
        self.assertEqual(result['chart']['data']['labels'], ['Water', 'Water'])
        self.assertEqual(result['chart']['data']['datasets'][0]['values'], [5, 9])
        self.assertEqual(result['result'][0]['item_code'], 'ID1')

    def test_dataset_names_and_fallback(self):
        data = {'labels': ['Jan'], 'datasets': [{'name': 'CUSTOMER-ID', 'values': [10]}]}
        relabel(data, {'CUSTOMER-ID': 'Customer Name'})
        self.assertEqual(data['labels'], ['Jan'])
        self.assertEqual(data['datasets'][0]['name'], 'Customer Name')
