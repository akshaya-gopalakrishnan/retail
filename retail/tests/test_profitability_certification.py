"""Regression checks for certification gaps; independent of live accounting data."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import frappe
from retail.retail_app.report.profitability import profitability_total
from retail.retail_app.report.van_sales_report_utils import add_total_row


class TestCertification(unittest.TestCase):
    def test_shared_total_preserves_sales_components(self):
        rows = [frappe._dict(gross_sales=120, discount=20, sales_returns=0,
                            net_sales=100, vat=5, cost_amount=70),
                frappe._dict(gross_sales=0, discount=0, sales_returns=40,
                            net_sales=-40, vat=-2, cost_amount=-28)]
        total = profitability_total(rows, 'name')
        self.assertEqual((total.gross_sales, total.discount, total.sales_returns, total.vat), (120,20,40,3))
        self.assertEqual(total.net_sales, total.gross_sales-total.discount-total.sales_returns)
        self.assertEqual((total.gross_profit,total.profit_percent), (18,30))

    def test_van_total_does_not_turn_missing_cost_into_zero(self):
        rows = [frappe._dict(net_sales=100,cost_amount=70,gross_profit=30),
                frappe._dict(net_sales=50,cost_amount=None,gross_profit=None)]
        total = add_total_row(rows,'name',label='Total')[-1]
        self.assertIsNone(total.cost_amount)
        self.assertIsNone(total.gross_profit)
        self.assertIsNone(total.profit_percent)

    def test_missing_movement_invoice_is_not_zero_revenue(self):
        from retail.retail_app.report.margin_by_movement.margin_by_movement import get_sales_amount
        row=frappe._dict(voucher_type='Sales Invoice',voucher_no='MISSING',voucher_detail_no='MISSING-ITEM')
        with patch.object(frappe,'db',SimpleNamespace(get_value=lambda *a,**k: None)):
            self.assertIsNone(get_sales_amount(row,{}))

    def test_recorded_discount_tax_and_foc_components(self):
        from retail.retail_app.report.profitability import invoice_profitability
        doc=frappe._dict(doctype='Sales Invoice',docstatus=1,is_return=0,
            conversion_rate=1,base_net_total=171,items=[
                frappe._dict(name='paid',qty=2,rate=90,discount_amount=10,
                             base_net_amount=171,distributed_discount_amount=9),
                frappe._dict(name='free',qty=1,rate=0,is_free_item=1,
                             discount_amount=100,base_net_amount=0)],
            taxes=[frappe._dict(account_head='VAT',base_tax_amount_after_discount_amount=8.55),
                   frappe._dict(account_head='Shipping',base_tax_amount_after_discount_amount=5)])
        values=invoice_profitability(doc,{'paid':120,'free':10},vat_accounts={'VAT'})
        self.assertEqual((values.gross_sales,values.discount,values.sales_returns,values.net_sales,values.vat),
                         (200,29,0,171,8.55))
        self.assertEqual((values.cost_amount,values.gross_profit),(130,41))
        self.assertAlmostEqual(values.profit_percent,41/171*100)
        values=invoice_profitability(doc,{'paid':120},vat_accounts={'VAT'})
        self.assertIsNone(values.cost_amount)
        self.assertIn('free',values.cost_status)

    def test_purchase_return_is_rejected(self):
        from retail.retail_app.report.profitability import invoice_profitability
        with self.assertRaises(ValueError):
            invoice_profitability(frappe._dict(doctype='Purchase Invoice'),{},vat_accounts=set())

    def test_return_and_cancelled_document(self):
        from retail.retail_app.report.profitability import invoice_profitability
        doc=frappe._dict(doctype='Sales Invoice',docstatus=1,is_return=1,
            base_net_total=-40,items=[frappe._dict(name='r',base_net_amount=-40)],
            taxes=[frappe._dict(account_head='VAT',base_tax_amount_after_discount_amount=-2)])
        result=invoice_profitability(doc,{'r':-28},vat_accounts={'VAT'})
        self.assertEqual((result.gross_sales,result.discount,result.sales_returns,result.net_sales,
                          result.vat,result.cost_amount,result.gross_profit,result.profit_percent),
                         (0,0,40,-40,-2,-28,-12,None))
        doc.docstatus=2
        with self.assertRaises(ValueError):
            invoice_profitability(doc,{'r':-28},vat_accounts={'VAT'})

    def test_inconsistent_tax_rows_are_exposed(self):
        from retail.retail_app.report.profitability import invoice_profitability
        doc=frappe._dict(doctype='Sales Invoice',docstatus=1,base_net_total=10,
            base_total_taxes_and_charges=.5,items=[frappe._dict(name='i',base_net_amount=10)],
            taxes=[frappe._dict(account_head='VAT',base_tax_amount_after_discount_amount=.5)]*2)
        result=invoice_profitability(doc,{'i':7},vat_accounts={'VAT'})
        self.assertEqual(result.vat,1)
        self.assertIn('do not reconcile',result.tax_status)

    def test_unmapped_delivery_revenue_has_reason(self):
        from retail.retail_app.report.margin_by_movement import margin_by_movement as report
        row=frappe._dict(voucher_type='Delivery Note',voucher_no='DN',voucher_detail_no='DNI',
                        movement_type='Sale',stock_value_difference=-70,qty_in=0,qty_out=1)
        with patch.object(report,'get_stock_movements',return_value=[row]), patch.object(frappe, 'get_all', return_value=[]):
            result=report.get_data({})[0]
        self.assertIsNone(result.net_sales)
        self.assertIsNone(result.gross_profit)
        self.assertIn('no verified submitted invoice allocation', result.source_status)

    def test_return_display_and_weighted_aggregation(self):
        from retail.retail_app.report.profitability import aggregate_profitability, report_result
        rows = [frappe._dict(invoice_no='S', item_code='I', is_return=0, net_sales=100,
                            gross_sales=110, discount=10, sales_returns=0, vat=5,
                            cost_amount=70, source_status='Recorded / Posted'),
                frappe._dict(invoice_no='R', item_code='I', is_return=1, net_sales=-40,
                            gross_sales=0, discount=0, sales_returns=40, vat=-2,
                            cost_amount=-28, source_status='Recorded / Posted')]
        grouped = aggregate_profitability(rows, ['invoice_no'])
        self.assertIsNone(grouped[1].profit_percent)
        result = report_result(rows, [dict(fieldname='invoice_no', fieldtype='Data')], ['invoice_no'])
        total = result[1][-1]
        self.assertEqual((total.net_sales, total.cost_amount, total.gross_profit, total.profit_percent), (60,42,18,30))
        self.assertEqual(total.gross_sales-total.discount-total.sales_returns, total.net_sales)

    def test_unknown_item_tax_keeps_trustworthy_invoice_vat(self):
        rows = [frappe._dict(invoice_no='S', voucher_type='Sales Invoice', invoice_item_count=2,
                            invoice_vat=5, vat=None, net_sales=amount, cost_amount=cost)
                for amount,cost in [(60,40),(40,30)]]
        self.assertEqual(profitability_total(rows, 'name').vat, 5)
        self.assertIsNone(profitability_total(rows[:1], 'name').vat)

    def test_unknown_source_status_survives_total(self):
        rows = [frappe._dict(net_sales=20,cost_amount=21,source_status='Posted SLE COGS differs from stock GL')]
        total = profitability_total(rows, 'name')
        self.assertEqual(total.gross_profit,-1)
        self.assertIn('differs from stock GL',total.source_status)

    def test_pos_split_cost_join_does_not_multiply_revenue(self):
        import sqlite3
        from retail.retail_app.report.pos_report_utils import pos_cost_joins
        db=sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript('''
            create table `tabPOS Invoice` (name text, consolidated_invoice text);
            create table `tabPOS Invoice Item` (name text, parent text, base_net_amount real);
            create table `tabSales Invoice` (name text, docstatus int);
            create table `tabSales Invoice Item` (name text,parent text,pos_invoice_item text);
            create table `tabStock Ledger Entry` (voucher_type text,voucher_no text,voucher_detail_no text,is_cancelled int,stock_value_difference real);
            insert into `tabPOS Invoice` values ('POS','SI');
            insert into `tabPOS Invoice Item` values ('PI','POS',100);
            insert into `tabSales Invoice` values ('SI',1);
            insert into `tabSales Invoice Item` values ('SI-I','SI','PI');
            insert into `tabStock Ledger Entry` values ('Sales Invoice','SI','SI-I',0,-50),('Sales Invoice','SI','SI-I',0,-20),('Sales Invoice','SI','SI-I',1,-999);
        ''')
        row=db.execute(f'''select sum(pii.base_net_amount),sum(coalesce(consolidated_cost.cost_amount,direct_cost.cost_amount))
            from `tabPOS Invoice` pi join `tabPOS Invoice Item` pii on pii.parent=pi.name {pos_cost_joins()}''').fetchone()
        self.assertEqual(row,(100,70))
