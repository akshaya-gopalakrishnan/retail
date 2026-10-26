"""Rollback-only integration checks for the Retail card extension."""
import unittest
from decimal import Decimal
from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate

from retail import voucher_cards as cards
from retail.api import gift_vouchers as api


class TestVoucherCards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if frappe.local.site != 'retail-test.localhost':
            raise RuntimeError('Run voucher-card integration checks only on retail-test.localhost.')
        frappe.set_user('Administrator')
        cls.company = frappe.db.get_value('POS Branch Counter', 'Business Demo Branch-COUNTER-1', 'company')
        cls.currency = frappe.get_cached_value('Company', cls.company, 'default_currency')
        cls.item = frappe.db.get_value('Item', {'disabled': 0, 'is_sales_item': 1}, 'name')

    def setUp(self):
        frappe.set_user('Administrator')
        from werkzeug.test import EnvironBuilder
        from werkzeug.wrappers import Request
        frappe.local.request = Request(EnvironBuilder(path='/printview', base_url='http://retail-test.localhost').get_environ())
        self.commit = patch.object(frappe.db, 'commit')
        self.commit.start()
        self.publish = patch.object(frappe, 'publish_realtime')
        self.publish.start()

    def tearDown(self):
        frappe.set_user('Administrator')
        frappe.db.rollback()
        self.publish.stop()
        self.commit.stop()

    def batch(self, **kwargs):
        doc = frappe.get_doc(dict(doctype='Voucher Card Batch', title='Rollback-only card test',
            company=self.company, currency=self.currency, voucher_amount=100,
            card_count=2, valid_from=nowdate(), expiry_date=add_days(nowdate(), 10),
            all_products=1, print_from=1, print_to=2, **kwargs))
        return doc.insert()

    def generate(self, batch):
        batch.db_set('generation_status', 'Queued')
        cards.generate_worker(batch.name)
        batch.reload()
        return frappe.get_all('Gift Voucher Ledger', filters={'voucher_card_batch': batch.name},
            pluck='name', order_by='card_number')

    def test_generation_is_unique_resumable_and_retains_history(self):
        batch = self.batch()
        batch.card_count = 205
        batch.save()
        names = self.generate(batch)
        self.assertEqual(len(names), 205)
        self.assertEqual(len(set(names)), 205)
        self.assertTrue(all(len(name) == 5 for name in names))
        self.assertEqual(batch.generated_count, 205)
        cards.generate_worker(batch.name)
        self.assertEqual(frappe.db.count('Gift Voucher Ledger', {'voucher_card_batch': batch.name}), 205)
        voucher = frappe.get_doc('Gift Voucher Ledger', names[0])
        self.assertEqual(api.invalid_reason(voucher), 'Draft')
        cards.manage_cards(batch.name, names[:1], 'Activate')
        self.assertIsNone(api.invalid_reason(voucher.reload()))
        self.assertEqual(frappe.db.get_value('Gift Voucher Ledger', names[1], 'status'), 'Draft')
        with self.assertRaises(frappe.ValidationError):
            frappe.delete_doc('Gift Voucher Ledger', names[0])
        voucher.reload()
        voucher.voucher_card_batch = None
        with self.assertRaises(frappe.ValidationError):
            voucher.save()
        batch.voucher_amount = 200
        with self.assertRaises(frappe.ValidationError):
            batch.save()

    def test_short_code_collision_retries_without_duplicate_cards(self):
        batch = self.batch()
        first, second = cards.make_card_code(), cards.make_card_code()
        while frappe.db.exists('Gift Voucher Ledger', first):
            first = cards.make_card_code()
        while second == first or frappe.db.exists('Gift Voucher Ledger', second):
            second = cards.make_card_code()
        with patch.object(cards, 'make_card_code', side_effect=[first, first, second]):
            names = self.generate(batch)
        self.assertEqual(names, [first, second])
        self.assertEqual(frappe.db.count('Gift Voucher Ledger', {'voucher_card_batch': batch.name}), 2)

    def test_generation_api_queues_after_commit_and_locks_batch_settings(self):
        batch = self.batch()
        with patch.object(frappe, 'enqueue') as enqueue:
            self.assertEqual(cards.generate_cards(batch.name), {'status': 'Queued'})
            self.assertTrue(enqueue.call_args.kwargs['enqueue_after_commit'])
            self.assertEqual(enqueue.call_args.kwargs['queue'], 'long')
        batch.reload()
        self.assertEqual(batch.generation_status, 'Queued')
        batch.card_count += 1
        with self.assertRaises(frappe.ValidationError):
            batch.save()

    def test_generation_progress_and_transaction_history_cannot_be_forged(self):
        batch = self.batch()
        batch.generation_status = 'Complete'
        batch.generated_count = 999
        with self.assertRaises(frappe.ValidationError):
            batch.save()
        batch.reload()
        name = self.generate(batch)[0]
        event_name = frappe.db.get_value('Voucher Card Transaction', {'voucher': name}, 'name')
        event = frappe.get_doc('Voucher Card Transaction', event_name)
        event.amount = 500
        with self.assertRaises(frappe.ValidationError):
            event.save(ignore_permissions=True)
        with self.assertRaises(frappe.ValidationError):
            frappe.delete_doc('Voucher Card Transaction', event_name, ignore_permissions=True)

    def test_ten_partial_redemptions_retry_and_reverse(self):
        from retail import pos_operations
        batch = self.batch(activate_all_cards=1)
        name = self.generate(batch)[0]
        for i in range(10):
            reference = f'{batch.name}:{i}'
            request = dict(voucher_code=name, amount=10, company=self.company)
            action = lambda: api.debit(name, 10, self.company, bill_total=10, reference=reference)
            first = pos_operations.execute('Voucher Redemption', reference, request, action, name)
            self.assertEqual(first['balance_after'], 90 - i * 10)
            self.assertTrue(pos_operations.execute('Voucher Redemption', reference, request, action, name)['duplicate'])
        voucher = frappe.get_doc('Gift Voucher Ledger', name)
        self.assertEqual(api.invalid_reason(voucher), 'Redeemed')
        self.assertEqual(frappe.db.count('Voucher Card Transaction', {'voucher': name}), 1)
        self.assertEqual(frappe.db.get_value('Voucher Card Transaction', {'voucher': name}, 'status'), 'Fully Used')
        self.assertEqual(frappe.db.count('Version', {'ref_doctype': 'Voucher Card Transaction'}), 0)
        restored = api.reverse(f'{batch.name}:9', 'same', company=self.company)
        self.assertEqual(restored['balance_after'], 10)
        self.assertEqual(frappe.db.count('Voucher Card Transaction', {'voucher': name}), 1)
        self.assertEqual(frappe.db.get_value('Voucher Card Transaction', {'voucher': name}, 'balance_after'), 10)
        self.assertTrue(api.reverse(f'{batch.name}:9', 'different', company=self.company)['duplicate'])
        cards.manage_cards(batch.name, [name], 'Block')
        self.assertEqual(api.invalid_reason(voucher.reload()), 'Blocked')

    def test_activation_times_define_one_continuous_period(self):
        from datetime import datetime, time
        from frappe.utils import getdate, get_time
        batch = self.batch(activate_all_cards=1, use_redemption_hours=1, active_from_time='09:00:00', active_to_time='17:00:00')
        name = self.generate(batch)[0]
        voucher = frappe.get_doc('Gift Voucher Ledger', name)
        self.assertEqual(str(get_time(voucher.active_from_time)), '09:00:00')
        def at(hour, minute=0):
            return datetime.combine(getdate(nowdate()), time(hour, minute))
        with patch.object(api, 'now_datetime', return_value=at(10)):
            self.assertEqual(api.debit(name, 10, self.company, bill_total=20)['balance_after'], 90)
            self.assertEqual(api.voucher_result(voucher)['active_from_time'], '09:00:00')
        with patch.object(api, 'now_datetime', return_value=at(8)):
            self.assertEqual(api.invalid_reason(voucher), 'Not yet valid')
            with self.assertRaises(frappe.ValidationError):
                api.debit(name, 10, self.company, bill_total=20)
        with patch.object(api, 'now_datetime', return_value=at(20)):
            self.assertIsNone(api.invalid_reason(voucher))
        html = frappe.get_print('Voucher Card Batch', batch.name, print_format='Voucher Cards - A4 - Retail')
        self.assertIn('09:00', html)
        self.assertNotIn('Daily', html)
        self.assertIn('17:00', html)
        batch.reload()
        batch.terms = 'Print text can still be edited'
        batch.save()
        batch.active_from_time = '08:00:00'
        with self.assertRaises(frappe.ValidationError):
            batch.save()

    def test_activation_endpoints_and_intermediate_days(self):
        from datetime import datetime, time
        from frappe.utils import getdate
        batch = self.batch(activate_all_cards=1, use_redemption_hours=1, active_from_time='22:00:00', active_to_time='02:00:00')
        batch.expiry_date = add_days(nowdate(), 2)
        batch.save()
        voucher = frappe.get_doc('Gift Voucher Ledger', self.generate(batch)[0])
        for offset, hour, expected in [(0,21,'Not yet valid'),(0,22,None),(1,12,None),(1,23,None),(2,2,None),(2,3,'Expired')]:
            clock = datetime.combine(getdate(add_days(nowdate(), offset)), time(hour))
            with patch.object(api, 'now_datetime', return_value=clock):
                self.assertEqual(api.invalid_reason(voucher), expected)
        same_day = self.batch(use_redemption_hours=1, active_from_time='00:00:00', active_to_time='04:00:00')
        same_day.expiry_date = same_day.valid_from
        same_day.save()
        same_day.active_from_time = '05:00:00'
        with self.assertRaises(frappe.ValidationError):
            same_day.save()
        self.assertFalse(self.batch().use_redemption_hours)

    def test_expiry_start_date_archive_and_company_permissions(self):
        batch = self.batch(activate_all_cards=1)
        name = self.generate(batch)[0]
        voucher = frappe.get_doc('Gift Voucher Ledger', name)
        voucher.valid_from = add_days(nowdate(), 1)
        self.assertEqual(api.invalid_reason(voucher), 'Not yet valid')
        voucher.valid_from = nowdate()
        voucher.expiry_date = add_days(nowdate(), -1)
        self.assertEqual(api.invalid_reason(voucher), 'Expired')
        with self.assertRaises(frappe.ValidationError):
            cards.manage_cards(batch.name, [name], 'Archive')
        frappe.db.set_value('Gift Voucher Ledger', name, 'expiry_date', add_days(nowdate(), -1))
        cards.manage_cards(batch.name, [name], 'Archive')
        self.assertEqual(api.invalid_reason(voucher.reload()), 'Archived')
        frappe.set_user('Guest')
        with self.assertRaises(frappe.PermissionError):
            cards.manage_cards(batch.name, [name], 'Activate')

    def test_restrictions_reject_wrong_products_and_missing_evidence(self):
        batch = self.batch()
        batch.all_products = 0
        batch.append('restrictions', {'item_code': self.item})
        batch.save()
        name = self.generate(batch)[0]
        cards.manage_cards(batch.name, [name], 'Activate')
        voucher = frappe.get_doc('Gift Voucher Ledger', name)
        rows = [dict(item_code=self.item, net_amount=35), dict(item_code=self.item, net_amount=0)]
        self.assertEqual(cards.eligible_amount(voucher, rows, 80), 35)
        with self.assertRaises(frappe.ValidationError):
            api.debit(name, 36, self.company, items=rows, bill_total=80)
        with self.assertRaises(frappe.ValidationError):
            api.debit(name, 10, self.company, bill_total=80)
        self.assertEqual(api.debit(name, 10, self.company, items=rows, bill_total=80)['balance_after'], 90)

    def test_erp_invoice_partial_amount_does_not_compound_and_cancel_restores(self):
        batch = self.batch(activate_all_cards=1)
        batch.all_products = 0
        batch.append('restrictions', {'item_code': self.item})
        batch.save()
        name = self.generate(batch)[0]
        company = frappe.get_cached_doc('Company', self.company)
        customer = frappe.db.get_value('Customer', {'disabled': 0}, 'name')
        invoice = frappe.get_doc(dict(doctype='Sales Invoice', company=self.company,
            customer=customer, posting_date=nowdate(), due_date=nowdate(), currency=self.currency,
            debit_to=company.default_receivable_account, update_stock=0,
            custom_gift_voucher_code=name, custom_voucher_card_redeem_amount=10,
            items=[dict(item_code=self.item, qty=1, rate=100, income_account=company.default_income_account,
                cost_center=company.cost_center, warehouse=frappe.db.get_value('Warehouse',
                    {'company': self.company, 'is_group': 0}, 'name'))]))
        invoice.insert()
        self.assertEqual(invoice.custom_gift_voucher_amount, 10)
        invoice.save()
        self.assertEqual(invoice.custom_gift_voucher_amount, 10)
        invoice.submit()
        self.assertEqual(frappe.db.get_value('Gift Voucher Ledger', name, 'balance_amount'), 90)
        invoice.cancel()
        self.assertEqual(frappe.db.get_value('Gift Voucher Ledger', name, 'balance_amount'), 100)

    def test_pos_api_partial_redemption_and_retry_after_block(self):
        batch = self.batch(activate_all_cards=1)
        name = self.generate(batch)[0]
        counter = frappe.get_doc('POS Branch Counter', 'Business Demo Branch-COUNTER-1')
        request = dict(branch=counter.branch, counter_code=counter.counter_code,
            voucher_code=name, amount=10, bill_total=45,
            external_pos_reference='card-sale-' + batch.name,
            redemption_reference='card-redemption-' + batch.name)
        self.assertEqual(api.redeem_gift_voucher(request)['balance_after'], 90)
        lookup = api.get_gift_voucher({**request, 'bill_total': 45})
        self.assertEqual(lookup['maximum_redeemable_amount'], 45)
        self.assertTrue(lookup['online_redemption_required'])
        cards.manage_cards(batch.name, [name], 'Block')
        self.assertTrue(api.redeem_gift_voucher(request)['duplicate'])
        self.assertEqual(api.get_gift_voucher(request)['maximum_redeemable_amount'], 0)

    def test_generated_batch_print_settings_save_from_browser_json(self):
        batch = self.batch()
        self.generate(batch)
        payload = frappe.parse_json(frappe.as_json(batch.as_dict()))
        payload['terms'] = 'Saved from print format dialog'
        payload['label_width'] = 90
        frappe.get_doc(payload).save()
        self.assertEqual(frappe.db.get_value('Voucher Card Batch', batch.name, 'terms'), payload['terms'])

    def test_print_format_install_preserves_customer_html_and_css(self):
        name = 'Voucher Cards - A4'
        frappe.db.set_value('Print Format', name, {'html': '<p>Customer layout</p>', 'css': '.customer {color:red;}'})
        cards.ensure_print_formats()
        html, css = frappe.db.get_value('Print Format', name, ['html', 'css'])
        self.assertEqual(html, '<p>Customer layout</p>')
        self.assertEqual(css, '.customer {color:red;}')

    def test_brand_and_category_descendant_eligibility(self):
        token = frappe.generate_hash(length=12)
        brand = frappe.get_doc(dict(doctype='Brand', brand='Voucher-test-' + token)).insert()
        parent = frappe.get_doc(dict(doctype='Item Group', item_group_name='Voucher-parent-' + token,
            parent_item_group='All Item Groups', is_group=1)).insert()
        child = frappe.get_doc(dict(doctype='Item Group', item_group_name='Voucher-child-' + token,
            parent_item_group=parent.name, is_group=0)).insert()
        original = frappe.db.get_value('Item', self.item, ['brand', 'item_group'], as_dict=True)
        try:
            frappe.db.set_value('Item', self.item, {'brand': brand.name, 'item_group': child.name})
            frappe.clear_document_cache('Item', self.item)
            for restriction in ({'brand': brand.name}, {'item_group': parent.name}):
                batch = self.batch()
                batch.all_products = 0
                batch.append('restrictions', restriction)
                batch.save()
                voucher = frappe._dict(voucher_card_batch=batch.name)
                rows = [dict(item_code=self.item, amount_including_vat=35)]
                self.assertEqual(cards.eligible_amount(voucher, rows, 80), 35)
                self.assertEqual(cards.eligible_amount(voucher, rows, 20), 20)
            wrong = self.batch()
            wrong.all_products = 0
            wrong.append('restrictions', {'brand': 'Voucher-test-' + token})
            wrong.save()
            # A forged terminal brand cannot make a different saved Item eligible.
            frappe.db.set_value('Item', self.item, 'brand', original.brand)
            frappe.clear_document_cache('Item', self.item)
            self.assertEqual(cards.eligible_amount(frappe._dict(voucher_card_batch=wrong.name),
                [dict(item_code=self.item, brand=brand.name, amount_including_vat=35)], 80), 0)
        finally:
            frappe.db.set_value('Item', self.item, original)
            frappe.clear_document_cache('Item', self.item)

    def test_large_value_and_print_formats(self):
        batch = self.batch()
        batch.voucher_amount = 1000000000000
        batch.terms = '<b>Terms</b> & conditions'
        batch.save()
        names = self.generate(batch)
        self.assertEqual(Decimal(str(frappe.db.get_value('Gift Voucher Ledger', names[0], 'voucher_amount'))), Decimal('1000000000000'))
        self.assertEqual(cards.card_money('1000000000000.01'), 1000000000000.01)
        cards.manage_cards(batch.name, [names[0]], 'Activate')
        self.assertEqual(api.debit(names[0], .01, self.company, bill_total=1)['balance_after'], 999999999999.99)
        for fmt in ('Voucher Cards - A4', 'Voucher Cards - Labels'):
            html = frappe.get_print('Voucher Card Batch', batch.name, print_format=fmt)
            self.assertEqual(html.count('class="voucher-card"'), 2)
            self.assertIn('data:image/svg+xml;base64,', html)
            self.assertIn('&lt;b&gt;Terms&lt;/b&gt;', html)
            self.assertNotIn('<script>untrusted</script>', html)
        for fmt in ('Voucher Card - Card', 'Voucher Card - Label'):
            html = frappe.get_print('Gift Voucher Ledger', names[0], print_format=fmt)
            self.assertEqual(html.count('class="voucher-card"'), 1)


def run_integration():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestVoucherCards)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise AssertionError('Voucher card integration checks failed.')
    return {'tests': result.testsRun, 'passed': True}


def run_unit_regressions():
    from retail.test_pos_gift_vouchers import TestVoucherAmounts
    from retail.test_gift_voucher_permissions import TestGiftVoucherPermissions
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
        for cls in (TestVoucherAmounts, TestGiftVoucherPermissions))
    original_flags = getattr(frappe.local, 'flags', frappe._dict())
    try:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        frappe.local.flags = original_flags
    if not result.wasSuccessful():
        raise AssertionError('Existing voucher unit regressions failed.')
    return {'tests': result.testsRun, 'passed': True}
