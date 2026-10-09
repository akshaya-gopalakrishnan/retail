import sqlite3
import unittest
from unittest.mock import patch
import frappe
from retail.retail_app.report.profitability import profit_values, profitability_total, sales_cost_join, sales_cost_sql, set_profit
from retail.retail_app.report.van_sales_report_utils import signed_amount, signed_qty, add_total_row


class TestProfitability(unittest.TestCase):
    def test_a_b_c(self):
        for revenue, cost, expected in [(1000,700,300),(800,560,240),(105/1.05,70,30)]:
            profit, margin = profit_values(revenue,cost)
            self.assertAlmostEqual(profit,expected)
            self.assertAlmostEqual(margin,30)
        self.assertEqual(profit_values(0,70),(-70,0))
        self.assertEqual(profit_values(-200,-140),(-60,30))
        self.assertEqual(profit_values(100,None),(None,None))
        self.assertEqual(profit_values(None,50),(None,None))

    def test_movement_total_uses_weighted_margin(self):
        from retail.retail_app.report.margin_by_movement import margin_by_movement as report
        rows = [frappe._dict(net_sales=100, cost_amount=90),
                frappe._dict(net_sales=900, cost_amount=450)]
        with patch.object(report, "get_data", return_value=rows):
            result = report.execute({})
        self.assertTrue(result[5])
        self.assertEqual(result[1][-1].profit_percent, 46)

    def test_totals_preserve_unavailable_values(self):
        for field in ("net_sales", "cost_amount"):
            rows = [frappe._dict(net_sales=100, cost_amount=70),
                    frappe._dict(net_sales=200, cost_amount=80)]
            rows[1][field] = None
            total = profitability_total(rows, "item_code")
            self.assertIsNone(total[field])
            self.assertIsNone(total.gross_profit)
            self.assertIsNone(total.profit_percent)

    def test_return_signs_and_weighted_total(self):
        row=frappe._dict(is_return=1,stock_qty=-2,base_net_amount=-200)
        self.assertEqual((signed_qty(row),signed_amount(row)),(-2,-200))
        rows=[frappe._dict(net_sales=1000,cost_amount=700,gross_profit=300,profit_percent=30),
              frappe._dict(net_sales=-200,cost_amount=-140,gross_profit=-60,profit_percent=30)]
        total=add_total_row(rows,'item_code',label='Total')[-1]
        self.assertEqual((total.net_sales,total.cost_amount,total.gross_profit,total.profit_percent),(800,560,240,30))

    def test_posted_cost_foc_delivery_returns_reposting_and_cancelled(self):
        db=sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript('''
        create table `tabSales Invoice` (name text, update_stock int,docstatus int,is_return int);
        create table `tabDelivery Note` (name text,docstatus int);
        insert into `tabDelivery Note` values ('DN',1);
        create table `tabSales Invoice Item` (name text,parent text,delivery_note text,dn_detail text,stock_qty real);
        create table `tabStock Ledger Entry` (voucher_type text,voucher_no text,voucher_detail_no text,
            stock_value_difference real,actual_qty real,is_cancelled int);
        insert into `tabSales Invoice` values ('SI',1,1,0),('DN-SI',0,1,0),('RETURN',1,1,1),('CANCELLED',1,2,0);
        insert into `tabSales Invoice Item` values ('I','SI',null,null,6),('D','DN-SI','DN','DI',2),('R','RETURN',null,null,-2);
        insert into `tabStock Ledger Entry` values ('Sales Invoice','SI','I',-50,-6,0),
        ('Sales Invoice','SI','I',-999,-6,1),('Delivery Note','DN','DI',-100,-12,0),
        ('Sales Invoice','RETURN','R',16.6666666667,2,0);
        ''')
        query=f'''select si.name, {sales_cost_sql()} from `tabSales Invoice` si
            join `tabSales Invoice Item` sii on sii.parent=si.name {sales_cost_join()} where si.docstatus=1'''
        costs=dict(db.execute(query))
        self.assertEqual(costs['SI'],50)  # 12 units cost 100 including FOC; six sold cost 50, not 60.
        self.assertAlmostEqual(costs['DN-SI'],100/6)
        self.assertAlmostEqual(costs['RETURN'],-100/6)
        db.execute("update `tabDelivery Note` set docstatus=2")
        self.assertIsNone(dict(db.execute(query))['DN-SI'])
        db.execute("update `tabDelivery Note` set docstatus=1")
        db.execute("update `tabSales Invoice` set is_return=1 where name='DN-SI'")
        self.assertIsNone(dict(db.execute(query))['DN-SI'])
        db.execute("update `tabStock Ledger Entry` set stock_value_difference=-54 where voucher_no='SI' and is_cancelled=0")
        self.assertEqual(dict(db.execute(query))['SI'],54)
        db.execute("delete from `tabStock Ledger Entry` where voucher_no='SI'")
        self.assertIsNone(dict(db.execute(query))['SI'])
