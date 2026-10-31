import unittest
from unittest.mock import patch

import frappe
from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import SerialandBatchBundle
from retail.serial_batch_bundle import RetailSerialAndBatchBundle


class TestNegativeBatchSettings(unittest.TestCase):
    def test_only_permitted_non_serial_sales_skip_negative_batch_guard(self):
        for voucher in ("POS Invoice", "Sales Invoice", "Stock Entry"):
            for serial in (0, 1):
                for batch_allowed, stock_allowed in ((0, False), (0, True), (1, False), (1, True)):
                    with self.subTest(voucher=voucher, serial=serial, batch=batch_allowed, stock=stock_allowed):
                        bundle = RetailSerialAndBatchBundle(frappe._dict(doctype="Serial and Batch Bundle",
                            voucher_type=voucher, has_serial_no=serial, item_code="ITEM"))
                        with patch("retail.serial_batch_bundle.frappe.db.get_single_value", return_value=batch_allowed), \
                                patch("retail.serial_batch_bundle.is_negative_stock_allowed", return_value=stock_allowed), \
                                patch.object(SerialandBatchBundle, "validate_negative_batch") as native:
                            bundle.validate_negative_batch("B1", -20)
                            if voucher != "Stock Entry" and not serial and batch_allowed and stock_allowed:
                                native.assert_not_called()
                            else:
                                native.assert_called_once_with("B1", -20)
