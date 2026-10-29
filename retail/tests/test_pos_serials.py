import unittest
from unittest.mock import patch

import frappe

from retail.pos_serials import apply_master_serials, serial_fields


class TestPOSSerials(unittest.TestCase):
    def item(self, **values):
        return frappe._dict(name="SERIAL-ITEM", stock_uom="Nos", has_serial_no=1,
                            uoms=[frappe._dict(uom="Pair", conversion_factor=2)], **values)

    def test_serial_mapping_and_stock_uom_quantity(self):
        result = serial_fields({"qty": 1, "uom": "Pair", "serial_no": " S1\nS2 "}, self.item())
        self.assertEqual(result, {"serial_no": "S1\nS2", "use_serial_batch_fields": 1})
        self.assertEqual(serial_fields({"qty": -1, "serial_no": "S1"}, self.item())["serial_no"], "S1")

    def test_missing_wrong_count_and_duplicate_serials_rejected(self):
        with patch("retail.pos_serials.frappe.throw", side_effect=ValueError):
            for raw in ("S1\nS2", ["S1"]):
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    serial_fields({"qty": 1, "serial_no": raw}, self.item())
            with self.assertRaises(ValueError):
                serial_fields({"qty": 2, "serial_no": "S1\nS1"}, self.item())
            with self.assertRaises(ValueError):
                serial_fields({"qty": 1, "serial_no": "S1"}, self.item(), {"S1"})

    def test_ordinary_items_unchanged(self):
        self.assertEqual(serial_fields({"qty": 2}, frappe._dict(has_serial_no=0)), {})

    def test_omitted_serials_are_optional(self):
        for raw in (None, "", "  "):
            self.assertEqual(serial_fields({"qty": 1, "serial_no": raw}, self.item()), {})

    def test_serial_batch_is_derived_and_mixed_batches_rejected(self):
        row = {"qty": 2, "serial_no": "S1\nS2"}
        with patch("retail.pos_serials.frappe.get_all", return_value=["B1", "B1"]):
            self.assertEqual(serial_fields(row, self.item(has_batch_no=1))["batch_no"], "B1")
        with patch("retail.pos_serials.frappe.get_all", return_value=["B1", "B2"]), \
                patch("retail.pos_serials.frappe.throw", side_effect=ValueError), self.assertRaises(ValueError):
            serial_fields(row, self.item(has_batch_no=1))

    def test_master_snapshot_is_scoped_and_clears_sold_serials(self):
        items = [frappe._dict(item_code="A", has_serial_no=1),
                 frappe._dict(item_code="B", has_serial_no=1),
                 frappe._dict(item_code="C", has_serial_no=0)]
        with patch("retail.pos_serials.frappe.get_all", return_value=[frappe._dict(name="S1", item_code="A")]) as query:
            apply_master_serials(items, "Counter Warehouse")
        self.assertEqual([r.serial_numbers for r in items], [["S1"], [], []])
        self.assertEqual(query.call_args.kwargs["filters"], {
            "item_code": ["in", ["A", "B"]], "warehouse": "Counter Warehouse", "status": "Active"})

    def test_existing_item_mapper_keeps_selected_serial(self):
        from retail.api.pos_sync import _append_invoice_items
        doc = frappe.new_doc("POS Invoice")
        row = {"item_code": "SERIAL-ITEM", "qty": 1, "rate": 10,
               "uom": "Nos", "conversion_factor": 1, "serial_no": "S1"}
        with patch("retail.api.pos_sync._resolve_item", return_value="SERIAL-ITEM"), \
                patch("retail.api.pos_sync.frappe.get_cached_doc", return_value=self.item()), \
                patch("retail.api.pos_sync.get_item_tax_rate", return_value=0):
            _append_invoice_items(doc, {"items": [row]}, frappe._dict(warehouse="WH", cost_center="CC"))
        self.assertEqual(doc.items[0].serial_no, "S1")
        self.assertEqual(doc.items[0].use_serial_batch_fields, 1)
        self.assertEqual(doc.items[0].warehouse, "WH")
