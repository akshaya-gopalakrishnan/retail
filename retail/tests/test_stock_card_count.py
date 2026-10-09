from unittest import TestCase
from uuid import uuid4
import frappe
from retail.retail_app.report.low_stock_reorder_report import low_stock_reorder_report as report

class TestStockCardCount(TestCase):
    def test_count_matches_report_for_reorder_boundaries(self):
        savepoint = 'stock_count_' + uuid4().hex
        frappe.db.savepoint(savepoint)
        try:
            # qty, reorder level, disabled, stock item. None qty has no Bin.
            cases = [(None, 5, 0, 1), (-2, 5, 0, 1), (0, 5, 0, 1),
                     (4, 5, 0, 1), (5, 5, 0, 1), (6, 5, 0, 1),
                     (0, 5, 1, 1), (0, 5, 0, 0), (0, 0, 0, 1)]
            warehouse = 'count-check-' + uuid4().hex
            for qty, level, disabled, stock in cases:
                name = 'count-check-' + uuid4().hex
                frappe.db.sql('insert into `tabItem` (name,item_name,disabled,is_stock_item) values (%s,%s,%s,%s)', (name,name,disabled,stock))
                frappe.db.sql('insert into `tabItem Reorder` (name,parent,parenttype,parentfield,warehouse,warehouse_reorder_level) values (%s,%s,%s,%s,%s,%s)', (uuid4().hex,name,'Item','reorder_levels',warehouse,level))
                if qty is not None:
                    frappe.db.sql('insert into `tabBin` (name,item_code,warehouse,actual_qty) values (%s,%s,%s,%s)', (uuid4().hex,name,warehouse,qty))
            for out in (False, True):
                filters = frappe._dict(only_low_stock=1, only_out_of_stock=int(out))
                expected = len(report.get_data(filters))
                actual = report.get_stock_count(out)
                self.assertEqual(actual['value'], expected)
                fixture_rows = report.get_data(frappe._dict(filters,warehouse=warehouse))
                self.assertEqual(len(fixture_rows), 3 if out else 5)
                self.assertEqual(actual['route_options'], dict(only_low_stock=1,only_out_of_stock=int(out)))
        finally:
            frappe.db.rollback(save_point=savepoint)
