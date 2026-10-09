"""Rollback-only exchange stock/accounting regressions."""
import copy
import json
import unittest
from unittest.mock import patch
import frappe
from frappe.utils import flt, nowdate, nowtime


class TestExchangeMonetaryComparisons(unittest.TestCase):
    def test_subcent_values_match_without_changing_amounts(self):
        from retail.pos_exchange import split, _money_equal
        with patch('frappe.get_system_settings', return_value="Banker's Rounding"):
            self.assertTrue(_money_equal(35.000048, 35.00))
            self.assertTrue(_money_equal(-35.000048, -35.00))
            self.assertTrue(_money_equal(.000048, 0))
            self.assertFalse(_money_equal(35.01, 35))
            for vat in (0, 2.381):
                payload = {
                    'external_pos_reference': 'precision-regression',
                    'items': [
                        {'qty': 1, 'rate': 50.000048, 'amount': 50.000048,
                         'net_amount': 50.000048, 'vat_amount': vat},
                        {'qty': -1, 'rate': 15, 'amount': -15,
                         'net_amount': -15, 'vat_amount': 0}],
                    'grand_total': 35+vat, 'net_total': 35,
                    'vat_amount': vat, 'rounded_total': round(35+vat, 2),
                    'payments': [{'mode_of_payment': 'CARD', 'amount': 35.000048+vat}]}
                before = copy.deepcopy(payload)
                sales, _, payments, _, _ = split(payload)
                self.assertEqual(payload, before)
                self.assertEqual(sales[0]['net_amount'], 50.000048)
                self.assertEqual(sales[0]['vat_amount'], vat)
                self.assertEqual(payments[0]['amount'], 35.000048+vat)
                for field in ('grand_total', 'net_total', 'vat_amount', 'rounded_total'):
                    bad = copy.deepcopy(payload)
                    bad[field] += .02
                    with patch('retail.pos_exchange.frappe.throw', side_effect=ValueError):
                        with self.assertRaises(ValueError, msg=field):
                            split(bad)
                bad = copy.deepcopy(payload)
                bad['payments'][0]['amount'] += .02
                with patch('retail.pos_exchange.frappe.throw', side_effect=ValueError):
                    with self.assertRaises(ValueError):
                        split(bad)


