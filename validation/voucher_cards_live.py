"""10,000-card, concurrent spending and Chromium checks; remove only our fixtures."""
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import frappe
from frappe.app import application_with_statics
from frappe.sessions import Session, delete_session
from frappe.utils import add_days, nowdate
from werkzeug.serving import make_server, WSGIRequestHandler

BENCH = Path(__file__).resolve().parents[3]
os.chdir(BENCH / 'sites')
frappe.init(site='retail-test.localhost')
frappe.connect()
frappe.set_user('Administrator')
from retail import voucher_cards as cards
from retail.api import gift_vouchers as api

batch_name = None
print_format_name = None
sid = None
server = None
spent_names = []
started = time.monotonic()
expected_count = int(os.environ.get('RETAIL_CARD_COUNT', '10000'))
try:
    counter = frappe.get_doc('POS Branch Counter', 'Business Demo Branch-COUNTER-1')
    batch = frappe.get_doc(dict(doctype='Voucher Card Batch', title='TEMPORARY voucher regression ' + uuid4().hex,
        company=counter.company, currency=frappe.get_cached_value('Company', counter.company, 'default_currency'),
        voucher_amount=100, card_count=expected_count, valid_from=nowdate(), expiry_date=add_days(nowdate(), 10),
        print_from=1, print_to=2, all_products=1, activate_all_cards=0)).insert()
    batch_name = batch.name
    test_format = frappe.copy_doc(frappe.get_doc('Print Format', 'Voucher Cards - A4'))
    test_format.name = 'TEMPORARY Voucher Design ' + uuid4().hex
    test_format.custom_document_code = None
    test_format.standard = 'No'
    test_format.insert(ignore_permissions=True)
    print_format_name = test_format.name
    if os.environ.get('RETAIL_USE_QUEUE') == '1':
        cards.generate_cards(batch.name)
        frappe.db.commit()
        for _ in range(90):
            frappe.db.rollback()
            if frappe.db.get_value('Voucher Card Batch', batch.name, 'generation_status') == 'Complete':
                break
            time.sleep(.5)
        else:
            raise AssertionError('Long-queue worker did not complete the test batch.')
    else:
        batch.db_set('generation_status', 'Queued')
        frappe.db.commit()
        cards.generate_worker(batch.name, user='Administrator')
    batch.reload()
    count = frappe.db.count('Gift Voucher Ledger', {'voucher_card_batch': batch.name})
    assert count == batch.generated_count == expected_count
    cards.generate_worker(batch.name, user='Administrator')
    assert frappe.db.count('Gift Voucher Ledger', {'voucher_card_batch': batch.name}) == expected_count
    spent_names = frappe.get_all('Gift Voucher Ledger', filters={'voucher_card_batch': batch.name},
        pluck='name', order_by='card_number', limit_page_length=2)
    cards.manage_cards(batch.name, spent_names, 'Activate')
    frappe.db.commit()
    print(json.dumps({'generated_unique_cards': count, 'generation_seconds': round(time.monotonic() - started, 2)}), flush=True)

    def concurrent(request, barrier):
        frappe.init(site='retail-test.localhost', sites_path=str(BENCH / 'sites'))
        frappe.connect()
        frappe.set_user('Administrator')
        try:
            barrier.wait(timeout=20)
            result = api.redeem_gift_voucher(request)
            frappe.db.commit()
            return result
        except frappe.ValidationError as exc:
            frappe.db.rollback()
            return {'rejected': str(exc)}
        finally:
            frappe.destroy()

    base = dict(branch=counter.branch, counter_code=counter.counter_code, amount=60, bill_total=100)
    requests = [{**base, 'voucher_code': spent_names[0], 'external_pos_reference': f'{batch.name}-sale-{i}',
        'redemption_reference': f'{batch.name}-redeem-{i}'} for i in range(2)]
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(concurrent, request, barrier) for request in requests]
        results = [f.result(timeout=40) for f in futures]
    assert sum(bool(r.get('approved')) for r in results) == 1, results
    assert sum('rejected' in r for r in results) == 1, results
    frappe.db.rollback()  # Refresh MariaDB's repeatable-read snapshot after other connections commit.
    assert frappe.db.get_value('Gift Voucher Ledger', spent_names[0], 'balance_amount') == 40
    request = {**base, 'voucher_code': spent_names[1], 'external_pos_reference': f'{batch.name}-same-sale',
        'redemption_reference': f'{batch.name}-same-redeem'}
    barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(concurrent, request, barrier) for _ in range(2)]
        results = [f.result(timeout=40) for f in futures]
    assert sum(bool(r.get('duplicate')) for r in results) == 1, results
    frappe.db.rollback()
    assert frappe.db.get_value('Gift Voucher Ledger', spent_names[1], 'balance_amount') == 40
    print(json.dumps({'concurrent_overspend_blocked': True, 'concurrent_retry_debits_once': True}), flush=True)
    frappe.db.rollback()
    frappe.local.request = frappe._dict(cookies={})
    frappe.local.request_ip = '127.0.0.1'
    frappe.local.form_dict = frappe._dict()
    session = Session(user='Administrator', user_type='System User', full_name='Administrator')
    sid = session.sid
    frappe.db.commit()

    class Quiet(WSGIRequestHandler):
        def log(self, *args, **kwargs):
            pass

    server = make_server('127.0.0.1', 0, application_with_statics(), threaded=True, request_handler=Quiet)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    environment = dict(os.environ, RETAIL_SID=sid, RETAIL_BATCH=batch.name, RETAIL_PRINT_FORMAT=print_format_name,
        RETAIL_EXPECTED_COUNT=str(expected_count), RETAIL_URL='http://retail-test.localhost:' + str(server.server_port),
        LD_LIBRARY_PATH='/tmp/retail-card-browser-libs/usr/lib/x86_64-linux-gnu')
    # Exercise the same wkhtmltopdf renderer used by ERPNext's Download PDF.
    from io import BytesIO
    from pypdf import PdfReader
    from werkzeug.test import EnvironBuilder
    from werkzeug.wrappers import Request
    native_url = 'http://127.0.0.1:' + str(server.server_port)
    previous_host = frappe.local.conf.get('host_name')
    previous_request = frappe.local.request
    try:
        frappe.local.conf.host_name = native_url
        frappe.local.request = Request(EnvironBuilder(path='/printview', base_url=native_url).get_environ())
        native_results = []
        for fmt, expected_pages, expected_width in [('Voucher Cards - A4', 1, 595), ('Voucher Cards - Labels', 2, 243)]:
            pdf = frappe.get_print('Voucher Card Batch', batch.name, print_format=fmt, no_letterhead=True, as_pdf=True)
            Path('/tmp/' + ('voucher-cards-native-labels.pdf' if 'Labels' in fmt else 'voucher-cards-native-a4.pdf')).write_bytes(pdf)
            reader = PdfReader(BytesIO(pdf))
            width = float(reader.pages[0].mediabox.width)
            assert len(reader.pages) == expected_pages, (fmt, len(reader.pages))
            assert abs(width - expected_width) < 2, (fmt, width)
            native_results.append({'format': fmt, 'pages': len(reader.pages), 'width_points': width})
        print(json.dumps({'native_pdf': native_results}), flush=True)
    finally:
        frappe.local.conf.host_name = previous_host
        frappe.local.request = previous_request
    subprocess.run(['/home/adler/.nvm/versions/node/v18.20.8/bin/node',
        str(Path(__file__).with_suffix('.cjs')).replace('_live.cjs', '_browser.cjs')],
        env=environment, timeout=150, check=True)
    print(json.dumps({'browser_passed': True, 'elapsed_seconds': round(time.monotonic() - started, 2)}), flush=True)
