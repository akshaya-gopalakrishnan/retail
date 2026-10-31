"""Rollback-only real posting checks for privileged Desk corrections."""
import copy
import json
from unittest.mock import patch
import frappe


def run_integration():
    if frappe.local.site != 'retail-test.localhost':
        raise RuntimeError('Local rollback-only suite')
    from retail.api import pos_sync as api
    from retail import pos_admin_recovery as admin, pos_operations
    original_user = frappe.session.user
    frappe.set_user('Administrator')
    frappe.flags.in_test = True
    token = frappe.generate_hash(length=10)
    raw = json.loads(frappe.db.get_value('POS Sync Log', 'PSL-2644', 'request_json'))
    base = raw.get('payload', raw)
    cash = frappe.db.get_value('Mode of Payment', {'type': 'Cash'}, 'name')
    item = {**base['items'][0], 'qty': 2, 'rate': 100, 'amount': 200,
        'net_amount': 200, 'vat_amount': 0, 'rate_includes_vat': 0}
    base.update(items=[item], grand_total=200, net_total=200, vat_amount=0,
        discount_amount=0, update_stock=0, payments=[dict(mode_of_payment=cash, amount=150)])
    for field in ('rounded_total', 'rounding_adjustment'):
        base.pop(field, None)
    results = []

    def create(suffix):
        payload = frappe._dict({**copy.deepcopy(base), 'external_pos_reference': 'admin-test-'+token+'-'+suffix})
        with patch.object(api, '_base_invoice', side_effect=frappe.ValidationError('Test posting failure')):
            response = api.create_pos_invoice(payload)
        assert response.get('accepted'), response
        tx = frappe.get_doc('POS Accepted Transaction', response['accepted_transaction'])
        assert tx.status == 'Reconciliation Exception' and not tx.pos_invoice
        return payload, tx

    def correct(payload, total=180):
        value = copy.deepcopy(payload)
        value.update(grand_total=total, net_total=total)
        value['items'][0].update(rate=total/2, amount=total, net_amount=total)
        return value

    def denied(action):
        frappe.db.savepoint('admin_denied')
        try:
            action()
        except (frappe.ValidationError, frappe.PermissionError):
            frappe.db.rollback(save_point='admin_denied')
        else:
            raise AssertionError('Forbidden edit was accepted')

    try:
        with patch.object(frappe, 'enqueue'):
            payload, tx = create('log')
            log = frappe.get_doc('POS Sync Log', pos_operations.find('POS Sale', payload.external_pos_reference).name)
            before = log.request_json
            wrapper = json.loads(before)
            wrapper['payload'] = correct(payload)
            log.request_json = json.dumps(wrapper)
            log.correction_reason = 'Fix incorrect item net amount'
            log.save()
            assert frappe.db.get_value('POS Sync Log', log.name, 'request_json') == log.request_json
            assert frappe.db.get_value('POS Sync Log', log.name, 'original_request_json') == before
            tx.reload()
            assert json.loads(tx.payload_json) == payload
            assert admin.effective_payload(tx)['grand_total'] == 180
            allocation = frappe.get_doc('POS Settlement Allocation', {'transaction':tx.name})
            assert allocation.requested_amount == 30 and allocation.unresolved_amount == 30
            results.append('Admin Save persists log edits, preserves original request/bill and rebuilds credit allocation')
            result = admin.retry_posting('POS Sync Log', log.name)
            assert result['status'] == 'Reconciled', result
            tx.reload()
            invoice = frappe.get_doc('POS Invoice', tx.pos_invoice)
            assert invoice.docstatus == 1 and invoice.grand_total == 180
            assert frappe.db.get_value('Sales Invoice', tx.sales_invoice, 'docstatus') == 1
            gl = frappe.get_all('GL Entry', filters={'voucher_no':tx.sales_invoice, 'is_cancelled':0}, fields=['debit','credit'])
            assert gl and abs(sum(row.debit-row.credit for row in gl)) < .001
            exceptions = frappe.get_all('POS Settlement Exception', filters={'transaction':tx.name}, fields=['status','resolved_at'])
            assert exceptions and all(r.status=='Reconciled' and r.resolved_at for r in exceptions)
            assert not tx.exception_reason
            assert api.create_pos_invoice(payload).get('duplicate') is True
            admin.retry_posting('POS Sync Log', log.name)
            assert frappe.db.count('POS Invoice', {'external_pos_reference':payload.external_pos_reference}) == 1
            results.append('Corrected bill submits with balanced GL; exceptions resolve; retries create no duplicates')
            log.reload()
            changed = json.loads(log.request_json)
            changed['payload'] = correct(payload,170)
            log.request_json = json.dumps(changed)
            denied(log.save)
            results.append('Posted bill payload changes blocked')
            for doctype in ('POS Accepted Transaction','POS Settlement Allocation','POS Settlement Exception'):
                original, transaction = create(doctype.split()[-1].lower())
                name = transaction.name if doctype=='POS Accepted Transaction' else frappe.db.get_value(doctype, {'transaction':transaction.name}, 'name')
                form = frappe.get_doc(doctype,name)
                form.correction_payload_json = json.dumps(correct(original,190))
                form.correction_reason = 'Correct through '+doctype
                # Desk submits JSON strings for dates and datetimes.
                form = frappe.get_doc(json.loads(form.as_json()))
                form.save()
                transaction.reload()
                assert admin.effective_payload(transaction)['grand_total']==190
                assert frappe.db.get_value('POS Settlement Allocation', {'transaction':transaction.name}, 'requested_amount')==40
                outcome = admin.retry_posting(doctype,name)
                assert outcome['status']=='Reconciled', outcome
            results.append('Accepted transaction, allocation and exception forms each save corrections and post')
            original, transaction = create('access')
            log = frappe.get_doc('POS Sync Log', pos_operations.find('POS Sale',original.external_pos_reference).name)
            log.correction_reason = 'Access check'
            log.request_json = json.dumps({**json.loads(log.request_json),'payload':correct(original)})
            for role, should_allow in [('System Manager',False), ('Super Admin',True)]:
                frappe.set_user('Administrator')
                user = frappe.get_doc(dict(doctype='User', email=f'pos-admin-{token}-{int(should_allow)}@example.test',
                    first_name='POS Admin Test', enabled=1, user_type='System User', send_welcome_email=0,
                    roles=[dict(role=role)])).insert(ignore_permissions=True)
                frappe.set_user(user.name)
                log.reload()
                log.correction_reason = 'Role boundary test'
                log.request_json = json.dumps({**json.loads(log.request_json),'payload':correct(original)})
                if should_allow:
                    assert frappe.has_permission('POS Accepted Transaction','write')
                    log.save()
                    assert admin.retry_posting('POS Sync Log',log.name)['status']=='Reconciled'
                else:
                    denied(log.save)
                    denied(lambda: admin.retry_posting('POS Sync Log',log.name))
            frappe.set_user('Administrator')
            log.reload()
            results.append('Real System Manager denied; real Super Admin saves and posts with native permissions')
            log.status = 'Failed'
            denied(log.save)
            results.append('Manual status forgery rejected')
    finally:
        frappe.db.rollback()
        frappe.set_user(original_user)
    return results
