import unittest
from unittest.mock import patch, MagicMock

import frappe
from erpnext.stock import serial_batch_bundle as core
from retail.core_compat.runtime import _install_batch_negative_stock_setting


class TestBatchNegativeStockSetting(unittest.TestCase):
    def run_quantity_update(self, enabled):
        with patch.object(core, 'throw_negative_batch_validation', side_effect=frappe.ValidationError('Negative batch')) as original, \
             patch.object(core, 'flt', side_effect=lambda value, precision=None: float(value)), \
             patch.object(core, 'get_batchwise_qty', return_value={'BATCH-1': -1}), \
             patch.object(core, 'get_batch_current_qty', return_value=0), \
             patch.object(frappe, 'get_precision', return_value=6), \
             patch.object(frappe, 'db', new=MagicMock()) as db:
            db.get_single_value.return_value = enabled
            _install_batch_negative_stock_setting()
            wrapped = core.throw_negative_batch_validation
            _install_batch_negative_stock_setting()
            self.assertIs(wrapped, core.throw_negative_batch_validation)
            if enabled:
                core.update_batch_qty('Sales Invoice', 'SI-TEST', 1)
                db.set_value.assert_called_once_with('Batch', 'BATCH-1', 'batch_qty', -1)
                original.assert_not_called()
            else:
                with self.assertRaises(frappe.ValidationError):
                    core.update_batch_qty('Sales Invoice', 'SI-TEST', 1)
                db.set_value.assert_not_called()
                original.assert_called_once_with('BATCH-1', -1)
            db.get_single_value.assert_called_once_with('Stock Settings', 'allow_negative_stock_for_batch')

    def test_enabled_allows_negative_batch_total(self):
        self.run_quantity_update(1)

    def test_disabled_preserves_native_block(self):
        self.run_quantity_update(0)