finally:
    if server:
        server.shutdown()
    frappe.init(site='retail-test.localhost', force=True)
    frappe.connect()
    frappe.set_user('Administrator')
    if sid:
        delete_session(sid=sid, reason='Voucher regression complete')
    if batch_name:
        # The lifecycle guards correctly forbid deleting real cards. These direct
        # deletes are narrowly scoped to this harness's newly created fixture batch.
        if spent_names:
            frappe.db.delete('POS Sync Log', {'voucher_code': ['in', spent_names]})
        frappe.db.delete('Voucher Card Transaction', {'batch': batch_name})
        frappe.db.delete('Gift Voucher Ledger', {'voucher_card_batch': batch_name})
        frappe.db.delete('Voucher Card Restriction', {'parent': batch_name})
        frappe.db.delete('Version', {'ref_doctype': 'Voucher Card Batch', 'docname': batch_name})
        frappe.db.delete('Voucher Card Batch', {'name': batch_name})
        frappe.clear_document_cache('Voucher Card Batch', batch_name)
    if print_format_name:
        frappe.db.delete('Version', {'ref_doctype': 'Print Format', 'docname': print_format_name})
        frappe.delete_doc('Print Format', print_format_name, ignore_permissions=True, force=True)
    frappe.db.commit()
    print('Temporary voucher batch, all generated cards and test receipts removed.', flush=True)
    frappe.destroy()
