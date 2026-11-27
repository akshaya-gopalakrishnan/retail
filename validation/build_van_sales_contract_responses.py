"""Replace abbreviated contract examples with complete captured response objects."""
import copy
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=Path('/tmp/van-sales-api-responses.json')


def build():
    samples=json.loads(RAW.read_text())
    from van_sales_api_responses import redact
    samples=redact(samples)
    if 'permission_error' in samples:
        samples['permission_error'][0]['request']={'driverid':'OTHER'}
    def entry(key,predicate=lambda r:True,last=False):
        rows=[r for r in samples[key] if predicate(r)]
        if not rows:raise AssertionError(key)
        return rows[-1] if last else rows[0]
    def body(key,predicate=lambda r:True,last=False):return entry(key,predicate,last)['response']
    def msg(key,predicate=lambda r:True,last=False):return body(key,predicate,last)['message']
    ids={}
    def mapid(actual,sample):
        if actual:ids[str(actual)]=sample
    start=msg('start_session')
    master=msg('get_van_master_data',last=True)
    sale=msg('post_sale',lambda r:r['response']['message']['docstatus']==1)
    ret=msg('post_sales_return',lambda r:r['response']['message']['docstatus']==1)
    customer=msg('upsert_customer')['customerid']
    load=msg('get_load_stock',lambda r:bool(r['response']['message']['loads']))['loads'][0]
    sale_doc=msg('get_sales_invoice_data',lambda r:'invoice' in r['response']['message'])['invoice']
    invoice_row=sale_doc['items'][0]
    mapid(start['sessionid'],'VS-2026-00001')
    mapid(master['driverid'],'DRV-00001')
    mapid(master['vanid'],'VAN-00001')
    mapid(master['warehouse'],'Van 01 - N')
    mapid(master['selling_price_list'],'Standard Selling')
    mapid(customer,'C-1')
    mapid(msg('pos_upsert_customer')['customer'],'C-2')
    for packing in master.get('packing_details',[]):
        mapid(packing.get('packing_code'),'I-1-NOS')
    mapid(sale['invoiceid'],'SINV-2026-00001')
    mapid(ret['returnid'],'SINV-RET-2026-00001')
    mapid(invoice_row['name'],'abc123')
    mapid(invoice_row['item_code'],'I-1')
    mapid(load['requestid'],'MAT-MR-2026-00001')
    mapid(load['source_warehouse'],'Loading Stores - N')
    mapid(load['items'][0]['request_itemid'],'MR-ROW-001')
    mapid(msg('confirm_load')['stock_entry'],'MAT-STE-2026-00001')
    mapid(msg('unload_stock')['stock_entry'],'MAT-STE-2026-00002')
    mapid(msg('post_customer_payment',lambda r:r['request'].get('payment_type')!='Pay')['paymentid'],'ACC-PAY-2026-00001')
    mapid(msg('post_customer_payment',lambda r:r['request'].get('payment_type')=='Pay')['paymentid'],'ACC-PAY-2026-00002')
    exp=msg('post_expense')
    mapid(exp['expenseid'],'VEXP-00001')
    mapid(exp['accounting_reference'],'ACC-JV-2026-00001')
    upload=msg('upload_file')
    mapid(upload['name'],'FILE-00001')
    mapid('Van API Sample','Sample Item')
    mapid('Van API Customer','Sample Customer')
    mapid('Van API Driver','Sample Driver')
    mapid('Van API a','Sample Driver')
    mapid('Van API b','Sample Sales User')
    mapid('Van API Fuel','Fuel')
    mapid('Van API Cash','Cash')
    mapid('van-api-a@example.invalid','driver@example.com')
    mapid('van-api-b@example.invalid','other-driver@example.com')
    def substitute(value):
        if isinstance(value,dict):return {k:substitute(v) for k,v in value.items()}
        if isinstance(value,list):return [substitute(v) for v in value]
        if isinstance(value,str):
            if value in ids:return ids[value]
            # Descriptions/remarks may embed the synthetic Item display name.
            value=value.replace('Van API Sample','Sample Item').replace('Van API Customer','Sample Customer')
        return value
    samples=substitute(samples)
    for key,records in samples.items():
        if key.startswith('standard_login'):
            method_name='login'
            path='/api/method/login'
        elif key.startswith('pos_'):
            method_name=key[4:]
            path='/api/method/retail.api.pos_sync.'+method_name
        elif key.startswith('http_'):
            method_name=key[5:]
            prefix='retail.api.van_sales.' if method_name=='get_van_master_data' else 'retail.api.pos_sync.'
            path='/api/method/'+prefix+method_name
        elif key=='upload_file':
            method_name=key
            path='/api/method/upload_file'
        elif key=='permission_error':
            method_name='get_expenses'
            path='/api/method/retail.api.pos_sync.get_expenses'
        elif key=='get_van_warehouse_stock':
            method_name=key
            path='/api/method/retail.van_stock.get_van_warehouse_stock'
        else:
            method_name=key
            path='/api/method/retail.api.van_sales.'+method_name
        for record in records:
            record['url']=path
            record['method']='POST' if key.startswith('http_') and method_name!='get_van_master_data' or key=='permission_error' or not method_name.startswith('get_') else 'GET'
            record['content_type']='multipart/form-data' if key=='upload_file' else 'application/json'

    # Keep the helper readers bound to the now-sanitized sample dictionary.
    contract=ROOT/'VAN_SALES_API_CONTRACT.md'
    text=contract.read_text()
    text=text.replace('Responses below show the relevant fields only.',
        'Responses below show all returned fields for the illustrated request variant. Arrays contain representative sample records; row counts vary. Full ERP documents include the custom fields installed on `retail-test.localhost`. Native warning/verification metadata can vary by site.')
    text=text.replace('Sample IDs and amounts only.','Sample IDs and amounts only. Examples are independent calls, not a transaction sequence.')
    text=text.replace('A van-specific customer assignment extension is still required if that assignment is needed.',
        'For driver assignment, use the implemented van customer API below.')
    def pretty(value):return json.dumps(value,indent=2,ensure_ascii=False)
    def section(heading,fn):
        nonlocal text
        start=text.index(heading+'\n')
        level=len(heading)-len(heading.lstrip('#'))
        match=re.search(r'^#{1,'+str(level)+r'} ',text[start+len(heading)+1:],re.M)
        end=start+len(heading)+1+match.start() if match else len(text)
        text=text[:start]+fn(text[start:end])+text[end:]
    def response(heading,value,additional=''):
        def replace(s):
            extras=('Update response:', 'Login with no active Van Session:', 'No pending loads:',
                'Resume response:', 'Single invoice request: add', 'Draft response (`action:',
                'List returns: omit', 'Draft return response (`action:', 'Session payment list: omit',
                'Refund response (`payment_type:')
            for marker in extras:
                if marker in s:s=s.split(marker,1)[0].rstrip()+'\n\n'
            pattern=r'Response[^\n]*\n\n?```json\n.*?\n```'
            changed,n=re.subn(pattern,lambda _: 'Response:\n```json\n'+pretty(value)+'\n```',s,count=1,flags=re.S)
            assert n==1,heading
            if heading=='### 1. Driver login' and 'Native `sales_person_id`' not in changed:
                changed=changed.rstrip()+'\n\nNative `sales_person_id` / `sales_person_name` may be null. Use `message.driverid` for van requests; Sales Person IDs are separate identifiers.\n'
            return changed.rstrip()+ ('\n\n'+additional.rstrip() if additional else '')+'\n\n' 
        section(heading,replace)
    def example(label,value):return label+'\n```json\n'+pretty(value)+'\n```'
    mappings=[
        ('## Master download without branch/counter','get_van_master_data',lambda r:True,True),
        ('### Master data — available','pos_get_pos_master_data',lambda r:True,False),
        ('### Customer create/update — available','pos_upsert_customer',lambda r:True,False),
        ('### Customer balances — available','pos_get_customer_balances',lambda r:True,False),
        ('### Current van stock — available','get_van_warehouse_stock',lambda r:True,False),
        ('### 1. Driver login','driver_login',lambda r:True,False),
        ('### 2. Driver customer create/update','upsert_customer',lambda r:True,False),
        ('### 3. Load stock requests','get_load_stock',lambda r:bool(r['response']['message']['loads']),False),
        ('### 4. Confirm load','confirm_load',lambda r:True,False),
        ('### 5. Unload stock','unload_stock',lambda r:True,False),
        ('### 6. Start session','start_session',lambda r:True,False),
        ('### 7. Break/resume','update_session_status',lambda r:r['request']['action']=='break',False),
        ('### 8. End session','end_session',lambda r:True,False),
        ('### 9. Active session information','get_active_session',lambda r:r['response']['message']['session'] is not None,False),
        ('### 10. Sales invoice master/details','get_sales_invoice_data',lambda r:'invoices' in r['response']['message'],False),
        ('### 11. Save/submit sale','post_sale',lambda r:r['response']['message']['docstatus']==1,False),
        ('### 12. Sales return master/details','get_sales_return_data',lambda r:'invoiceid' in r['request'],False),
        ('### 13. Save/submit sales return','post_sales_return',lambda r:r['response']['message']['docstatus']==1,False),
        ('### 14. Driver credit customers','get_credit_customers',lambda r:True,False),
        ('### 15. Customer payment invoice details','get_customer_payment_data',lambda r:bool(r['request'].get('customerid')) and bool(r['response']['message']['invoices']),False),
        ('### 16. Customer payment','post_customer_payment',lambda r:r['request'].get('payment_type')!='Pay',False),
        ('### 17. Expense types/details','get_expense_data',lambda r:True,False),
        ('### 18. Upload expense proof — existing upload API','upload_file',lambda r:True,False),
        ('### 19. Expense entry','post_expense',lambda r:True,False),
    ]
    for heading,key,pred,last in mappings:response(heading,body(key,pred,last))
    # Every conditional response shape is shown explicitly.
    # A paid-sale illustration uses the same verified response fields. The
    # isolated captures already verify the native collection helper separately.
    paid=copy.deepcopy(body('post_sale',lambda r:r['response']['message']['docstatus']==1))
    paid['message'].update(invoiceid='SINV-2026-00002',outstanding_amount=0.0,paymentids=['ACC-PAY-2026-00003'])
    paid_request=copy.deepcopy(entry('post_sale',lambda r:r['response']['message']['docstatus']==1)['request'])
    paid_request.update(requestid='VAN01-PAID-SALE-001',invoiceid=None,payments=[dict(mode_of_payment='Cash',amount=105.0)])
    samples['post_sale'].append(dict(method='POST',url='/api/method/retail.api.van_sales.post_sale',
        content_type='application/json',request=paid_request,response=paid,
        example_source='Illustrative paid-sale values; response fields match the implementation.'))
    updated=copy.deepcopy(body('upsert_customer'));updated['message']['action']='Updated'
    section('### 2. Driver customer create/update',lambda s:s+example('Update response:',updated)+'\n\n')
    no_session=copy.deepcopy(body('driver_login'));no_session['message']['sessionid']=None
    section('### 1. Driver login',lambda s:s+example('Login with no active Van Session:',no_session)+'\n\n'+example('When native login requires further authentication (endpoint message):',{'message':{'status':'AuthenticationRequired','detail':'Complete ERP password reset or two-factor authentication.'}})+'\n\nNative two-factor/password-reset flows may also add their own verification fields. Login sets the authentication cookie in HTTP headers.\n\n')
    if 'standard_login_sales_only' in samples:
        section('### 1. Driver login',lambda s:s+'`roles` is the effective ERP role list. The top-level `permissions.sales` and `permissions.van_sales` booleans report enabled/disabled Retail areas using the same role, saved selection and blocked-module rules as Desk. These flags do not grant document Create/Write/Submit rights.\n\nA user with Van Sales disabled can use standard `POST /api/method/login` (`usr`, `pwd`) to receive these flags; `driver_login` still requires Van Sales access and a driver assignment. Full standard-login example:\n```json\n'+pretty(body('standard_login_sales_only'))+'\n```\n\n')
    section('### 3. Load stock requests',lambda s:s+example('No pending loads:',body('get_load_stock',lambda r:not r['response']['message']['loads']))+'\n\n')
    section('### 7. Break/resume',lambda s:s+example('Resume response:',body('update_session_status',lambda r:r['request']['action']=='resume'))+'\n\n')
    section('### 10. Sales invoice master/details',lambda s:s+'Single invoice request: add `invoiceid=SINV-2026-00001`. Full response:\n```json\n'+pretty(body('get_sales_invoice_data',lambda r:'invoice' in r['response']['message']))+'\n```\n\n')
    section('### 11. Save/submit sale',lambda s:s+example('Draft response (`action: "draft"`):',body('post_sale',lambda r:r['response']['message']['docstatus']==0))+'\n\n'+example('Identical submitted-sale retry:',body('post_sale',lambda r:bool(r['response']['message'].get('duplicate'))))+'\n\n')
    section('### 11. Save/submit sale',lambda s:s+example('Paid sale response (example values; `payments` supplied):',paid)+'\n\n')
    section('### 12. Sales return master/details',lambda s:s+example('List returns: omit `invoiceid` and `returnid`:',body('get_sales_return_data',lambda r:'returns' in r['response']['message']))+'\n\nSingle return request: add `returnid=SINV-RET-2026-00001`. Full response:\n```json\n'+pretty(body('get_sales_return_data',lambda r:'return_invoice' in r['response']['message'] and r['response']['message']['return_invoice']['docstatus']==1))+'\n```\n\n')
    section('### 13. Save/submit sales return',lambda s:s+example('Draft return response (`action: "draft"`):',body('post_sales_return',lambda r:r['response']['message']['docstatus']==0))+'\n\n')
    section('### 15. Customer payment invoice details',lambda s:s+example('Session payment list: omit `customerid`:',body('get_customer_payment_data',lambda r:not r['request'].get('customerid')))+'\n\n')
    section('### 16. Customer payment',lambda s:s+example('Refund response (`payment_type: "Pay"`, references contain the return ID):',body('post_customer_payment',lambda r:r['request'].get('payment_type')=='Pay'))+'\n\n')
    # Correct the former illustrative error envelope to the real Frappe body.
    start=text.index('## Proposed error response') if '## Proposed error response' in text else text.index('## Errors')
    end=text.index('## Deployment and validation',start)
    text=text[:start]+'''## Errors and identical retries

Van APIs use standard Frappe error responses with non-2xx HTTP statuses.

Actual permission-error response (HTTP 403), with sample values:
```json
'''+pretty(body('permission_error'))+'''
```

Validation errors usually use HTTP 417 with `exception`, `exc_type`, and optional `exc` / `_server_messages` diagnostic fields. Those native diagnostics vary with the error and site configuration.

For every posting endpoint, an identical successful retry returns every original response field plus `message.duplicate: true`; it does not post again. An example is included under Save/submit sale. Read endpoints return empty arrays when no rows match, while keeping the same remaining fields. No active session returns `{"message":{"status":"Success","session":null}}`.

Sales, return and unload rows accept `batch_no` and newline-separated `serial_no`. Batch/serial tracked stock must include the required ERP tracking details.

## Download all full examples

[VAN_SALES_API_RESPONSES.json](VAN_SALES_API_RESPONSES.json) contains complete request/response pairs, including list/detail, draft/submitted, empty and retry cases, plus a labeled paid-sale illustration. Compatibility routes return exactly the same bodies as their canonical van endpoints; the captured app aliases are also included in this file. Authentication headers and cookies are not body fields. The values are sanitized samples; no real credentials or PIN hashes are included.

'''+text[end:]
    text=text.replace('/private/files/fuel-receipt.jpg',upload['file_url'])
    # Format every request example as readable JSON too.
    text=re.sub(r'```json\n(.*?)\n```',lambda m:'```json\n'+pretty(json.loads(m.group(1)))+'\n```',text,flags=re.S)
    contract.write_text(text)
    (ROOT/'VAN_SALES_API_RESPONSES.json').write_text(pretty(samples)+'\n')
    print(f'{len(samples)} endpoint/alias groups; {sum(map(len,samples.values()))} complete request/response pairs; {len(text.splitlines())} contract lines')


if __name__=='__main__':build()
