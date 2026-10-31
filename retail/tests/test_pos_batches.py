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
                patch("retail.pos_serials.frappe.db.get_single_value", side_effect=lambda dt, field: "FIFO" if field == "pick_serial_and_batch_based_on" else 0), \
                patch("erpnext.stock.doctype.batch.batch.get_available_batches",return_value={"OLD":1,"NEW":3}) as available, \
                patch("erpnext.stock.serial_batch_bundle.SerialBatchCreation") as create:
            create.return_value.make_serial_and_batch_bundle.return_value=frappe._dict(name="BUNDLE")
            allocate_missing_tracking(doc)
        self.assertEqual(create.call_args_list[0].args[0]["batches"],{"OLD":1,"NEW":1})
        self.assertEqual(create.call_args_list[1].args[0]["batches"],{"NEW":2})
        self.assertEqual(available.call_args.args[0].based_on,"FIFO")

    def test_negative_batch_allocation_respects_both_permissions(self):
        from retail.pos_serials import allocate_missing_tracking
        for batch_allowed, stock_allowed in ((0, False), (0, True), (1, False), (1, True)):
            with self.subTest(batch_allowed=batch_allowed, stock_allowed=stock_allowed):
                rows = [frappe._dict(name="ROW", item_code="ITEM", warehouse="WH", stock_qty=3)]
                doc = SimpleNamespace(items=rows, is_return=0, name="POS", company="CO",
                    doctype="POS Invoice", posting_date="2026-10-31", posting_time="10:00:00", is_new=lambda:True)
                with patch("retail.pos_serials.frappe.get_cached_doc", return_value=frappe._dict(has_batch_no=1, has_serial_no=0)), \
                        patch("retail.pos_serials.frappe.db.get_single_value", side_effect=lambda dt, field: "FIFO" if field == "pick_serial_and_batch_based_on" else batch_allowed), \
                        patch("erpnext.stock.stock_ledger.is_negative_stock_allowed", return_value=stock_allowed), \
                        patch("erpnext.stock.doctype.batch.batch.get_available_batches", return_value={"OLD":0,"NEW":1}) as available, \
                        patch("erpnext.stock.serial_batch_bundle.SerialBatchCreation") as create, \
                        patch("retail.pos_serials.frappe.throw", side_effect=ValueError):
                    create.return_value.make_serial_and_batch_bundle.return_value=frappe._dict(name="BUNDLE")
                    if batch_allowed and stock_allowed:
                        allocate_missing_tracking(doc)
                        self.assertEqual(create.call_args.args[0]["batches"], {"NEW":1,"OLD":2})
                        self.assertTrue(available.call_args.args[0].consider_negative_batches)
                    else:
                        with self.assertRaises(ValueError):
                            allocate_missing_tracking(doc)
                        create.assert_not_called()

    def test_negative_stock_still_requires_an_eligible_batch(self):
        from retail.pos_serials import allocate_missing_tracking
        doc = SimpleNamespace(items=[frappe._dict(name="ROW",item_code="ITEM",warehouse="WH",stock_qty=1)],
            is_return=0,name="POS",company="CO",doctype="POS Invoice",posting_date="2026-10-31",
            posting_time="10:00:00",is_new=lambda:True)
        with patch("retail.pos_serials.frappe.get_cached_doc", return_value=frappe._dict(has_batch_no=1,has_serial_no=0)), \
                patch("retail.pos_serials.frappe.db.get_single_value", side_effect=lambda dt, field: "FIFO" if field == "pick_serial_and_batch_based_on" else 1), \
                patch("erpnext.stock.stock_ledger.is_negative_stock_allowed", return_value=True), \
                patch("erpnext.stock.doctype.batch.batch.get_available_batches", return_value={}), \
                patch("retail.pos_serials.frappe.get_all", return_value=[]), \
                patch("retail.pos_serials.frappe.throw", side_effect=ValueError) as throw:
            with self.assertRaises(ValueError):
                allocate_missing_tracking(doc)
            self.assertIn("No enabled, unexpired batch", throw.call_args.args[0])

    def test_backdated_negative_sale_uses_existing_batch_without_prior_stock(self):
        from retail.pos_serials import allocate_missing_tracking
        doc = SimpleNamespace(items=[frappe._dict(name="ROW",item_code="ITEM",warehouse="WH",stock_qty=20)],
            is_return=0,name="POS",company="CO",doctype="POS Invoice",posting_date="2026-10-31",
            posting_time="10:00:00",is_new=lambda:True)
        with patch("retail.pos_serials.frappe.get_cached_doc", return_value=frappe._dict(has_batch_no=1,has_serial_no=0)), \
                patch("retail.pos_serials.frappe.db.get_single_value", side_effect=lambda dt, field: "FIFO" if field == "pick_serial_and_batch_based_on" else 1), \
                patch("erpnext.stock.stock_ledger.is_negative_stock_allowed", return_value=True), \
                patch("erpnext.stock.doctype.batch.batch.get_available_batches", return_value={}), \
                patch("retail.pos_serials.frappe.get_all", return_value=[frappe._dict(name="B1", expiry_date=None)]), \
                patch("erpnext.stock.serial_batch_bundle.SerialBatchCreation") as create:
            create.return_value.make_serial_and_batch_bundle.return_value=frappe._dict(name="BUNDLE")
            allocate_missing_tracking(doc)
            self.assertEqual(create.call_args.args[0]["batches"], {"B1":20})

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

    def test_configured_batch_selection_and_negative_fallback(self):
        from retail.pos_serials import allocate_missing_tracking
        for method in ("FIFO", "LIFO", "Expiry"):
            for has_stock_history in (False, True):
                with self.subTest(method=method, has_stock_history=has_stock_history):
                    row = frappe._dict(name="ROW",item_code="ITEM",warehouse="WH",stock_qty=20)
                    doc = SimpleNamespace(items=[row],is_return=0,name="POS",company="CO",doctype="POS Invoice",
                        posting_date="2026-10-31",posting_time="10:00:00",is_new=lambda:True)
                    candidates = [frappe._dict(name="OLD",expiry_date=None),
                                  frappe._dict(name="NEW",expiry_date="2027-01-01")]
                    if method == "LIFO":
                        candidates.reverse()
                    expected = "OLD" if method == "FIFO" else "NEW"
                    with patch("retail.pos_serials.frappe.get_cached_doc", return_value=frappe._dict(has_batch_no=1,has_serial_no=0)), \
                            patch("retail.pos_serials.frappe.db.get_single_value", side_effect=lambda dt, field: method if field == "pick_serial_and_batch_based_on" else 1), \
                            patch("erpnext.stock.stock_ledger.is_negative_stock_allowed", return_value=True), \
                            patch("erpnext.stock.doctype.batch.batch.get_available_batches", return_value={expected:1} if has_stock_history else {}) as available, \
                            patch("retail.pos_serials.frappe.get_all", return_value=candidates) as batches, \
                            patch("erpnext.stock.serial_batch_bundle.SerialBatchCreation") as create:
                        create.return_value.make_serial_and_batch_bundle.return_value=frappe._dict(name="BUNDLE")
                        allocate_missing_tracking(doc)
                        self.assertEqual(available.call_args.args[0].based_on, method)
                        self.assertEqual(create.call_args.args[0]["batches"], {expected:20})
                        if not has_stock_history:
                            self.assertEqual(batches.call_args.kwargs["order_by"],
                                "creation desc, name desc" if method == "LIFO" else "creation asc, name asc")
