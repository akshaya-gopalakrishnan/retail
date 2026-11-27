import unittest
from unittest.mock import Mock, patch
from retail.report_speed import stock_ledger


class TestStockLedgerSpeed(unittest.TestCase):
    def test_unfiltered_ledger_does_not_execute_query(self):
        run = Mock()
        with patch('frappe.msgprint'), patch('erpnext.stock.report.stock_ledger.stock_ledger.get_columns', return_value=['columns']):
            self.assertEqual(stock_ledger({'company': 'Co'}, run), (['columns'], []))
        run.assert_not_called()

    def test_filtered_ledger_preserves_result_metadata_and_warns_on_limit(self):
        run = Mock(return_value=(['columns'], list(range(501)), 'message', 'chart'))
        with patch('frappe.msgprint') as message:
            result = stock_ledger({'barcode': '123'}, run)
        self.assertEqual(result, (['columns'], list(range(500)), 'message', 'chart'))
        message.assert_called_once()
        run.return_value = (['columns'], [1], None)
        with patch('frappe.msgprint') as message:
            self.assertIs(stock_ledger({'warehouse': 'W'}, run), run.return_value)
        message.assert_not_called()
