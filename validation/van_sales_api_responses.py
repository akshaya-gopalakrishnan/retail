"""Generate complete, sanitized response examples in a disposable DB.

Run from bench root with env/bin/python. Only /tmp/van-sales-api-responses.json
is exported; the observer never writes to the source ERP site.
"""
import importlib.util
import json
from pathlib import Path
import frappe

CAPTURES = {}


def sample_catalog(message):
    """Keep representative rows, preserving every field and nested object."""
    sample_code = next((r['item_code'] for r in message.get('items', []) if r.get('item_name')=='Van API Sample'),None)
    for key in ('items','packing_details','item_barcodes','item_prices'):
        if sample_code:
            message[key]=[r for r in message.get(key,[]) if r.get('item_code')==sample_code]
    if 'customers' in message:
        message['customers']=[r for r in message['customers'] if r.get('customer_name')=='Van API Customer']
    if 'modes_of_payment' in message:
        modes=[r for r in message['modes_of_payment'] if isinstance(r,dict) and r.get('name')=='Van API Cash']
        if modes:message['modes_of_payment']=modes
    # Snapshots may contain many business records. One complete row per array
    # illustrates the schema without exporting the user's full catalog.
    for key in ('operators','counters','promo_prices','buy_x_get_y_promotions','gift_voucher_promotions','scale_barcode_formats'):
        if key in message:message[key]=message[key][:1]


def redact(value, key=''):
    if isinstance(value,dict):
        if key=='bill_format':
            value=dict(value,address='Dubai, UAE',email_id='sales@example.com',phone_number='971500000000',
                tax_id='100000000000001',h1='Sample Company',h2='Dubai, UAE')
        return {k:redact(v,k) for k,v in value.items()}
    if isinstance(value,list):return [redact(v,key) for v in value]
    lowered=key.lower()
    if value and any(word in lowered for word in ('password','secret','quick_pin','api_key','access_token','refresh_token','voucher_code','card_number','pin_code')):
        return '<sample '+key+'>'
    if isinstance(value,str) and value and key in {'email','email_id','mobile_no','phone','phone_number','tax_id','address_display'}:
        return {'email':'customer@example.com','email_id':'sales@example.com','mobile_no':'971500000000',
            'phone':'971500000000','phone_number':'971500000000','tax_id':'100000000000001',
            'address_display':'Dubai, UAE'}[key]
    # Only sample identities appear in published documentation.
    if isinstance(value,str) and key in {'employee_name','user_id','employee_number','cell_number','pos_login_id','login_id','integration_user'}:
        return 'sample@example.com' if ('user' in key or '@' in value) else 'SAMPLE-001'
    return value


def record(name,request,response,*,http=False):
    envelope=json.loads(frappe.as_json(response if http else dict(message=response)))
    if isinstance(envelope.get('message'),dict) and 'items' in envelope['message'] and 'packing_details' in envelope['message']:
        sample_catalog(envelope['message'])
    entry=redact(dict(request=json.loads(frappe.as_json(request)),response=envelope))
    CAPTURES.setdefault(name,[]).append(entry)
    Path('/tmp/van-sales-api-responses.json').write_text(json.dumps(CAPTURES,indent=2,ensure_ascii=False)+'\n')


if __name__=='__main__':
    folder=Path(__file__).resolve().parent
    def load(name,filename):
        spec=importlib.util.spec_from_file_location(name,folder/filename)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    validation=load('van_response_scenario','van_sales_api_isolated.py')
    validation.RESPONSE_OBSERVER=record
    harness=load('van_response_harness','product_conversion_isolated.py')
    harness.scenario=validation.scenario
    harness.main()
    print('Complete sanitized examples: /tmp/van-sales-api-responses.json')
