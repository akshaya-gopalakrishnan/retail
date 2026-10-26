"""Rollback-only proof of promotion additions to existing POS payments."""
import copy
import json
import unittest
from retail import pos_offline_promotions as offline
from retail.pos_settlements import cash_payments, settlements
from unittest.mock import patch
import frappe
from frappe.utils import add_days, nowdate

def run_integration():
    if frappe.local.site != 'retail-test.localhost': raise RuntimeError('Local rollback-only suite')
    from retail.api import pos_sync as api, gift_vouchers as vouchers
    from retail import voucher_cards
    frappe.set_user('Administrator'); frappe.flags.in_test = True
    token = frappe.generate_hash(length=12)
    base = json.loads(frappe.db.get_value('POS Sync Log', 'PSL-2644', 'request_json')); base = base.get('payload', base)
    counter = api._counter(base['branch'], base['counter_code']); company = frappe.get_doc('Company', counter.company)
    cash = frappe.db.get_value('Mode of Payment', {'type': 'Cash'}, 'name')
    card = frappe.db.get_value('Mode of Payment', {'type': 'Bank'}, 'name')
    program = frappe.get_doc(dict(doctype='Loyalty Program', loyalty_program_name='Mixed '+token,
        loyalty_program_type='Single Tier Program', from_date=add_days(nowdate(), -365),
        conversion_factor=1, expiry_duration=365, company=company.name,
        expense_account=company.default_expense_account, cost_center=company.cost_center,
        collection_rules=[dict(tier_name='Base', min_spent=0, collection_factor=1)])).insert()
    customer = frappe.get_doc(dict(doctype='Customer', customer_name='Mixed '+token,
        customer_type='Individual', customer_group=frappe.db.get_value('Customer Group', {'is_group':0}, 'name'), territory='All Territories', loyalty_program=program.name)).insert()
    base.update(customer=customer.name, posting_date=nowdate(), business_date=nowdate(), vat_amount=0, discount_amount=0, update_stock=0)
    for key in ('rounded_total','rounding_adjustment','voucher_redemption','issued_vouchers'): base.pop(key, None)
    source_item = copy.deepcopy(base['items'][0]); results = []
    def payload(suffix, total, **changes):
        item = {**source_item, 'qty': 1, 'rate': total, 'rate_includes_vat': 0, 'amount': total,
            'net_amount': total, 'vat_amount': 0, 'vat_rate': 0, 'discount_amount': 0}
        return frappe._dict({**copy.deepcopy(base), 'external_pos_reference': 'mixed-'+token+'-'+suffix,
            'items': [item], 'grand_total': total, 'net_total': total,
            'payments': [dict(mode_of_payment=cash, amount=total)], **changes})
    def posted(data):
        response = api.create_pos_invoice(data); assert response.get('accepted'), response
        tx = frappe.get_doc('POS Accepted Transaction', response['accepted_transaction'])
        assert tx.sales_invoice, (tx.status, tx.exception_reason)
        assert json.loads(tx.payload_json) == dict(data)
        return response, tx, frappe.get_doc('POS Invoice', tx.pos_invoice), frappe.get_doc('Sales Invoice', tx.sales_invoice)
    with patch.object(frappe, 'enqueue'), patch.object(frappe.db, 'commit'), patch.object(frappe, 'publish_realtime'), patch.object(vouchers, 'redeem_gift_voucher', side_effect=AssertionError('Offline invoice must not call online approval')):
        seed_data = payload('seed',1000); _, _, seed, seed_si = posted(seed_data)
        ret = payload('return',50,payments=[],original_external_pos_reference=seed_data.external_pos_reference,
            return_settlement_type='Reusable Customer Credit')
        res = api.create_pos_return_invoice(ret); credit = frappe.get_doc('POS Accepted Transaction',res['accepted_transaction'])
        assert credit.sales_invoice, (credit.status, credit.exception_reason)
        if not frappe.db.exists('Loyalty Point Entry', {'customer':customer.name,'loyalty_points':['>',0]}):
            frappe.get_doc(dict(doctype='Loyalty Point Entry',company=company.name,customer=customer.name,
                loyalty_program=program.name,loyalty_program_tier='Base',loyalty_points=1000,purchase_amount=1000,
                posting_date=nowdate(),expiry_date=add_days(nowdate(),365),invoice_type='Sales Invoice',invoice=seed_si.name)).insert()
        promo=frappe.get_doc(dict(doctype='Gift Voucher Ledger',voucher_code='PGV-'+frappe.generate_hash(length=32).upper(),
            company=company.name,currency=company.default_currency,customer=customer.name,voucher_amount=100,balance_amount=100,
            status='Unused',issued_date=nowdate(),expiry_date=add_days(nowdate(),30))).insert()
        batch=frappe.get_doc(dict(doctype='Voucher Card Batch',title='Mixed '+token,company=company.name,
            currency=company.default_currency,voucher_amount=100,card_count=1,valid_from=nowdate(),
            expiry_date=add_days(nowdate(),30),all_products=1,activate_all_cards=1,print_from=1,print_to=1)).insert()
        batch.db_set('generation_status','Queued'); voucher_cards.generate_worker(batch.name)
        card_code=frappe.db.get_value('Gift Voucher Ledger',{'voucher_card_batch':batch.name},'name')
        data=payload('all',500,
            payments=[dict(mode_of_payment=cash,amount=100),dict(mode_of_payment=card,amount=50),
                dict(mode_of_payment='Loyalty',amount=50,reference_no=program.name,points=50),
                dict(mode_of_payment='Promotion Voucher',amount=50,reference_no=promo.name),
                dict(mode_of_payment='Voucher Card',amount=50,reference_no=card_code)],
            credit_sale_amount=150,
            credit_note_redemptions=[dict(credit_note_external_reference=ret.external_pos_reference,amount=50)])
        response,tx,doc,invoice=posted(data)
        assert (invoice.grand_total,invoice.paid_amount,invoice.loyalty_amount,invoice.outstanding_amount)==(500,300,0,150), invoice.as_dict()
        assert doc.outstanding_amount==200, doc.outstanding_amount
        assert doc.custom_gift_voucher_amount==100, doc.custom_gift_voucher_amount
        gl = frappe.get_all('GL Entry', filters={'voucher_type':'Sales Invoice','voucher_no':invoice.name,'is_cancelled':0},
            fields=['account','debit','credit'])
        assert round(sum(r.debit-r.credit for r in gl),2)==0, gl
        assert any(r.debit==50 and r.account==program.expense_account for r in gl), gl
        def debited():
            return sum(r.loyalty_points for r in frappe.get_all('Loyalty Point Entry',filters={
                'invoice_type':'POS Invoice','invoice':doc.name,'redeem_against':['is','set']},fields=['loyalty_points']))
        assert debited()==-50, debited()
        assert not frappe.db.exists('Loyalty Point Entry',{'invoice_type':'Sales Invoice','invoice':invoice.name})
        for code in (promo.name,card_code):
            assert frappe.db.get_value('Gift Voucher Ledger',code,'balance_amount')==50
        assert api.create_pos_invoice(data).get('duplicate')
        assert frappe.db.count('POS Invoice',{'external_pos_reference':data.external_pos_reference})==1
        assert debited()==-50
        results.append('Seven portions reconcile: GL receivable 150, loyalty debit once, both vouchers debited offline, exact retry unchanged')
        _,_,ldoc,lsi=posted(payload('points-only',50,payments=[
            dict(mode_of_payment='Loyalty',amount=50,reference_no=program.name,points=50)],credit_sale_amount=0))
        assert lsi.outstanding_amount==0 and ldoc.outstanding_amount==0
        results.append('Loyalty-only payment row posts without cash/card or online calls')
        from retail import loyalty
        before = sum(n for _,n in loyalty.available_buckets(loyalty.ledger_entries(customer.name,program.name,company.name),nowdate()))
        first = max(1,before//2)
        second = before-first+10
        _,_,multi_doc,_ = posted(payload('two-loyalty-rows',first+second,payments=[
            dict(mode_of_payment='Loyalty',amount=first,reference_no=program.name,points=first),
            dict(mode_of_payment='Loyalty',amount=second,reference_no=program.name,points=second)],credit_sale_amount=0))
        comparisons=frappe.get_all('External POS Rate Audit',filters={'pos_invoice':multi_doc.name,
            'reason':['like','%Requested points exceed%']},fields=['erp_calculation_json'])
        assert any(json.loads(r.erp_calculation_json).get('available_points')==before-first for r in comparisons),comparisons
        results.append('Multiple loyalty rows consume sequential balances and audit the second-row shortage')
        frappe.db.set_value('Gift Voucher Ledger',card_code,'expiry_date',add_days(nowdate(),-1))
        _,_,expired_doc,expired_si=posted(payload('expired-card',10,payments=[
            dict(mode_of_payment='Voucher Card',amount=10,reference_no=card_code)],credit_sale_amount=0))
        assert expired_si.outstanding_amount==0
        assert frappe.db.get_value('Gift Voucher Ledger',card_code,'balance_amount')==40
        assert frappe.db.exists('External POS Rate Audit',{'pos_invoice':expired_doc.name,'reason':['like','%Expired%']})
        results.append('Card expiry after download is audit-only; the original offline redemption still posts')
        mismatch=payload('mismatch',200,payments=[
            dict(mode_of_payment='Loyalty',amount=100,reference_no=program.name,points=2000),
            dict(mode_of_payment='Promotion Voucher',amount=100,reference_no=promo.name)],credit_sale_amount=0)
        _,mtx,mdoc,msi=posted(mismatch)
        assert msi.outstanding_amount==0
        assert frappe.db.get_value('Gift Voucher Ledger',promo.name,'balance_amount')==-50
        audits=frappe.get_all('External POS Rate Audit',filters={'pos_invoice':mdoc.name},fields=['reason'])
        assert any('exceeds the ERP balance' in r.reason for r in audits),audits
        assert any('points exceed' in r.reason for r in audits),audits
        assert sum(r.loyalty_points for r in frappe.get_all('Loyalty Point Entry',
            filters={'invoice_type':'POS Invoice','invoice':mdoc.name},fields=['loyalty_points']) if r.loyalty_points<0)==-2000
        assert api.create_pos_invoice(mismatch).get('duplicate')
        assert frappe.db.get_value('Gift Voucher Ledger',promo.name,'balance_amount')==-50
        results.append('Insufficient points/voucher balance and changed conversion are audit-only; exact full debit and zero debt retained')
        missing=payload('missing',50,payments=[dict(mode_of_payment='Voucher Card',amount=50,reference_no='MISSING-'+token)],credit_sale_amount=0)
        _,_,missingdoc,missingsi=posted(missing)
        assert missingsi.outstanding_amount==0
        assert frappe.db.exists('External POS Rate Audit',{'pos_invoice':missingdoc.name,'reason':['like','%source was not found%']})
        results.append('Missing source preserves financial settlement and audit evidence without inventing a source record')
        for suffix, value, variance in [('short-total',20,30),('over-total',80,-30)]:
            mismatched=payload(suffix,50,payments=[dict(mode_of_payment='Voucher Card',amount=value,
                reference_no='MISSING-'+token)],credit_sale_amount=0)
            _,_,vd,vi=posted(mismatched)
            assert vi.outstanding_amount==0 and vi.grand_total==50
            assert next(r.amount for r in vd.payments if r.mode_of_payment=='Promotion Variance')==variance
            assert frappe.db.exists('External POS Rate Audit',{'pos_invoice':vd.name,
                'reason':['like','%Payment portions differ%']})
        results.append('Short and excess promotion totals use explicit audited variance, preserving the original sale and zero intended customer credit')
    return results




class TestOfflinePromotionPayments(unittest.TestCase):
    def test_additive_fields_and_existing_credit_fields(self):
        payload = dict(grand_total=500, payments=[dict(mode_of_payment='Cash',amount=100),
            dict(mode_of_payment='Card',amount=50),
            dict(mode_of_payment='Loyalty',amount=50,reference_no='LP',points=50),
            dict(mode_of_payment='Promotion Voucher',amount=50,reference_no='PROMO'),
            dict(mode_of_payment='Voucher Card',amount=50,reference_no='CARD')],
            credit_sale_amount=150,
            credit_note_redemptions=[dict(credit_note_external_reference='original-return',amount=50)])
        original = copy.deepcopy(payload)
        self.assertEqual([row['mode_of_payment'] for row in cash_payments(payload)],['Cash','Card'])
        self.assertEqual([(row['settlement_type'],row['requested_amount']) for row in settlements(payload)],
            [('Credit Note Redeemed',50),('Credit Sale',150)])
        self.assertEqual(offline.total_difference(payload),0)
        self.assertEqual(payload,original)
        self.assertNotIn('payment_format',payload)

    def test_original_cash_card_and_credit_logic(self):
        payload=dict(grand_total=200,payments=[dict(mode_of_payment='Cash',amount=50)],credit_sale_amount=150)
        self.assertEqual(cash_payments(payload),payload['payments'])
        self.assertEqual(settlements(payload),[dict(settlement_type='Credit Sale',requested_amount=150)])
        self.assertEqual(offline.rows(payload),[])

    def test_total_difference_is_explicit_and_preserves_customer_credit(self):
        for tender, difference in [(20,30),(80,-30)]:
            payload=dict(grand_total=50,payments=[dict(mode_of_payment='Voucher Card',amount=tender,
                reference_no='CODE')],credit_sale_amount=0)
            self.assertEqual(offline.total_difference(payload),difference)
            self.assertEqual(payload['credit_sale_amount'],0)

    def test_overdraft_is_offset_against_later_earnings(self):
        from retail.loyalty import available_buckets
        entries=[frappe._dict(name='old',invoice_type='Sales Invoice',invoice='old-sale',loyalty_points=100,
                    redeem_against=None,posting_date='2026-01-01',expiry_date='2099-12-31'),
            frappe._dict(name='debit',invoice_type='POS Invoice',invoice='offline-sale',loyalty_points=-150,
                    redeem_against='old',posting_date='2026-01-02',expiry_date='2099-12-31'),
            frappe._dict(name='new',invoice_type='Sales Invoice',invoice='new-sale',loyalty_points=100,
                    redeem_against=None,posting_date='2026-01-03',expiry_date='2099-12-31')]
        self.assertEqual(sum(value for _,value in available_buckets(entries,'2026-10-23')),50)

    def test_unlinked_offline_debit_is_counted(self):
        from retail.loyalty import available_buckets
        from retail.promotions.pos_download import _loyalty_point_totals
        entries=[frappe._dict(name='debit',invoice_type='POS Invoice',invoice='offline-sale',loyalty_points=-50,
                    redeem_against=None,posting_date='2026-01-01',expiry_date='2099-12-31'),
            frappe._dict(name='new',invoice_type='Sales Invoice',invoice='new-sale',loyalty_points=100,
                    redeem_against=None,posting_date='2026-01-02',expiry_date='2099-12-31')]
        self.assertEqual(sum(value for _,value in available_buckets(entries,'2026-10-23')),50)
        self.assertEqual(_loyalty_point_totals(entries,'2026-10-23')['used_points'],50)

    def test_offline_accounting_and_audit(self):
        try:
            self.assertGreaterEqual(len(run_integration()),5)
        finally:
            frappe.db.rollback()
