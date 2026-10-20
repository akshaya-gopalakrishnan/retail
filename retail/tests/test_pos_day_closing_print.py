import unittest
from retail.pos_day_closing_print import aggregate

class TestDayClosingPrint(unittest.TestCase):
    def test_saved_totals_change_refunds_and_external_collections(self):
        sale = dict(net_total=100, grand_total=105, total_taxes_and_charges=5, change_amount=15,
            account_for_change_amount='Cash', pos_counter='C1', pos_cashier_shift='S1',
            payments=[dict(mode_of_payment='Cash',account='Cash',amount=120)],
            items=[dict(item_code='A',item_group='Food',net_amount=100)],
            taxes=[dict(description='VAT',charge_type='On Net Total',item_wise_tax_detail='{"A":[5,10]}')], conversion_rate=2)
        returned = dict(is_return=1,net_total=-10,grand_total=-10,pos_counter='C1',pos_cashier_shift='S1',
            payments=[dict(mode_of_payment='Cash',account='Cash',amount=-10)],items=[dict(item_code='A',item_group='Food',net_amount=-10)])
        payments=[dict(payment_type='Receive',received_amount=20,mode_of_payment='Cash',pos_counter='C1',pos_cashier_shift='S1')]
        closing=dict(total_invoice_count=2,total_sales=95,payment_totals='{"Cash":115}',pos_settlement_totals='{"credit_sales":7}')
        result=aggregate([sale,returned],payments,closing)
        self.assertEqual(result['collection_total'],115)
        self.assertEqual(result['counter_collections'],{'C1':115})
        self.assertEqual(result['categories'][0]['amount'],90)
        self.assertEqual(result['sales']['item_refund'],-10)
        self.assertEqual(result['taxes'][0]['amount'],5)
        self.assertEqual(result['settlements']['credit_sales'],7)
        self.assertEqual(result['warnings'],[])

    def test_drift_warns_and_preserves_saved_snapshot(self):
        result=aggregate([],[],dict(total_sales=100,total_invoice_count=1,payment_totals='{"Card":100}'))
        self.assertEqual(result['modes'],{'Card':100})
        self.assertEqual(result['collection_total'],100)
        self.assertEqual(len(result['warnings']),2)

    def test_no_snapshot_does_not_invent_settlements(self):
        result=aggregate([],[],dict(total_sales=0,total_invoice_count=0))
        self.assertEqual(result['settlements'],{})
        self.assertTrue(result['warnings'])
