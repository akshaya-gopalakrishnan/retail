"""Offline settlement regressions. Site integration effects are rolled back."""
import copy
import json
import unittest
from unittest.mock import Mock, patch

import frappe
from frappe.utils import flt
from retail import pos_settlements as settlement


class TestSettlementFacts(unittest.TestCase):
    def setUp(self):
        self.rounding = patch.object(frappe, 'get_system_settings', return_value="Banker's Rounding")
        self.rounding.start()
        self.addCleanup(self.rounding.stop)

    def test_mixed_settlement_preserves_original(self):
        payload = dict(grand_total=200, payments=[dict(mode='Cash', amount=30), dict(mode='Card', amount=50),
            dict(mode='Credit Note', amount=100, credit_note_external_reference='RETURN-009'), dict(mode='Credit Sale', amount=20)])
        original = copy.deepcopy(payload)
        rows = settlement.settlements(payload)
        self.assertEqual([r['requested_amount'] for r in rows], [100, 20])
        self.assertEqual(len(settlement.cash_payments(payload)), 2)
        self.assertEqual(payload, original)

    def test_multiple_notes_and_remaining_credit_sale(self):
        rows = settlement.settlements(dict(grand_total=200, credit_note_redemptions=[
            dict(credit_note_external_reference='R1', amount=70), dict(credit_note_external_reference='R2', amount=100)]))
        self.assertEqual([r['requested_amount'] for r in rows], [70, 100, 30])

    def test_return_cannot_create_two_credits(self):
        with patch.object(frappe, 'throw', side_effect=frappe.ValidationError):
            with self.assertRaises(frappe.ValidationError):
                settlement.settlements(dict(grand_total=100, return_settlement_type='Reusable Customer Credit',
                    payments=[dict(mode='Cash', amount=100)]), True)

    def test_invalid_amounts_reject(self):
        with patch.object(frappe, 'throw', side_effect=frappe.ValidationError):
            for value in ('bad', float('nan'), float('inf'), -1):
                with self.subTest(value=value), self.assertRaises(frappe.ValidationError):
                    settlement.amount(value)

    def test_exception_log_failure_keeps_acceptance(self):
        transaction = frappe._dict(doctype="POS Accepted Transaction", name="accepted", status="Posted",
            sales_invoice="SI-1", external_pos_reference="sale", exception_reason=None)
        db = Mock()
        db.exists.return_value = False
        with patch.object(frappe, "db", db), patch.object(settlement, "insert", side_effect=RuntimeError("Audit unavailable")):
            settlement.audit(transaction, "Credit changed", "Warning")
        self.assertEqual(transaction.status, "Posted")
        self.assertIn("Audit unavailable", transaction.exception_reason)
        db.rollback.assert_called_once_with(save_point="pos_settlement_audit")
        db.set_value.assert_called_once()

    def test_worker_exception_does_not_stop_other_transactions(self):
        pending = [frappe._dict(name=name, branch="branch", customer="customer") for name in ("bad", "good")]
        documents = {name: Mock(name=name, doctype="POS Accepted Transaction", status="Posted", pos_invoice="POS-" + name)
            for name in ("bad", "good")}
        for name, document in documents.items():
            document.name = name
        db = Mock()
        processed = []
        def resolve(document):
            processed.append(document.name)
            if document.name == "bad":
                raise RuntimeError("Corrupt lifecycle link")
            document.status = "Reconciled"
        with patch.object(frappe, "db", db), patch.object(frappe, "get_all", return_value=pending), \
                patch.object(frappe, "get_doc", side_effect=lambda doctype, name, **kwargs: documents[name]), \
                patch.object(settlement, "resolve_transaction", side_effect=resolve), \
                patch.object(settlement, "audit"), patch.object(settlement, "refresh_day"):
            result = settlement.recover()
        self.assertEqual(result["processed"], 2)
        self.assertIn("good", processed)
        self.assertEqual(documents["good"].status, "Reconciled")
        self.assertEqual(db.rollback.call_count, 2)

    def test_recovery_context_restores_flag_after_failure(self):
        original = frappe.flags.get('pos_settlement_recovery')
        with self.assertRaises(RuntimeError):
            with settlement.recovery_context():
                self.assertTrue(frappe.flags.pos_settlement_recovery)
                raise RuntimeError()
        self.assertEqual(frappe.flags.get('pos_settlement_recovery'), original)


