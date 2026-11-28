import unittest
from unittest.mock import patch, MagicMock
import frappe
from erpnext.stock import stock_ledger as core
from retail.core_compat.runtime import _install_sales_negative_stock_valuation

class TestSalesNegativeStockValuation(unittest.TestCase):
    def test_setting_controls_only_sales_and_preserves_known_rates(self):
        for enabled, doctype, known, expected, zero in [
            (1,'Sales Invoice',None,0.0,True),
            (1,'Sales Invoice',25,25,True),
            (0,'Sales Invoice',None,None,False),
            (1,'Purchase Invoice',None,None,False),
            (1,'Delivery Note',None,None,False),
        ]:
            with self.subTest(enabled=enabled,doctype=doctype,known=known), patch.object(frappe,'db',new=MagicMock()) as db, patch.object(core,'get_valuation_rate',return_value=known) as original:
                db.get_single_value.return_value=enabled
                _install_sales_negative_stock_valuation()
                wrapped=core.get_valuation_rate
                _install_sales_negative_stock_valuation()
                self.assertIs(wrapped,core.get_valuation_rate)
                self.assertEqual(core.get_valuation_rate('ITEM','WH',doctype,'DOC',currency='AED'),expected)
                original.assert_called_once_with('ITEM','WH',doctype,'DOC',zero,currency='AED')
