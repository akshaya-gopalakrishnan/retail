"""Retail sales compatibility for ERPNext's negative-batch stock setting."""
import frappe
from frappe.utils import cint
from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import SerialandBatchBundle
from erpnext.stock.stock_ledger import is_negative_stock_allowed


class RetailSerialAndBatchBundle(SerialandBatchBundle):
    def validate_negative_batch(self, batch_no, available_qty):
        if (
            self.voucher_type in ("POS Invoice", "Sales Invoice")
            and not self.has_serial_no
            and cint(frappe.db.get_single_value("Stock Settings", "allow_negative_stock_for_batch"))
            and is_negative_stock_allowed(item_code=self.item_code)
        ):
            return
        return super().validate_negative_batch(batch_no, available_qty)