def run_integration():
    if frappe.local.site != 'retail-test.localhost':
        raise RuntimeError('Rollback-only suite restricted to retail-test.localhost')
    from retail.api import pos_sync as api
    frappe.set_user('Administrator')
    frappe.flags.in_test = True
    completed = []
    token = frappe.generate_hash(length=12)
    raw = json.loads(frappe.db.get_value('POS Sync Log', 'PSL-2644', 'request_json'))
    base = raw.get('payload', raw)
    counter = api._counter(base['branch'], base['counter_code'])
    cash = frappe.db.get_value('Mode of Payment', {'type': 'Cash'}, 'name')
    card = frappe.db.get_value('Mode of Payment', {'name': ['like', '%Card%']}, 'name')
    if not card:
        card = frappe.db.get_value('Mode of Payment', {'type': 'Bank'}, 'name')
    assert cash and card, 'Configure Cash and Card payment modes before integration testing'
    item = {**base['items'][0], 'qty': 2, 'rate': 100, 'rate_includes_vat': 0, 'amount': 200, 'net_amount': 200, 'vat_amount': 0}
    base.update(items=[item], grand_total=200, net_total=200, vat_amount=0, discount_amount=0,
                update_stock=0, payments=[dict(mode_of_payment=cash, amount=200)])
    base.pop('rounded_total', None)
    base.pop('rounding_adjustment', None)

    def ref(suffix):
        return f'settlement-test-{token}-{suffix}'

    def sale(suffix, **changes):
        payload = frappe._dict({**copy.deepcopy(base), 'external_pos_reference': ref(suffix), **changes})
        response = api.create_pos_invoice(payload)
        assert response.get('accepted') and response['status'] == 'Success', response
        transaction = frappe.get_doc('POS Accepted Transaction', response['accepted_transaction'])
        assert json.loads(transaction.payload_json) == dict(payload)
        return payload, response, transaction

    def posted(transaction):
        transaction.reload()
        assert transaction.sales_invoice, (transaction.status, transaction.exception_reason)
        return frappe.get_doc('Sales Invoice', transaction.sales_invoice)

    def ret(suffix, original_ref, typ='Reusable Customer Credit', **changes):
        returned = {**item, 'qty': 1, 'amount': 100, 'net_amount': 100}
        payload = frappe._dict({**copy.deepcopy(base), 'external_pos_reference': ref(suffix),
            'original_external_pos_reference': original_ref, 'return_settlement_type': typ,
            'items': [returned], 'grand_total': 100, 'net_total': 100, 'payments': [], **changes})
        response = api.create_pos_return_invoice(payload)
        assert response.get('accepted') and response['status'] == 'Success', response
        transaction = frappe.get_doc('POS Accepted Transaction', response['accepted_transaction'])
        assert json.loads(transaction.payload_json) == dict(payload)
        return payload, response, transaction

    def redeem(suffix, source, requested=100, **changes):
        return sale(suffix, payments=[dict(mode_of_payment=cash, amount=200-requested)],
            credit_note_redemptions=[dict(credit_note_external_reference=source, amount=requested)], **changes)

    def allocations(transaction, typ='Credit Note Redeemed'):
        return frappe.get_all('POS Settlement Allocation', filters={'transaction': transaction.name, 'settlement_type': typ}, fields=['*'])

    try:
        with patch.object(frappe, 'enqueue'):
            _, _, normal = sale('cash-card', payments=[dict(mode_of_payment=cash, amount=30), dict(mode_of_payment=card, amount=170)])
            assert posted(normal).outstanding_amount == 0
            completed.append('normal cash/card sale')
            _, _, credit = sale('full-credit', payments=[])
            assert posted(credit).outstanding_amount == 200
            assert allocations(credit, 'Credit Sale')[0].requested_amount == 200
            completed.append('full credit sale')
            _, _, partial = sale('partial-credit', payments=[dict(mode_of_payment=cash, amount=30)])
            assert posted(partial).outstanding_amount == 170
            completed.append('partial cash + credit sale')
            _, _, note = ret('reusable', normal.external_pos_reference)
            assert posted(note).outstanding_amount == -100
            assert posted(normal).outstanding_amount == 0
            completed.append('reusable credit-note issuance')
            _, _, reduction = ret('reduce-debt', credit.external_pos_reference, 'Original Debt Reduction')
            assert posted(reduction).outstanding_amount == 0
            assert posted(credit).outstanding_amount == 100
            assert allocations(reduction, 'Original Debt Reduction')[0].applied_amount == 100
            completed.append('return reducing original debt without reusable credit')
            _, _, redeemed = redeem('redeemed', note.external_pos_reference)
            assert posted(redeemed).outstanding_amount == 0
            assert posted(note).outstanding_amount == 0
            completed.append('offline credit note redeemed later')
            pending_payload, pending_response, pending_sale = redeem('pending-note', ref('late-note'))
            assert posted(pending_sale).outstanding_amount == 100
            assert allocations(pending_sale)[0].status == 'Pending Dependency'
            _, _, late_note = ret('late-note', normal.external_pos_reference)
            settlement.recover(1000)
            assert posted(pending_sale).outstanding_amount == 0
            completed.append('sale before referenced credit note')
            _, _, pending_return = ret('early-return', ref('later-original'))
            assert not pending_return.pos_invoice and pending_return.status == 'Pending Dependency'
            _, _, late_original = sale('later-original')
            settlement.recover(1000)
            assert posted(pending_return).outstanding_amount == -100
            completed.append('credit note before original sale')
            _, _, reverse_sale = redeem('reverse-sale', ref('reverse-return'))
            _, _, reverse_return = ret('reverse-return', ref('reverse-original'))
            _, _, reverse_original = sale('reverse-original')
            settlement.recover(1000)
            assert posted(reverse_sale).outstanding_amount == 0
            assert posted(reverse_return).outstanding_amount == 0
            completed.append('redemption before both original sale and return')
            retry = api.create_pos_invoice(pending_payload)
            assert retry['duplicate'] and {k:v for k,v in retry.items() if k != 'duplicate'} == {k:v for k,v in pending_response.items() if k != 'duplicate'}
            assert frappe.db.count('POS Invoice', {'external_pos_reference': pending_payload.external_pos_reference}) == 1
            completed.append('exact retry returns durable acceptance receipt')
            conflict = api.create_pos_invoice({**pending_payload, 'pos_bill_no': 'changed'})
            assert conflict['status'] == 'Failed' and 'conflict' in conflict['error'].lower()
            completed.append('conflicting duplicate reference')
            _, _, small_original = sale('small-original')
            _, _, small_note = ret('small-note', small_original.external_pos_reference,
                items=[{**item, 'qty': 1, 'rate': 80, 'amount': 80, 'net_amount': 80}], grand_total=80, net_total=80)
            _, _, short = redeem('partial-credit-note', small_note.external_pos_reference)
            assert posted(short).outstanding_amount == 20, (posted(short).outstanding_amount, allocations(short), posted(small_note).outstanding_amount)
            assert allocations(short)[0].applied_amount == 80 and allocations(short)[0].unresolved_amount == 20
            assert settlement.summary({'transaction': short.name})['credit_notes_redeemed'] == 100
            _, _, exhausted = redeem('exhausted-note', small_note.external_pos_reference)
            assert posted(exhausted).outstanding_amount == 100
            assert allocations(exhausted)[0].applied_amount == 0
            completed.append('partial/exhausted ERP credit retains requested settlement')
            _, _, multi_original = sale('multi-original')
            _, _, multi_note1 = ret('multi-note1', multi_original.external_pos_reference)
            _, _, multi_note2 = ret('multi-note2', multi_original.external_pos_reference)
            _, _, multi = sale('multi-redemption', payments=[], credit_note_redemptions=[
                dict(credit_note_external_reference=multi_note1.external_pos_reference, amount=100),
                dict(credit_note_external_reference=multi_note2.external_pos_reference, amount=100)])
            assert posted(multi).outstanding_amount == 0
            assert len(allocations(multi)) == 2
            completed.append('multiple credit notes in one sale')
            _, _, split_original = sale('split-original')
            _, _, split_note = ret('split-note', split_original.external_pos_reference)
            _, _, split_first = redeem('split-first', split_note.external_pos_reference, 40)
            _, _, split_second = redeem('split-second', split_note.external_pos_reference, 60)
            assert posted(split_first).outstanding_amount == posted(split_second).outstanding_amount == 0
            assert posted(split_note).outstanding_amount == 0
            completed.append('one credit note across multiple sales')
            before_journals = frappe.db.count('Journal Entry')
            settlement.recover(1000)
            settlement.recover(1000)
            assert frappe.db.count('Journal Entry') == before_journals
            completed.append('repeated settlement recovery never duplicates allocation')
            _, _, shifted = sale('late-shift')
            assert posted(shifted).docstatus == 1
            completed.append('late sync after shift close')
            def closed(*args, **kwargs):
                raise frappe.ValidationError('Test: late transaction after day close')
            with patch.object(api, '_assert_day_not_closed', side_effect=closed):
                _, _, closed_day = sale('late-day')
            assert posted(closed_day).docstatus == 1
            completed.append('late sync after day close')
            with patch.object(api, '_validate_credit_customer', side_effect=frappe.ValidationError('Credit limit changed; customer balance changed')):
                _, _, changed_credit = sale('changed-credit-limit', payments=[])
            assert posted(changed_credit).outstanding_amount == 200
            assert frappe.db.exists('POS Settlement Exception', {'transaction': changed_credit.name, 'severity': 'Requires Review'})
            completed.append('credit-limit/customer-balance change is advisory')
            _, _, recovery_original = sale('recovery-original')
            _, _, recovery_note = ret('recovery-note', recovery_original.external_pos_reference)
            with patch.object(settlement, 'reconcile', side_effect=RuntimeError('Test accounting temporarily unavailable')):
                failed_payload, _, failed = redeem('recovery-redemption', recovery_note.external_pos_reference)
            assert posted(failed).outstanding_amount == 100
            assert allocations(failed)[0].status == 'Reconciliation Exception'
            settlement.recover(1000)
            assert posted(failed).outstanding_amount == 0
            assert allocations(failed)[0].applied_amount == 100
            completed.append('reconciliation failure then successful recovery')
            from retail.customer_balances import get_customer_credit_balances
            balances = get_customer_credit_balances([normal.customer], normal.company)['data'][0]
            assert balances['net_balance'] == balances['outstanding_amount'] == balances['current_receivable']
            assert balances['available_credit_including_credit_notes'] == flt(balances['credit_limit'] - balances['outstanding_amount'], 2)
            completed.append('native customer outstanding and no double deduction of open credits')
            from retail.retail_app.report.pos_report_utils import pos_sales_summary
            columns, rows = pos_sales_summary(frappe._dict(company=normal.company,
                from_date=base['posting_date'], to_date=base['posting_date']))[:2]
            assert any(c['fieldname'] == 'credit_notes_unresolved' for c in columns)
            assert sum(r.get('credit_notes_redeemed', 0) for r in rows if not r.get('is_total_row')) >= 100
            assert settlement.summary({'transaction': failed.name})['credit_notes_applied'] == 100
            completed.append('reporting preserves historical requested and accounting applied amounts')
            from retail.retail_app.report.pos_report_utils import payment_mode_summary, pos_transaction_log
            filters = frappe._dict(company=normal.company, from_date=base['posting_date'],
                to_date=base['posting_date'])
            _, log_rows = pos_transaction_log(filters)
            bills = {row.invoice_no: row for row in log_rows}
            assert bills[changed_credit.pos_invoice].payment_mode == 'Credit Sale'
            assert bills[changed_credit.pos_invoice].credit_sales == 200
            assert bills[recovery_note.pos_invoice].credit_notes_issued == 100
            assert bills[failed.pos_invoice].credit_notes_redeemed == 100
            assert bills[failed.pos_invoice].credit_notes_applied == 100
            assert bills[failed.pos_invoice].credit_notes_unresolved == 0
            assert frappe.db.get_value('POS Invoice', changed_credit.pos_invoice, 'custom_pos_transaction_type') == 'Credit Sale'
            assert frappe.db.get_value('POS Invoice', recovery_note.pos_invoice, 'custom_pos_transaction_type') == 'Credit Note Issued'
            assert frappe.db.get_value('POS Invoice', failed.pos_invoice, 'custom_pos_transaction_type') == 'Credit Note Redeemed'
            log = frappe.db.get_value('POS Sync Log', {'external_reference': failed.external_pos_reference,
                'status': 'Success'}, ['sync_type', 'custom_pos_transaction_type'], as_dict=True)
            assert log.sync_type == 'POS Sale' and log.custom_pos_transaction_type == 'Credit Note Redeemed'
            for typ, field in (('Credit Sale', 'credit_sales'),
                    ('Credit Note Issued', 'credit_notes_issued'),
                    ('Credit Note Redeemed', 'credit_notes_redeemed')):
                _, summary_rows = payment_mode_summary(frappe._dict(dict(filters), payment_mode=typ))
                assert summary_rows and all(row.mode_of_payment == typ for row in summary_rows)
                assert sum(row[field] for row in summary_rows) >= 100
                assert all(row.paid_amount == 0 for row in summary_rows)
            completed.append('transaction and payment reports distinguish non-cash settlements')
            _, _, exchange_original = sale('exchange-original')
            exchange_rows = [{**item, 'qty': 1, 'amount': 100, 'net_amount': 100},
                {**item, 'qty': -1, 'amount': -100, 'net_amount': -100, 'original_external_pos_reference': exchange_original.external_pos_reference}]
            _, _, exchange = sale('exchange', items=exchange_rows, grand_total=0, net_total=0, payments=[], exchange_mode_of_payment=cash)
            assert posted(exchange).docstatus == 1
            completed.append('mixed exchange path')
            _, _, cash_original = sale('cash-refund-original')
            _, _, cash_return = ret('cash-refund', cash_original.external_pos_reference, 'Cash Refund', payments=[dict(mode_of_payment=cash, amount=100)])
            assert posted(cash_return).outstanding_amount == 0
            _, _, card_return = ret('card-refund', cash_original.external_pos_reference, 'Card Refund', payments=[dict(mode_of_payment=card, amount=100)])
            assert posted(card_return).outstanding_amount == 0
            completed.append('cash and card refunds')
            missing_shift_payload, _, missing_shift = sale('missing-shift', external_shift_reference=ref('missing-shift-ref'),
                external_session_reference=ref('missing-session-ref'))
            assert posted(missing_shift).docstatus == 1 and missing_shift.status == 'Pending Dependency'
            assert json.loads(missing_shift.payload_json) == dict(missing_shift_payload)
            completed.append('missing shift/session does not block completed sale')
            try:
                frappe.get_doc('POS Invoice', normal.pos_invoice).cancel()
            except frappe.ValidationError:
                pass
            else:
                raise AssertionError('Completed bill was cancelled')
            assert posted(normal).docstatus == 1
            completed.append('completed bill cannot be cancelled')
            # Pending posting preserves acceptance even for a technical posting failure.
            with patch.object(api, '_append_invoice_items', side_effect=RuntimeError('Posting temporarily unavailable')):
                delayed_payload, _, delayed = sale('posting-recovery')
            assert not delayed.pos_invoice
            settlement.recover(1000)
            assert posted(delayed).docstatus == 1
            completed.append('accepted posting failure recovers without terminal resend')
            return dict(passed=completed, business_data='rolled back')
    finally:
        frappe.db.rollback()


