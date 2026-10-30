import unittest
from unittest.mock import patch
import frappe
from retail.retail_app.report.promotion_performance.promotion_performance import posted_cost, summarize, enrich

MODULE = 'retail.retail_app.report.promotion_performance.promotion_performance'


class TestPromotionPerformance(unittest.TestCase):
    def test_posted_cost_and_return_sign_and_missing(self):
        doc = frappe._dict(doctype='POS Invoice', name='POS-1')
        line = frappe._dict(name='LINE', stock_qty=2)
        with patch.object(frappe, 'get_all', return_value=[frappe._dict(actual_qty=-2, stock_value_difference=-14)]):
            self.assertEqual(posted_cost(doc, line), 14)
        line.stock_qty = -2
        with patch.object(frappe, 'get_all', return_value=[frappe._dict(actual_qty=2, stock_value_difference=14)]):
            self.assertEqual(posted_cost(doc, line), -14)
        with patch.object(frappe, 'get_all', return_value=[]):
            self.assertIsNone(posted_cost(doc, line))

    def test_consolidated_cost_uses_exact_original_item(self):
        doc = frappe._dict(doctype='POS Invoice', name='POS-1', consolidated_invoice='SI-1')
        line = frappe._dict(name='LINE', stock_qty=2)
        with patch.object(frappe, 'get_all', side_effect=[
            [frappe._dict(parent='SI-1', name='SI-LINE')],
            [frappe._dict(actual_qty=-2, stock_value_difference=-10)]]) as query:
            self.assertEqual(posted_cost(doc, line), 10)
        self.assertEqual(query.call_args_list[0].kwargs['filters']['pos_invoice_item'], 'LINE')
        self.assertEqual(query.call_args_list[1].kwargs['filters']['voucher_detail_no'], 'SI-LINE')

    def row(self, **values):
        return frappe._dict(dict(promotion_type='Promo Price', promotion='OFFER', company='C',
            company_currency='AED', invoice='POS-1', item_row=1, item_code='I', uom='Nos',
            customer='CUSTOMER', is_return=0, base_sales=20, base_discount=5,
            cost=12, gross_profit=8, profit_status='Complete', **values))

    def test_missing_cost_blanks_group_profit_and_deduplicates_customers(self):
        a = self.row()
        b = self.row(); b.update(invoice='POS-2', cost=None, gross_profit=None, profit_status='Profit Incomplete')
        groups, _ = summarize([a,b])
        group = next(iter(groups.values()))
        self.assertEqual((group.sales_bills, group.customers, group.base_sales), (2,1,40))
        self.assertIsNone(group.gross_profit)
        self.assertIsNone(group.cost)

    def test_returns_reverse_profit_without_subtracting_discount_twice(self):
        a = self.row()
        b = self.row(); b.update(invoice='RET', is_return=1, base_sales=-10, base_discount=-2.5, cost=-6, gross_profit=-4)
        group = next(iter(summarize([a,b])[0].values()))
        self.assertEqual((group.base_sales, group.cost, group.gross_profit), (10,6,4))
        self.assertEqual(group.margin,40)
        self.assertEqual(group.return_bills,1)

    def test_overlapping_promotions_do_not_claim_profit(self):
        class Doc(frappe._dict):
            @property
            def items(self):
                return [frappe._dict(idx=1, name='LINE', qty=2, base_net_amount=20)]
        doc = Doc(customer='CUST', company='C', conversion_rate=1)
        rows = [self.row(), self.row()]
        for row in rows:
            row.update(status='Schedule Valid', quantity=2, sales_amount=20)
        rows[1].promotion='SECOND'
        with patch.object(frappe, 'get_doc', return_value=doc), \
             patch.object(frappe, 'get_cached_value', return_value='AED'), \
             patch(MODULE+'.posted_cost') as cost:
            result=enrich(rows)
        cost.assert_not_called()
        self.assertTrue(all(r.gross_profit is None for r in result))
