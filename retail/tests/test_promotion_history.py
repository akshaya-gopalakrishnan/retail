import json
import unittest
from unittest.mock import patch
import frappe
from retail.promotions.history import check_schedule, audit_application, capture, execute_summary, resolve_item_row, applications_for
from retail.promotions.api_payload import promotion_payload


class TestPromotionHistory(unittest.TestCase):
    def nested_item(self, **overrides):
        return dict(dict(item_code='I-48', barcode='BC0048800', uom='Nos', qty=1,
            rate=9, amount=9, net_amount=8.57, vat_rate=5, rate_includes_vat=1,
            discount_amount=0, applied_promotions=[dict(promotion_type='Promo Price',
                promotion='Chicken masala', promotion_version='VERSION', promotion_discount_amount=1)]), **overrides)

    def test_nested_terminal_evidence_and_header_precedence(self):
        item = self.nested_item()
        payload = dict(items=[item])
        row = applications_for(payload)[0]
        self.assertEqual((row['item_row'], row['item_code'], row['quantity']), (1, 'I-48', 1))
        self.assertEqual((row['discount_amount'], row['sales_amount']), (0.95, 8.57))
        self.assertNotIn('item_row', item['applied_promotions'][0])
        self.assertEqual(item['discount_amount'], 0)
        self.assertEqual(applications_for(dict(payload, applied_promotions=[])), [])
        self.assertEqual(applications_for(dict(items=[self.nested_item(rate_includes_vat=0)]))[0]['discount_amount'], 1)
        item['applied_promotions'][0]['discount_amount'] = 0.75
        self.assertEqual(applications_for(payload)[0]['discount_amount'], 0.75)

    def test_nested_capture_return_and_missing_discount(self):
        class Doc(frappe._dict):
            def set(self, key, value): self[key] = value
        item = self.nested_item(qty=-2)
        doc = Doc(is_return=1)
        with patch('retail.pos_completed_sale.payload_for', return_value=dict(items=[item])):
            capture(doc)
        row = json.loads(doc.custom_pos_promotion_history)['applications'][0]
        self.assertEqual((row['quantity'], row['discount_amount'], row['sales_amount']), (-2, -0.95, -8.57))
        del item['applied_promotions'][0]['promotion_discount_amount']
        with patch('retail.pos_completed_sale.payload_for', return_value=dict(items=[item])):
            capture(doc)
        self.assertIn('missing', json.loads(doc.custom_pos_promotion_history)['applications'][0]['reason'])

    def test_nested_discount_report_does_not_change_financial_discounts(self):
        from retail.retail_app.report.pos_report_utils import completed_discount_rows
        rows = [frappe._dict(invoice_no='BILL', item_index=1, qty=1,
            completed_payload=json.dumps(dict(items=[self.nested_item()])), rate=9)]
        row = completed_discount_rows(rows)[0]
        self.assertEqual(row.promotion_discount_amount, 0.95)
        self.assertEqual(row.discount_amount, 0)
        self.assertEqual(row.line_discount_amount, 0)

    def test_nested_exchange_preserves_parent_attribution(self):
        from retail.pos_exchange import split
        payload = dict(external_pos_reference='NESTED-EXCHANGE', items=[self.nested_item(qty=-1, net_amount=-8.57, amount=-9, vat_amount=-0.43),
                              self.nested_item(qty=2, net_amount=17.14, amount=18, vat_amount=0.86)],
                       payments=[dict(mode_of_payment='Cash', amount=9)])
        sales, returns, _, _, _ = split(payload)
        self.assertEqual(applications_for(dict(items=sales))[0]['quantity'], 2)
        self.assertEqual(applications_for(dict(items=returns[None]))[0]['quantity'], -1)

    def test_nested_invalid_discount_remains_reviewable(self):
        class Doc(frappe._dict):
            def set(self, key, value): self[key] = value
        for value in ('bad', float('inf'), None):
            item = self.nested_item()
            item['applied_promotions'][0]['promotion_discount_amount'] = value
            doc = Doc()
            with patch('retail.pos_completed_sale.payload_for', return_value=dict(items=[item])):
                capture(doc)
            row = json.loads(doc.custom_pos_promotion_history)['applications'][0]
            self.assertEqual(row['status'], 'Review Required')
            self.assertEqual(row['discount_amount'], 0)

    def test_return_links_saved_nested_original_without_saving(self):
        class Doc(frappe._dict):
            def set(self, key, value): self[key] = value
        original = Doc(is_return=0)
        application = dict(promotion_type='Promo Price', promotion='Chicken masala', original_item_row=1)
        with patch.object(frappe.db, 'get_value', return_value=None), \
             patch.object(frappe, 'get_doc', return_value=original), \
             patch('retail.pos_completed_sale.payload_for', return_value=dict(items=[self.nested_item()])):
            row = audit_application(application, {}, Doc(is_return=1, return_against='ORIGINAL'))
        self.assertEqual(row['status'], 'Return Linked')

    def test_item_code_matching_and_ambiguity(self):
        items = [dict(item_code='OTHER'), dict(item_code='ITEM', barcode='123', uom='Nos'),
                 dict(item_code='ITEM', barcode='456', uom='Box')]
        self.assertEqual(resolve_item_row(dict(item_code='OTHER'), items), (1, None))
        self.assertIn('Ambiguous', resolve_item_row(dict(item_code='ITEM'), items)[1])
        for selector in (dict(barcode='456'), dict(uom='Box')):
            self.assertEqual(resolve_item_row(dict(item_code='ITEM', **selector), items), (3, None))
        self.assertIsNotNone(resolve_item_row(dict(item_code='MISSING'), items)[1])
        self.assertIsNotNone(resolve_item_row(dict(item_row=1, item_code='ITEM'), items)[1])
        for value in (0, 4, 1.5, True, 'bad', float('inf')):
            self.assertIsNotNone(resolve_item_row(dict(item_row=value), items)[1])

    def test_item_code_capture_and_excluded_ambiguous_totals(self):
        class Doc(frappe._dict):
            def set(self, key, value): self[key] = value
        application = dict(promotion_type='Promo Price', promotion='OFFER', item_code='ITEM',
                           quantity=1, discount_amount=2, sales_amount=8)
        for items, expected in (([dict(item_code='OTHER'), dict(item_code='ITEM')], 2),
                                ([dict(item_code='ITEM'), dict(item_code='ITEM')], 0)):
            doc = Doc(is_return=0)
            with patch('retail.pos_completed_sale.payload_for', return_value=dict(items=items, applied_promotions=[application])):
                capture(doc)
            row = json.loads(doc.custom_pos_promotion_history)['applications'][0]
            self.assertEqual(row['item_row'], expected)
            self.assertEqual(row['item_code'], 'ITEM')
            if not expected:
                self.assertTrue(row['excluded_from_totals'])
                with patch('retail.promotions.history.report_rows', return_value=[dict(row, invoice='BILL')]):
                    self.assertEqual(execute_summary({})[1][0]['sales_amount'], 0)

    def test_exchange_item_code_resolves_before_split(self):
        from retail.promotions.history import exchange_applications
        payload = dict(items=[dict(item_code='RETURN'), dict(item_code='SALE')],
                       applied_promotions=[dict(item_code='SALE')])
        self.assertEqual(exchange_applications(payload, [dict(_promotion_source_row=2)]),
                         [dict(item_code='SALE', item_row=1)])
        self.assertEqual(exchange_applications(payload, [dict(_promotion_source_row=1)]), [])
        payload['items'] = [dict(item_code='SALE'), dict(item_code='SALE')]
        result = exchange_applications(payload, [dict(_promotion_source_row=2)])
        self.assertEqual(result[0]['item_row'], 0)
        self.assertIsNotNone(resolve_item_row(result[0], [dict(item_code='SALE')])[1])

    def rule(self):
        return dict(doctype='Promo Price', disabled=0, active_from='2026-10-17', active_to='2026-10-17', active_from_time='09:00:00', active_to_time='12:00:00')

    def test_original_sale_time_inclusive_expiry(self):
        for time in ('09:00:00','11:00:00','12:00:00'):
            self.assertEqual(check_schedule(self.rule(),dict(posting_date='2026-10-17',posting_time=time))[0],'Schedule Valid')
        for date,time in (('2026-10-18','10:00:00'),('2026-10-17','12:00:01')):
            self.assertEqual(check_schedule(self.rule(),dict(posting_date=date,posting_time=time))[0],'Review Required')

    def test_disabled_and_missing_time(self):
        rule=self.rule(); rule['disabled']=1
        self.assertIn('disabled',check_schedule(rule,dict(posting_date='2026-10-17',posting_time='10:00:00'))[1])
        self.assertEqual(check_schedule(self.rule(),dict(posting_date='2026-10-17'))[0],'Review Required')

    def test_overnight_midnight(self):
        rule=self.rule(); rule.update(active_from_time='22:00:00',active_to_time='02:00:00')
        for time in ('23:00:00','00:00:00','02:00:00'):
            self.assertEqual(check_schedule(rule,dict(posting_date='2026-10-17',posting_time=time))[0],'Schedule Valid')
        self.assertEqual(check_schedule(rule,dict(posting_date='2026-10-17',posting_time='12:00:00'))[0],'Review Required')

    def test_historical_version_and_stale_cache(self):
        app=dict(promotion_type='Promo Price',promotion='OFFER',promotion_version='OLD')
        doc=frappe._dict(is_return=0,company='COMPANY',set_warehouse='WH')
        payload=dict(posting_date='2026-10-17',posting_time='10:00:00')
        with patch.object(frappe,'get_all',return_value=[frappe._dict(name='OLD',rule_json=json.dumps(self.rule()))]) as query:
            self.assertEqual(audit_application(app,payload,doc)['status'],'Schedule Valid')
        self.assertTrue(any('effective_from' in call.kwargs.get('filters', {}) for call in query.call_args_list))
        with patch.object(frappe,'get_all',return_value=[frappe._dict(name='NEW',rule_json=json.dumps(self.rule()))]):
            self.assertEqual(audit_application(app,payload,doc)['status'],'Review Required')
        with patch.object(frappe,'get_all',return_value=[]):
            self.assertEqual(audit_application(app,payload,doc)['status'],'Review Required')

    def test_return_signed_amounts_and_packing(self):
        class Doc(frappe._dict):
            def set(self,key,value): self[key]=value
        doc=Doc(is_return=1,return_against=None)
        payload=dict(applied_promotions=[dict(promotion_type='Promo Price',promotion='OFFER',item_row=1,quantity=2,discount_amount=1,sales_amount=9,free_quantity=0)],items=[dict(item_code='ITEM',uom='Box',barcode='123')])
        with patch('retail.pos_completed_sale.payload_for',return_value=payload): capture(doc)
        row=json.loads(doc.custom_pos_promotion_history)['applications'][0]
        self.assertEqual(row['quantity'],-2)
        self.assertEqual(row['discount_amount'],-1)
        self.assertEqual(row['uom'],'Box')
        self.assertEqual(row['status'],'Review Required')

    def test_summary_distinct_receipts_separate_currency(self):
        rows=[dict(promotion='OFFER',promotion_type='Promo Price',status='Schedule Valid',currency=c,invoice='BILL',quantity=1,discount_amount=2,sales_amount=8) for c in ('AED','AED','USD')]
        with patch('retail.promotions.history.report_rows',return_value=rows): _,result,_=execute_summary({})
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]['receipts'],1)
        self.assertEqual(result[0]['discount_amount'],4)

    def test_download_status_version(self):
        for kind in ('Promo Price','Buy X Get Y Promotion','Gift Voucher Promotion'):
            doc=frappe.get_doc(dict(doctype=kind,name='OFFER',modified='2026-10-17 08:00:00',disabled=1,enabled=0,products=[]))
            row=promotion_payload(doc)
            self.assertEqual(row['enabled'],0)
            self.assertEqual(row['disabled'],1)
            self.assertEqual(len(row['promotion_version']),64)

    def test_exchange_references_remap_to_split_lines(self):
        from retail.pos_exchange import split
        from retail.promotions.history import exchange_applications
        payload=dict(external_pos_reference='EX',items=[dict(qty=-1,rate=10,vat_amount=0),dict(qty=2,rate=10,vat_amount=0)],
                     payments=[dict(mode_of_payment='Cash',amount=10)],applied_promotions=[dict(item_row=1,promotion='RETURN'),dict(item_row=2,promotion='SALE')])
        sales, returns, _, _, _=split(payload)
        self.assertEqual(exchange_applications(payload,sales),[dict(item_row=1,promotion='SALE')])
        self.assertEqual(exchange_applications(payload,returns[None]),[dict(item_row=1,promotion='RETURN')])

    def test_no_evidence_legacy_and_explicit_empty_distinguished(self):
        class Doc(frappe._dict):
            def set(self,key,value): self[key]=value
        for payload, expected in ((dict(items=[]),False),(dict(items=[],applied_promotions=[]),True)):
            doc=Doc()
            with patch('retail.pos_completed_sale.payload_for',return_value=payload): capture(doc)
            result=json.loads(doc.custom_pos_promotion_history)
            self.assertEqual(result['reported'],expected)
            self.assertEqual(result['applications'],[])

    def test_invalid_evidence_does_not_block_sale(self):
        class Doc(frappe._dict):
            def set(self,key,value): self[key]=value
        doc=Doc()
        with patch('retail.pos_completed_sale.payload_for',return_value=dict(items=[],applied_promotions=[dict(promotion_type=[])])):
            capture(doc)
        self.assertEqual(json.loads(doc.custom_pos_promotion_history)['applications'][0]['status'],'Review Required')