def run_integration():
    assert frappe.local.site == 'retail-test.localhost'
    from retail.api import pos_sync as api
    from retail.pos_exchange import split
    frappe.set_user('Administrator')
    frappe.flags.in_test = True
    base = json.loads(frappe.db.get_value('POS Invoice', 'POS-89', 'custom_pos_completed_payload'))
    base.update(posting_date=nowdate(), posting_time=nowtime(), business_date=nowdate(), issued_vouchers=[])
    token = frappe.generate_hash(length=12)
    row = {**base['items'][0], 'rate': 50, 'rate_includes_vat': 0, 'vat_rate': 0, 'vat_amount': 0}
    results = []
    try:
        originals = []
        for label, sold, returned, vat in [('positive', 2, 1, 0), ('zero', 1, 1, 0),
                                          ('negative', 1, 2, 0), ('vat', 2, 1, 2.5),
                                          ('unlinked-positive', 2, 1, 0),
                                          ('unlinked-zero', 1, 1, 0),
                                          ('unlinked-negative', 1, 2, 0)]:
            row['vat_amount'] = vat
            row['vat_rate'] = 5 if vat else 0
            original = {**copy.deepcopy(base), 'external_pos_reference': f'exchange-test-{token}-{label}-original',
                        'grand_total': 150+3*vat, 'vat_amount': 3*vat,
                        'items': [{**row, 'qty': 3, 'amount': 150, 'net_amount': 150, 'vat_amount': 3*vat}],
                        'payments': [{'mode_of_payment': 'CARD', 'amount': 150+3*vat}]}
            created = api.create_pos_invoice(original)
            assert created['status'] == 'Success', created
            originals.append(original['external_pos_reference'])
            total = (sold-returned)*(50+vat)
            payload = {**copy.deepcopy(base), 'external_pos_reference': f'exchange-test-{token}-{label}',
                       'original_external_pos_reference': '' if label.startswith('unlinked-') else original['external_pos_reference'],
                       'items': [{**row, 'qty': sold, 'amount': sold*50, 'net_amount': sold*50, 'vat_amount': sold*vat},
                                 {**row, 'qty': -returned, 'rate': -50, 'amount': -returned*50,
                                  'net_amount': -returned*50, 'vat_amount': -returned*vat}],
                       'grand_total': total, 'vat_amount': (sold-returned)*vat, 'exchange_mode_of_payment': 'CARD',
                       'payments': [{'mode_of_payment': 'CARD', 'amount': total}] if total else []}
            result = api.create_pos_invoice(payload)
            assert result['status'] == 'Success', result
            assert result['grand_total'] == total
            assert api.create_pos_invoice(payload)['duplicate'] is True
            names = result['accounting_invoices']
            assert len(names) == 2
            docs = [frappe.get_doc('POS Invoice', result['sale_invoice']),
                    frappe.get_doc('POS Invoice', result['return_invoices'][0])]
            if label.startswith('unlinked-'):
                assert not docs[1].return_against
                assert not frappe.db.get_value('Sales Invoice', docs[1].consolidated_invoice, 'return_against')
            else:
                assert docs[1].return_against == created['invoice_name']
            assert sum(d.paid_amount for d in docs) == total
            account = docs[0].payments[0].account
            gl = frappe.get_all('GL Entry', filters={'voucher_type': 'Sales Invoice',
                'voucher_no': ['in', names], 'is_cancelled': 0}, fields=['account', 'debit', 'credit'])
            assert abs(sum(r.debit-r.credit for r in gl)) < .01
            assert abs(sum(r.debit-r.credit for r in gl if r.account == account)-total) < .01, gl
            sle = frappe.get_all('Stock Ledger Entry', filters={'voucher_type': 'Sales Invoice',
                'voucher_no': ['in', names], 'is_cancelled': 0}, fields=['actual_qty', 'item_code'])
            assert sum(r.actual_qty for r in sle if r.item_code == row['item_code']) == returned-sold, sle
            assert all(flt(frappe.db.get_value('Sales Invoice', name, 'outstanding_amount')) == 0 for name in names)
            results.append(label + ': net CARD, stock, balanced GL, zero balances and duplicate retry')
        bad = copy.deepcopy(payload)
        bad['original_external_pos_reference'] = ''
        assert None in split(bad)[1]
        results.append('missing/empty original reference selects standalone return')
        row.update(vat_amount=0, vat_rate=0)
        multiple = {**copy.deepcopy(base), 'external_pos_reference': f'exchange-test-{token}-multiple',
                    'items': [{**row, 'qty': 3, 'amount': 150, 'net_amount': 150},
                              {**row, 'qty': -1, 'amount': -50, 'net_amount': -50,
                               'original_external_pos_reference': originals[0]},
                              {**row, 'qty': -1, 'amount': -50, 'net_amount': -50,
                               'original_external_pos_reference': originals[1]}],
                    'grand_total': 50, 'vat_amount': 0, 'payments': [{'mode_of_payment': 'CARD', 'amount': 50}]}
        response = api.create_pos_invoice(multiple)
        assert response['status'] == 'Success' and len(response['return_invoices']) == 2, response
        assert sum(frappe.db.get_value('Sales Invoice', n, 'paid_amount') for n in response['accounting_invoices']) == 50
        results.append('multiple original invoices produce separate settled returns')
        refund = {**copy.deepcopy(base), 'external_pos_reference': f'exchange-test-{token}-refund',
                  'original_external_pos_reference': originals[3],
                  'items': [{**row, 'qty': -1, 'amount': -50, 'net_amount': -50,
                             'vat_rate': 5, 'vat_amount': -2.5}],
                  'grand_total': -52.5, 'vat_amount': -2.5,
                  'payments': [{'mode_of_payment': 'CARD', 'amount': 52.5}]}
        response = api.create_pos_invoice(refund)
        assert response['status'] == 'Success' and response['sale_invoice'] is None, response
        assert response['net_payments'][0]['amount'] == -52.5
        assert len(response['accounting_invoices']) == 1
        assert frappe.db.get_value('Sales Invoice', response['accounting_invoices'][0], 'outstanding_amount') == 0
        results.append('return-only receipt accepts a positive refund magnitude and posts a credit note')
        refund['external_pos_reference'] = f'exchange-test-{token}-unlinked-refund'
        refund.pop('original_external_pos_reference')
        response = api.create_pos_invoice(refund)
        assert response['status'] == 'Success' and response['sale_invoice'] is None, response
        assert not frappe.db.get_value('POS Invoice', response['return_invoices'][0], 'return_against')
        assert not frappe.db.get_value('Sales Invoice', response['accounting_invoices'][0], 'return_against')
        results.append('return-only receipt without a bill creates a standalone credit note')
        refund['external_pos_reference'] = f'exchange-test-{token}-dedicated-return'
        response = api.create_pos_return_invoice(refund)
        assert response['status'] == 'Success', response
        standalone = frappe.get_doc('POS Invoice', response['return_invoice'])
        assert standalone.is_return and not standalone.return_against
        assert not frappe.db.get_value('Sales Invoice', standalone.consolidated_invoice, 'return_against')
        assert api.create_pos_return_invoice(refund)['duplicate']
        results.append('dedicated return API also accepts standalone returns and duplicate retries')
        combined = copy.deepcopy(multiple)
        combined['external_pos_reference'] = f'exchange-test-{token}-combined'
        combined['original_external_pos_reference'] = originals[1]
        combined['items'] = [{**row, 'qty': 2, 'amount': 100, 'net_amount': 100},
                             {**row, 'qty': -1, 'amount': -50, 'net_amount': -50},
                             {**row, 'qty': -1, 'amount': -50, 'net_amount': -50,
                              'original_external_pos_reference': ''}]
        combined.update(grand_total=0, payments=[], exchange_mode_of_payment='CARD')
        response = api.create_pos_invoice(combined)
        assert response['status'] == 'Success' and len(response['return_invoices']) == 2, response
        links = [frappe.db.get_value('POS Invoice', name, 'return_against') for name in response['return_invoices']]
        assert sum(bool(link) for link in links) == 1, links
        results.append('one receipt can combine linked and standalone returns; empty item reference overrides header')
        from retail.pos_operations import execute
        from retail.pos_external_refs import authorize
        changed = copy.deepcopy(multiple)
        changed['grand_total'] = 51
        counter = authorize('Sales Invoice', changed)
        try:
            execute('POS Sale', changed['external_pos_reference'],
                    {'payload': changed, 'company': counter.company, 'counter': counter.name}, lambda: None)
            raise AssertionError('Changed retry accepted')
        except frappe.ValidationError:
            pass
        results.append('changed retry rejected')
        for field in ('grand_total', 'vat_amount'):
            bad = copy.deepcopy(multiple)
            bad[field] += .01
            try:
                split(bad)
                raise AssertionError('One-cent mismatch accepted')
            except frappe.ValidationError:
                pass
        results.append('one-cent header mismatches rejected')
        failed = {**copy.deepcopy(multiple), 'external_pos_reference': f'exchange-test-{token}-atomic'}
        failed['items'][1]['qty'] = -999
        failed['items'][1]['amount'] = failed['items'][1]['net_amount'] = -49950
        failed['grand_total'] = -49850
        failed['payments'][0]['amount'] = -49850
        response = api.create_pos_invoice(failed)
        assert response['status'] == 'Failed', response
        assert 'Cannot return more than' in response['error'], response
        assert not frappe.db.exists('POS Invoice', {'external_pos_reference': failed['external_pos_reference']})
        assert not frappe.db.exists('POS Invoice', {'external_pos_reference': multiple['external_pos_reference']})
        results.append('over-return failure rolls back all uncommitted stock/GL/components')
        missing = copy.deepcopy(refund)
        missing['external_pos_reference'] = f'exchange-test-{token}-missing'
        missing['original_external_pos_reference'] = f'exchange-test-{token}-not-synced'
        response = api.create_pos_invoice(missing)
        assert response['status'] == 'Failed' and response['error_code'] == 'BlockedDependency', response
        results.append('supplied missing original does not silently become a standalone return')
        return {'passed': results, 'business_data': 'rolled back'}
    finally:
        frappe.db.rollback()