class TestConcurrentSettlement(unittest.TestCase):
    def test_two_concurrent_attempts_share_one_credit(self):
        """Exercise the real reconciliation function with a locking ledger adapter."""
        import threading
        from concurrent.futures import ThreadPoolExecutor
        lock = threading.Lock()
        thread_state = threading.local()
        source = frappe._dict(name='credit', is_return=1, docstatus=1, company='company', customer='customer',
            debit_to='receivable', currency='AED', outstanding_amount=-100, cost_center='cost')
        destinations = {name: frappe._dict(name=name, is_return=0, docstatus=1, company='company', customer='customer',
            debit_to='receivable', currency='AED', outstanding_amount=100, cost_center='cost') for name in ('first', 'second')}
        journals = []
        barrier = threading.Barrier(2)

        class DB:
            def get_value(self, doctype, name, field, for_update=False):
                if doctype == 'Customer' and for_update:
                    lock.acquire()
                    thread_state.locked = True
                return name

        class Journal:
            def __init__(self, values):
                self.values = values
                self.flags = frappe._dict()
                self.name = 'JE-' + str(len(journals))

            def insert(self, **kwargs):
                pass

            def submit(self):
                amount = self.values['accounts'][0]['debit_in_account_currency']
                destination = self.values['accounts'][1]['reference_name']
                source.outstanding_amount += amount
                destinations[destination].outstanding_amount -= amount
                journals.append(self)

        def get_doc(doctype, name=None, **kwargs):
            if isinstance(doctype, dict):
                return Journal(doctype)
            return source if name == 'credit' else destinations[name]

        def run(destination):
            barrier.wait()
            try:
                return settlement.reconcile('credit', destination, 100, frappe._dict(customer='customer', company='company', external_pos_reference=destination))[0]
            finally:
                if getattr(thread_state, 'locked', False):
                    lock.release()

        with patch.object(frappe, 'db', DB()), patch.object(frappe, 'get_doc', side_effect=get_doc), \
                patch.object(frappe, 'get_cached_value', return_value='AED'), \
                patch.object(frappe, 'get_system_settings', return_value="Banker's Rounding"):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(run, ('first', 'second')))
        self.assertEqual(sorted(results), [0, 100])
        self.assertEqual(len(journals), 1)
        self.assertEqual(source.outstanding_amount, 0)


def run_unit():
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(cls)
        for cls in (TestSettlementFacts, TestConcurrentSettlement)])
    result = unittest.TestResult()
    suite.run(result)
    if result.errors or result.failures:
        raise AssertionError(result.errors + result.failures)
    return {"passed": result.testsRun}


class TestSettlementIntegration(unittest.TestCase):
    def test_completed_offline_settlement_flow(self):
        result = run_integration()
        self.assertGreaterEqual(len(result["passed"]), 22)
