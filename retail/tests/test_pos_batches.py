import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from retail.pos_serials import apply_master_batches, serial_fields


class TestPOSBatches(unittest.TestCase):
    def test_batch_row_and_ordinary_row(self):
        item = frappe._dict(name="ITEM", has_batch_no=1)
        with patch("retail.pos_serials.frappe.db.get_value", return_value=frappe._dict(item="ITEM", disabled=0)):
            self.assertEqual(serial_fields({"batch_no": "B1"}, item),
                             {"batch_no": "B1", "use_serial_batch_fields": 1})
        self.assertEqual(serial_fields({}, frappe._dict(name="PLAIN")), {})

    def test_missing_invalid_and_wrong_item_batch(self):
        with patch("retail.pos_serials.frappe.throw", side_effect=ValueError):
            for raw in (["B1"],):
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    serial_fields({"batch_no": raw}, frappe._dict(name="ITEM", has_batch_no=1))
            for batch in (None, frappe._dict(item="OTHER", disabled=0), frappe._dict(item="ITEM", disabled=1)):
                with patch("retail.pos_serials.frappe.db.get_value", return_value=batch), self.assertRaises(ValueError):
                    serial_fields({"batch_no": "B1"}, frappe._dict(name="ITEM", has_batch_no=1))

    def test_omitted_batches_are_optional(self):
        for raw in (None, "", "  "):
            self.assertEqual(serial_fields({"qty":1,"batch_no":raw},
                            frappe._dict(name="ITEM",has_batch_no=1)), {})

    def test_fifo_spans_batches_and_deducts_other_rows(self):
        from retail.pos_serials import allocate_missing_tracking
        rows = [frappe._dict(name="ROW1",item_code="ITEM",warehouse="WH",stock_qty=2),
                frappe._dict(name="ROW2",item_code="ITEM",warehouse="WH",stock_qty=2)]
        doc = SimpleNamespace(items=rows,is_return=0,name="POS",company="CO",doctype="POS Invoice",
                              posting_date="2026-10-28",posting_time="10:00:00",is_new=lambda:True)
        with patch("retail.pos_serials.frappe.get_cached_doc",return_value=frappe._dict(has_batch_no=1,has_serial_no=0)), \
                patch("erpnext.stock.doctype.batch.batch.get_available_batches",return_value={"OLD":1,"NEW":3}) as available, \
                patch("erpnext.stock.serial_batch_bundle.SerialBatchCreation") as create:
            create.return_value.make_serial_and_batch_bundle.return_value=frappe._dict(name="BUNDLE")
            allocate_missing_tracking(doc)
        self.assertEqual(create.call_args_list[0].args[0]["batches"],{"OLD":1,"NEW":1})
        self.assertEqual(create.call_args_list[1].args[0]["batches"],{"NEW":2})
        self.assertEqual(available.call_args.args[0].based_on,"FIFO")

    def test_master_uses_core_available_quantity_and_empty_snapshot(self):
        items = [frappe._dict(item_code="ITEM", has_batch_no=1),
                 frappe._dict(item_code="PLAIN", has_batch_no=0)]
        with patch("erpnext.stock.doctype.batch.batch.get_batch_qty", return_value=[
                frappe._dict(batch_no="B1", qty=3.5, expiry_date="2027-01-01")]) as query:
            apply_master_batches(items, "WH")
        query.assert_called_once_with(item_code="ITEM", warehouse="WH")
        self.assertEqual(items[0].batches, [{"batch_no":"B1", "available_qty":3.5,
                                          "expiry_date":"2027-01-01", "warehouse":"WH"}])
        self.assertEqual(items[1].batches, [])
        with patch("erpnext.stock.doctype.batch.batch.get_batch_qty", return_value=[]):
            apply_master_batches(items, "WH")
        self.assertEqual(items[0].batches, [])
