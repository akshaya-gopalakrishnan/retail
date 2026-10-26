"""Mixed-settlement contract and rollback-only local accounting checks."""
import copy
import json
import unittest
from unittest.mock import patch
import frappe
from frappe.utils import add_days, nowdate
from retail import pos_mixed_payments as mixed
from retail.pos_settlements import settlements

class TestMixedPayments(unittest.TestCase):
    def setUp(self):
        self.payload = dict(bill_total_before_vouchers=500, grand_total=400,
            payments=[dict(mode='Cash', amount=100), dict(mode='Card', amount=50)],
            loyalty_redemption=dict(loyalty_program='LP', points=50, amount=50),
            voucher_redemptions=[dict(voucher_code='PROMO', amount=50, redemption_reference='approval1'),
                dict(voucher_code='CARD', amount=50, redemption_reference='approval2')],
            credit_note_redemptions=[dict(credit_note_external_reference='return-ref', amount=50)], credit_sale_amount=150)
        p = patch.object(frappe, 'throw', side_effect=frappe.ValidationError); p.start(); self.addCleanup(p.stop)
    def test_all_parts_reconcile_without_mutation(self):
        before = copy.deepcopy(self.payload)
        self.assertEqual([(r['settlement_type'], r['requested_amount']) for r in settlements(self.payload)],
            [('Credit Note Redeemed', 50), ('Credit Sale', 150)])
        self.assertEqual(before, self.payload)
    def test_loyalty_only(self):
        self.assertEqual(settlements(dict(grand_total=50, payments=[], credit_sale_amount=0,
            loyalty_redemption=dict(loyalty_program='LP', points=50, amount=50))), [])
    def test_legacy_single_voucher(self):
        self.assertEqual(settlements(dict(grand_total=50, payments=[dict(mode='Cash', amount=50)],
            voucher_redemption=dict(voucher_code='OLD', amount=50, redemption_reference='old'))), [])
    def test_invalid_breakdowns(self):
        for changes in [dict(credit_sale_amount=200), dict(grand_total=500),
                dict(loyalty_redemption=dict(loyalty_program='LP', points=1.5, amount=50)),
                dict(loyalty_redemption=dict(loyalty_program='LP', points=50, amount=-50)),
                dict(voucher_redemptions={}), dict(voucher_redemption=dict(voucher_code='OLD')),
                dict(voucher_redemptions=[self.payload['voucher_redemptions'][0]]*2)]:
            with self.subTest(changes=changes), self.assertRaises(frappe.ValidationError):
                settlements({**self.payload, **changes})
    def test_return_rejects_redemptions(self):
        with self.assertRaises(frappe.ValidationError): settlements(self.payload, True)


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
    with patch.object(frappe, 'enqueue'), patch.object(frappe.db, 'commit'), patch.object(frappe, 'publish_realtime'):
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
        data=payload('all',400,bill_total_before_vouchers=500,
            payments=[dict(mode_of_payment=cash,amount=100),dict(mode_of_payment=card,amount=50)],
            loyalty_redemption=dict(loyalty_program=program.name,points=50,amount=50),credit_sale_amount=150,
            credit_note_redemptions=[dict(credit_note_external_reference=ret.external_pos_reference,amount=50)],voucher_redemptions=[])
        for i,code in enumerate((promo.name,card_code)):
            approval=vouchers.redeem_gift_voucher(dict(branch=base['branch'],counter_code=base['counter_code'],
                external_pos_reference=data.external_pos_reference,redemption_reference='mixed-approve-'+token+'-'+str(i),
                voucher_code=code,amount=50,bill_total=500,items=data['items']))
            assert approval['approved'], approval
            data.voucher_redemptions.append(dict(voucher_code=code,amount=50,redemption_reference=approval['redemption_reference']))
        response,tx,doc,invoice=posted(data)
        assert (invoice.grand_total,invoice.paid_amount,invoice.loyalty_amount,invoice.outstanding_amount)==(400,200,50,150), invoice.as_dict()
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
        for row in data.voucher_redemptions:
            assert vouchers.pos_operations.find('Voucher Redemption',row['redemption_reference']).linked_invoice==doc.name
            assert frappe.db.get_value('Gift Voucher Ledger',row['voucher_code'],'balance_amount')==50
        assert api.create_pos_invoice(data).get('duplicate')
        assert frappe.db.count('POS Invoice',{'external_pos_reference':data.external_pos_reference})==1
        assert debited()==-50
        results.append('Seven portions reconcile: GL receivable 150, loyalty debit once, both vouchers bound, exact retry unchanged')
        _,_,ldoc,lsi=posted(payload('points-only',50,payments=[],credit_sale_amount=0,
            loyalty_redemption=dict(loyalty_program=program.name,points=50,amount=50)))
        assert lsi.outstanding_amount==0 and ldoc.outstanding_amount==0
        results.append('Loyalty-only sale has no tender and zero receivable')
        bad=payload('bad-approval',50,bill_total_before_vouchers=100,
            voucher_redemptions=[dict(voucher_code=promo.name,amount=50,redemption_reference='missing-'+token)])
        response=api.create_pos_invoice(bad); tx=frappe.get_doc('POS Accepted Transaction',response['accepted_transaction'])
        assert not tx.pos_invoice and tx.status=='Reconciliation Exception',tx.status
        results.append('Missing voucher approval retains immutable acceptance without posting a false settled invoice')
        vouchers.redeem_gift_voucher(dict(branch=base['branch'],counter_code=base['counter_code'],
            external_pos_reference=bad.external_pos_reference,redemption_reference='missing-'+token,
            voucher_code=promo.name,amount=50))
        from retail import pos_settlements
        with pos_settlements.recovery_context():
            pos_settlements.post(tx, lambda: api.create_pos_invoice(bad))
        tx.reload()
        assert tx.sales_invoice and tx.status=='Reconciled', (tx.status,tx.exception_reason)
        results.append('Delayed voucher approval recovers the same accepted sale and binds without a second debit')
        invalid = payload('wrong-loyalty-value',50,payments=[],credit_sale_amount=0,
            loyalty_redemption=dict(loyalty_program=program.name,points=5,amount=50))
        res = api.create_pos_invoice(invalid)
        failed = frappe.get_doc('POS Accepted Transaction',res['accepted_transaction'])
        assert not failed.pos_invoice and failed.status=='Reconciliation Exception'
        assert 'conversion factor' in failed.exception_reason
        results.append('Wrong loyalty money value is retained for reconciliation without spending points')
        returned = payload('loyalty-return',10,payments=[],return_settlement_type='Reusable Customer Credit',
            original_external_pos_reference=data.external_pos_reference)
        res = api.create_pos_return_invoice(returned)
        failed = frappe.get_doc('POS Accepted Transaction',res['accepted_transaction'])
        assert not failed.pos_invoice and 'loyalty allocation' in failed.exception_reason
        assert debited()==-50
        results.append('Loyalty-sale return retained for review without deleting original debit or over-refunding')
    return results
