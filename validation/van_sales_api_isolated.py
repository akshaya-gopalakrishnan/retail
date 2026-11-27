"""Validate van stock/accounting in a disposable DB/Redis clone of retail-test.localhost.

Run from bench root: env/bin/python apps/retail/validation/van_sales_api_isolated.py
The shared harness reads the source DB once, then uses only an isolated Unix socket.
"""
import importlib.util
import json
from pathlib import Path
import frappe


# Optional documentation observer. Default validation behavior is unchanged.
RESPONSE_OBSERVER = None


def observe(name, request, response, *, http=False):
    if RESPONSE_OBSERVER:
        RESPONSE_OBSERVER(name, request, response, http=http)


def scenario():
    from frappe.utils import nowdate
    from retail.api import van_sales as api
    from retail.van_api_setup import install
    print(install(), flush=True)
    from retail.patches.sync_log_navigation import execute as install_log_navigation
    install_log_navigation()
    check_pos_catalog_parity()
    company = frappe.db.get_value('Company', {}, 'name')
    currency = frappe.db.get_value('Company', company, 'default_currency')
    cost_center = frappe.db.get_value('Company', company, 'cost_center')
    cash = frappe.db.get_value('Account', dict(company=company, account_type='Cash', is_group=0, disabled=0), 'name')
    expense = frappe.db.get_value('Account', dict(company=company, root_type='Expense', is_group=0, disabled=0), 'name')
    assert company and cost_center and cash and expense
    for suffix in ('a', 'b'):
        user = frappe.get_doc(dict(doctype='User', email=f'van-api-{suffix}@example.invalid', first_name='Van API '+suffix,
            enabled=1, user_type='System User', send_welcome_email=0, roles=[dict(role='Van Sales User')]))
        user.insert(ignore_permissions=True)
    driver = frappe.get_doc(dict(doctype='Driver', full_name='Van API Driver', status='Active', custom_van_user='van-api-a@example.invalid')).insert()
    other_driver = frappe.get_doc(dict(doctype='Driver', full_name='Other Van API Driver', status='Active', custom_van_user='van-api-b@example.invalid')).insert()
    warehouse = frappe.get_doc(dict(doctype='Warehouse', warehouse_name='Van API Mobile', company=company)).insert().name
    source = frappe.get_doc(dict(doctype='Warehouse', warehouse_name='Van API Source', company=company)).insert().name
    price_list = frappe.get_doc(dict(doctype='Price List', price_list_name='Van API Selling', selling=1, enabled=1, currency=currency)).insert().name
    van = frappe.get_doc(dict(doctype='Van Fleet', van_registration_no='VAN-API-TEST', vehicle_name='Van API Test',
        van_warehouse=warehouse, default_driver=driver.name, vehicle_status='Active', custom_source_warehouse=source,
        custom_cost_center=cost_center, custom_selling_price_list=price_list)).insert()
    draft = frappe.get_doc(dict(doctype='Van Session', driver=driver.name, van=van.name, van_warehouse=warehouse,
        custom_salesperson='van-api-a@example.invalid', session_date=nowdate(), status='Draft')).insert()
    # Another driver's session is used for authorization tests.
    other_wh = frappe.get_doc(dict(doctype='Warehouse', warehouse_name='Van API Other', company=company)).insert().name
    other_van = frappe.get_doc(dict(doctype='Van Fleet', van_registration_no='VAN-API-OTHER', vehicle_name='Other Van',
        van_warehouse=other_wh, default_driver=other_driver.name, vehicle_status='Active')).insert()
    other_session = frappe.get_doc(dict(doctype='Van Session', driver=other_driver.name, van=other_van.name,
        van_warehouse=other_wh, custom_salesperson='van-api-b@example.invalid', session_date=nowdate(), status='Draft')).insert()
    group = frappe.db.get_value('Item Group', {'is_group':0}, 'name')
    item = frappe.get_doc(dict(doctype='Item', item_code='Van API Sample', item_name='Van API Sample', item_group=group,
        stock_uom='Nos', is_stock_item=1, is_sales_item=1, custom_purchase_rate_entry=8,
        custom_purchase_rate_includes_vat=0)).insert()
    receipt = frappe.new_doc('Stock Entry')
    receipt.update(dict(company=company, stock_entry_type='Material Receipt', purpose='Material Receipt', posting_date=nowdate()))
    receipt.append('items',dict(item_code=item.name, qty=100, uom='Nos', t_warehouse=source, conversion_factor=1,
        basic_rate=8, set_basic_rate_manually=1))
    receipt.insert(); receipt.submit()
    mode = frappe.get_doc(dict(doctype='Mode of Payment', mode_of_payment='Van API Cash', type='Cash', enabled=1,
        accounts=[dict(company=company,default_account=cash)])).insert().name
    kind = frappe.get_doc(dict(doctype='Van Expense Type',expense_type='Van API Fuel',company=company,
        expense_account=expense,enabled=1,proof_required=0)).insert()
    def call(fn, requestid=None, **values):
        p=dict(driverid=driver.name)
        p.update(values)
        if requestid:p['requestid']=requestid
        result=fn(data=p)
        observe(fn.__name__,p,result)
        return result
    def denied(fn, **values):
        try:call(fn, **values)
        except (frappe.PermissionError,frappe.ValidationError):return
        raise AssertionError('Unauthorized/invalid operation was accepted')
    frappe.set_user('van-api-a@example.invalid')
    start = call(api.start_session,'start', sessionid=draft.name, opening_balance=100)
    assert start['sessionid']==draft.name, start
    assert call(api.start_session,'start',sessionid=draft.name,opening_balance=100)['duplicate']
    denied(api.start_session,requestid='start',sessionid=draft.name,opening_balance=200)
    denied(api.get_active_session,sessionid=other_session.name)
    denied(api.get_active_session,driverid=other_driver.name)
    if RESPONSE_OBSERVER:call(api.get_active_session)
    customer_group=frappe.db.get_value('Customer Group', {'is_group':0}, 'name')
    territory=frappe.db.get_value('Territory', {'is_group':0}, 'name')
    customer = call(api.upsert_customer,'customer', external_customer_id='van-app-1', customer_name='Van API Customer',
        customer_group=customer_group,territory=territory)['customerid']
    masters = call(api.get_van_master_data)
    assert masters['warehouse']==warehouse and any(r['item_code']==item.name for r in masters['items'])
    assert [c.name for c in masters['customers']]==[customer], masters['customers']
    assert mode in [r['name'] for r in masters['modes_of_payment']]
    assert call(api.update_session_status,'break', action='break')['activity_status']=='Break'
    assert call(api.update_session_status,'resume', action='resume')['activity_status']=='Active'
    # Create the assigned material request through the standard ERP controller.
    request=frappe.new_doc('Material Request')
    request.update(dict(company=company,material_request_type='Material Transfer', custom_is_van_stock_request=1,
        custom_van_session=draft.name,custom_van_request_type='Loading',schedule_date=nowdate()))
    request.append('items',dict(item_code=item.name,qty=20,uom='Nos',warehouse=warehouse,from_warehouse=source,schedule_date=nowdate()))
    request.insert();request.submit()
    loads=call(api.get_load_stock)['loads']
    assert any(r['requestid']==request.name for r in loads),loads
    loaded=call(api.confirm_load,'load',load_requestid=request.name)
    assert loaded['docstatus']==1
    assert call(api.confirm_load,'load',load_requestid=request.name)['duplicate']
    denied(api.confirm_load,requestid='load-again',load_requestid=request.name)
    assert not call(api.get_load_stock)['loads']
    assert frappe.db.get_value('Bin',{'warehouse':warehouse,'item_code':item.name},'actual_qty')==20
    print('Load transfer and duplicate-load protection passed.',flush=True)
    count=frappe.db.count('Sales Invoice',{'custom_van_session':draft.name})
    denied(api.post_sale,requestid='bad-paid-sale',customerid=customer,action='submit',
        items=[dict(item_code=item.name,qty=1,uom='Nos',rate=10)],payments=[dict(mode_of_payment=mode,amount=999)])
    assert frappe.db.count('Sales Invoice',{'custom_van_session':draft.name})==count
    assert frappe.db.get_value('Bin',{'warehouse':warehouse,'item_code':item.name},'actual_qty')==20
    sale_args=dict(customerid=customer,items=[dict(item_code=item.name,qty=10,uom='Nos',rate=10.5,rate_includes_vat=1)],action='draft')
    saved=call(api.post_sale,'sale-draft',**sale_args)
    assert saved['docstatus']==0
    discount_args=dict(sale_args,invoiceid=saved['invoiceid'],apply_discount_on='Grand Total')
    discounted=call(api.post_sale,'sale-discount-percent',**discount_args,additional_discount_percentage=10)
    assert abs(discounted['grand_total']-94.5)<0.001,discounted
    discounted=call(api.post_sale,'sale-discount-amount',**discount_args,discount_amount=5)
    assert abs(discounted['grand_total']-100)<0.001,discounted
    assert call(api.post_sale,'sale-discount-amount',**discount_args,discount_amount=5)['duplicate']
    for invalid in (dict(additional_discount_percentage=101),dict(discount_amount=-1),
            dict(discount_amount=1,additional_discount_percentage=10),dict(discount_amount=999)):
        denied(api.post_sale,requestid='bad-discount-'+str(invalid),**discount_args,**invalid)
    call(api.post_sale,'sale-clear-discount',**discount_args,discount_amount=0)
    print('Invoice percentage/amount discounts, switching, clearing, retry and invalid values passed.',flush=True)
    sale_args.update(action='submit',invoiceid=saved['invoiceid'])
    sale=call(api.post_sale,'sale-submit',**sale_args)
    assert sale['docstatus']==1 and sale['grand_total']==105,sale
    assert call(api.post_sale,'sale-submit',**sale_args)['duplicate']
    invoice=frappe.get_doc('Sales Invoice',sale['invoiceid'])
    assert invoice.custom_van_session==draft.name and invoice.items[0].warehouse==warehouse
    print('Draft/submit sale and duplicate retry passed.',flush=True)
    if RESPONSE_OBSERVER:
        call(api.get_sales_invoice_data)
        call(api.get_sales_invoice_data,invoiceid=invoice.name)
    return_args=dict(invoiceid=invoice.name,items=[dict(invoice_itemid=invoice.items[0].name,item_code=item.name,qty=-1,uom='Nos')])
    return_draft=call(api.post_sales_return,'return-draft',action='draft',**return_args)
    assert return_draft['docstatus']==0
    fetched=call(api.get_sales_return_data,returnid=return_draft['returnid'])['return_invoice']
    assert fetched['docstatus']==0 and fetched['return_against']==invoice.name
    returned=call(api.post_sales_return,'return',returnid=return_draft['returnid'],action='submit',**return_args)
    assert call(api.post_sales_return,'return',returnid=return_draft['returnid'],action='submit',**return_args)['duplicate']
    assert returned['docstatus']==1 and returned['grand_total']==-10.5,returned
    details=call(api.get_sales_return_data,invoiceid=invoice.name)
    assert details['items'][0]['returnable_qty']==9,details
    denied(api.post_sales_return,requestid='over-return',invoiceid=invoice.name,
        items=[dict(invoice_itemid=invoice.items[0].name,item_code=item.name,qty=-10,uom='Nos')])
    # Reference outstanding, not bill total, determines what can be collected.
    if RESPONSE_OBSERVER:
        call(api.get_sales_return_data)
        call(api.get_sales_return_data,returnid=returned['returnid'])
        call(api.get_credit_customers)
        call(api.get_customer_payment_data,customerid=customer)
    outstanding=frappe.db.get_value('Sales Invoice',invoice.name,'outstanding_amount')
    denied(api.post_customer_payment,requestid='no-ledger-access',customerid=customer,mode_of_payment=mode,amount=outstanding,
        references=[dict(invoiceid=invoice.name,allocated_amount=outstanding)])
    exp=call(api.post_expense,'expense',expense_type=kind.name,amount=5,mode_of_payment=mode,remarks='Fuel')
    assert exp['docstatus']==1 and exp['accounting_reference'],exp
    assert call(api.post_expense,'expense',expense_type=kind.name,amount=5,mode_of_payment=mode,remarks='Fuel')['duplicate']
    # This is a synthetic user in the disposable DB, never a hosted user/role change.
    frappe.set_user('Administrator')
    fixture_user=frappe.get_doc('User','van-api-a@example.invalid')
    fixture_user.append('roles',dict(role='Accounts User'))
    fixture_user.save(ignore_permissions=True)
    frappe.set_user('van-api-a@example.invalid')
    payment=call(api.post_customer_payment,'payment',customerid=customer,mode_of_payment=mode,amount=outstanding,
        references=[dict(invoiceid=invoice.name,allocated_amount=outstanding)])
    assert payment['docstatus']==1,payment
    assert call(api.post_customer_payment,'payment',customerid=customer,mode_of_payment=mode,amount=outstanding,
        references=[dict(invoiceid=invoice.name,allocated_amount=outstanding)])['duplicate']
    assert not call(api.get_customer_payment_data,customerid=customer)['invoices']
    credit=frappe.db.get_value('Sales Invoice',returned['returnid'],'outstanding_amount')
    assert credit==-10.5,credit
    refund=call(api.post_customer_payment,'refund',customerid=customer,mode_of_payment=mode,amount=10.5,
        payment_type='Pay',references=[dict(invoiceid=returned['returnid'],allocated_amount=10.5)])
    assert refund['docstatus']==1,refund
    assert frappe.db.get_value('Sales Invoice',returned['returnid'],'outstanding_amount')==0
    print('Partial return, over-return rejection, collection and refund passed.',flush=True)
    unloaded=call(api.unload_stock,'unload',target_warehouse=source,items=[dict(item_code=item.name,qty=5,uom='Nos')])
    assert unloaded['docstatus']==1,unloaded
    assert frappe.db.get_value('Bin',{'warehouse':warehouse,'item_code':item.name},'actual_qty')==6
    assert frappe.db.get_value('Bin',{'warehouse':source,'item_code':item.name},'actual_qty')==85
    print('Expense GL and unloading passed.',flush=True)
    if RESPONSE_OBSERVER:
        frappe.set_user('Administrator')
        # Populate optional catalog sections using only the synthetic sample item.
        item.append('barcodes',dict(barcode='VAN-SAMPLE-001',uom='Nos'))
        item.append('custom_retail_packing_detail',dict(packing_name='Each',uom='Nos',
            conversion_factor=1,barcode='VAN-SAMPLE-001',selling_rate=10.5))
        item.custom_sales_rate_entry=10.5
        item.custom_sales_rate_includes_vat=1
        item.save()
        frappe.get_doc(dict(doctype='Item Price',item_code=item.name,price_list=price_list,
            currency=currency,uom='Nos',price_list_rate=10.5)).insert()
        frappe.set_user('van-api-a@example.invalid')
        call(api.get_van_master_data)
        call(api.get_expense_data)
        call(api.get_customer_payment_data)
        from retail.van_stock import get_van_warehouse_stock
        observe('get_van_warehouse_stock',dict(warehouse=warehouse),get_van_warehouse_stock(warehouse))
        frappe.set_user('Administrator')
        from retail.api import pos_sync
        counter=frappe.db.get_value('POS Branch Counter',dict(is_active=1,allow_offline_sync=1),['branch','counter_code'],as_dict=True)
        observe('pos_get_pos_master_data',counter,pos_sync.get_pos_master_data(**counter))
        pos_customer_args=dict(external_customer_id='VAN-DOC-POS-CUSTOMER',**counter,
            customer_name='POS Sample Customer',customer_group=customer_group,territory=territory)
        observe('pos_upsert_customer',pos_customer_args,pos_sync.upsert_customer(**pos_customer_args))
        observe('pos_get_customer_balances',dict(company=company,customer=customer,include_zero_balance=1),
            pos_sync.get_customer_balances(company=company,customer=customer,include_zero_balance=1))
        frappe.set_user('van-api-a@example.invalid')
    # Synthetic test users have no paid license seats. Stub ONLY the seat check;
    # keep native password authentication, module gates and document permissions real.
    # No production licensing code, settings, protected state or seats are changed.
    from unittest.mock import patch
    with patch('retail.licensing.enforcement.check_user') as license_check:
        http_checks(driver.name,warehouse,draft.name,customer)
        assert any(c.args==('van-api-a@example.invalid',) for c in license_check.call_args_list)

    closed=call(api.end_session,'close',closing_cash=187.5,collection_details=[dict(mode_of_payment=mode,amount=outstanding)])
    assert closed['session_status']=='Closed'
    assert call(api.end_session,'close',closing_cash=187.5,collection_details=[dict(mode_of_payment=mode,amount=outstanding)])['duplicate']
    if RESPONSE_OBSERVER:call(api.get_active_session)
    denied(api.post_expense,requestid='closed-expense',expense_type=kind.name,amount=5,mode_of_payment=mode)
    frappe.set_user('van-api-b@example.invalid')
    try:api.get_sales_invoice_data(data=dict(driverid=driver.name,sessionid=draft.name))
    except frappe.PermissionError:pass
    else:raise AssertionError('Cross-driver access accepted')
    frappe.set_user('Administrator')
    for dt,name in [('Sales Invoice',invoice.name),('Sales Invoice',returned['returnid']),('Payment Entry',payment['paymentid']),('Journal Entry',exp['accounting_reference'])]:
        gl=frappe.get_all('GL Entry',filters=dict(voucher_type=dt,voucher_no=name,is_cancelled=0),fields=['debit','credit'])
        assert gl and abs(sum(r.debit-r.credit for r in gl))<.001,(dt,name,gl)
    print(json.dumps(dict(session=start, sale=sale, returned=returned, payment=payment, expense=exp, unloaded=unloaded,
        closed=closed, van_stock=6, source_stock=85, checks='native GL/SLE, ownership, draft/submit, retries, over-return, close protection')),flush=True)

def check_pos_catalog_parity():
    import subprocess,types
    from retail.api import pos_sync
    counter=frappe.db.get_value('POS Branch Counter',dict(is_active=1,allow_offline_sync=1),['branch','counter_code'],as_dict=True)
    assert counter, 'A configured POS counter is needed for backward compatibility proof.'
    source=subprocess.check_output(['git','show','HEAD:retail/api/pos_sync.py'],cwd=Path(frappe.get_app_path('retail')).parent,text=True)
    baseline=types.ModuleType('retail._van_catalog_baseline')
    exec(compile(source,'<existing POS baseline>','exec'),baseline.__dict__)
    old=baseline.get_pos_master_data(**counter)
    new=pos_sync.get_pos_master_data(**counter)
    assert old.keys()==new.keys(),(old.keys(),new.keys())
    for field in ('counter','tax_config','bill_format','items','item_barcodes','packing_details','item_prices','scale_barcode_formats'):
        assert old[field]==new[field],field
    print('Existing POS full master: response keys and complete catalog match the pre-change implementation.',flush=True)


def http_checks(driver, warehouse, session, customer):
    """Exercise the real WSGI auth/dispatch, using a separate temporary sites directory."""
    import shutil
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    import frappe.app
    from frappe.utils.password import update_password
    from frappe.utils import nowdate
    root=Path(frappe.db.socket).parent/'http-sites'
    site='retail-test.localhost'
    (root/site/'logs').mkdir(parents=True)
    (root/'logs').mkdir()
    for folder in ('private/files','public/files'):(root/site/folder).mkdir(parents=True)
    shutil.copy(Path(frappe.local.sites_path)/'apps.txt',root/'apps.txt')
    assert frappe.db.sql('select database()')[0][0]=='conversion_validation'
    assert str(frappe.db.socket).startswith('/tmp/product-conversion-isolated-')
    frappe.db.commit()
    isolated_password=frappe.generate_hash(length=30)
    # Temporary DB login for Frappe's HTTP connect(); confined to the clone schema.
    frappe.db.sql("CREATE USER 'conversion_validation'@'localhost' IDENTIFIED BY %s",isolated_password)
    frappe.db.sql("GRANT ALL ON conversion_validation.* TO 'conversion_validation'@'localhost'")
    config=dict(frappe.conf)
    config.update(db_user='conversion_validation',db_password=isolated_password,db_host=None,db_socket=frappe.db.socket,
        developer_mode=0,maintenance_mode=0,mute_emails=True)
    (root/site/'site_config.json').write_text(json.dumps(config))
    (root/site/'site_config.json').chmod(0o600)
    frappe.set_user('Administrator')
    user=frappe.get_doc('User','van-api-a@example.invalid')
    user.api_key=frappe.generate_hash(length=20)
    secret=frappe.generate_hash(length=24)
    user.api_secret=secret
    user.save(ignore_permissions=True)
    password=frappe.generate_hash(length=24)
    update_password(user.name,password)
    key=user.api_key
    # A second clone-only user has both roles but Van Sales disabled in the
    # saved Retail selection, so standard login must report a false van flag.
    sales_user=frappe.get_doc('User','van-api-b@example.invalid')
    sales_user.append('roles',dict(role='Sales User'))
    from retail.sidebar_registry import registry
    sales_group=next(g for g in registry() if g['workspace']=='Sales')
    sales_entry_id=next(c['id'] for c in sales_group['children'] if c['workspace']=='Sales Orders')
    sales_user.retail_sidebar_permissions=json.dumps(dict(version=1,allowed=[sales_entry_id]))
    sales_user.save(ignore_permissions=True)
    sales_password=frappe.generate_hash(length=24)
    update_password(sales_user.name,sales_password)
    frappe.db.commit()
    frappe.destroy()
    frappe.app._sites_path=str(root)
    frappe.app._site=site
    client=Client(frappe.app.application,Response)
    login=client.post('/api/method/retail.api.van_sales.driver_login',json=dict(userid=user.name,password=password),base_url='http://retail-test.localhost')
    assert login.status_code==200,(login.status_code,login.get_json())
    observe('driver_login',dict(userid=user.name,password='<password>'),login.get_json(),http=True)
    assert 'Van Sales User' in login.get_json()['roles'],login.get_json()
    assert login.get_json()['permissions']==dict(sales=False,van_sales=True),login.get_json()
    other_client=Client(frappe.app.application,Response)
    normal=other_client.post('/api/method/login',json=dict(usr=sales_user.name,pwd=sales_password),base_url='http://retail-test.localhost')
    assert normal.status_code==200,(normal.status_code,normal.get_json())
    assert {'Sales User','Van Sales User'}.issubset(normal.get_json()['roles'])
    assert normal.get_json()['permissions']==dict(sales=True,van_sales=False),normal.get_json()
    observe('standard_login_sales_only',dict(usr=sales_user.name,pwd='<password>'),normal.get_json(),http=True)
    body=login.get_json()['message']
    assert body['driverid']==driver and body['sessionid']==session,body
    masters=client.get('/api/method/retail.api.van_sales.get_van_master_data',base_url='http://retail-test.localhost')
    assert masters.status_code==200,(masters.status_code,masters.get_json())
    assert masters.get_json()['message']['warehouse']==warehouse
    observe('http_get_van_master_data',{},masters.get_json(),http=True)
    token_client=Client(frappe.app.application,Response)
    headers={'Authorization':f'token {key}:{secret}'}
    for method in ('get_sales_invoices','get_sales_returns','get_customer_payments','get_expenses'):
        response=token_client.post('/api/method/retail.api.pos_sync.'+method,headers=headers,
            json=dict(driver_id=driver,session_id='',warehouse=warehouse),base_url='http://retail-test.localhost')
        assert response.status_code==200,(method,response.status_code,response.get_json())
        assert response.get_json()['message']['status']=='Success'
        assert 'roles' not in response.get_json() and 'permissions' not in response.get_json(),response.get_json()
        observe('http_'+method,dict(driver_id=driver,session_id='',warehouse=warehouse),response.get_json(),http=True)
    from io import BytesIO
    uploaded=token_client.post('/api/method/upload_file',headers=headers,
        data={'is_private':'1','file':(BytesIO(b'Van API receipt verification'),'receipt.txt')},base_url='http://retail-test.localhost')
    assert uploaded.status_code==200,(uploaded.status_code,uploaded.get_json())
    observe('upload_file',dict(is_private=1,file='<receipt file bytes>'),uploaded.get_json(),http=True)
    proof=uploaded.get_json()['message']['file_url']
    assert proof.startswith('/private/files/'),proof
    proved=token_client.post('/api/method/retail.api.van_sales.post_expense',headers=headers,
        json=dict(requestid='http-proof-expense',driverid=driver,expense_type='Van API Fuel',amount=2,
            mode_of_payment='Van API Cash',proof_url=proof,remarks='Uploaded receipt'),base_url='http://retail-test.localhost')
    assert proved.status_code==200,(proved.status_code,proved.get_json())
    assert proved.get_json()['message']['docstatus']==1
    replay=token_client.post('/api/method/retail.api.pos_sync.start_session',headers=headers,
        json=dict(driverid=driver,sessionid=session,opening_balance=100,requestid='start'),base_url='http://retail-test.localhost')
    assert replay.status_code==200 and replay.get_json()['message']['duplicate'],replay.get_json()
    denied=token_client.post('/api/method/retail.api.pos_sync.get_expenses',headers=headers,
        json=dict(driverid='OTHER'),base_url='http://retail-test.localhost')
    assert denied.status_code==403,(denied.status_code,denied.get_json())
    observe('permission_error',{},denied.get_json(),http=True)
    noauth=Client(frappe.app.application,Response).get('/api/method/retail.api.van_sales.get_van_master_data',base_url='http://retail-test.localhost')
    assert noauth.status_code in (401,403),noauth.status_code
    # The exact same site name now points exclusively to the disposable socket.
    frappe.init(site=site,sites_path=str(root),force=True)
    frappe.connect()
    assert frappe.db.sql('select database()')[0][0]=='conversion_validation'
    frappe.set_user('van-api-a@example.invalid')
    logs=frappe.get_all('Van Sales Sync Log',fields=['operation','status','http_status','request_json'],limit_page_length=0)
    assert any(r.status=='Failed' and r.http_status==403 for r in logs),logs
    assert any(r.operation=='start_session' and r.status=='Duplicate' for r in logs),logs
    login_logs=[r for r in logs if r.operation=='driver_login']
    assert login_logs and json.loads(login_logs[0].request_json)['password']=='[REDACTED]'
    assert not any(r.operation=='login' for r in logs)
    print('HTTP: login, cookies/tokens, compatibility, proof upload and sanitized success/failure/retry Van Sync Logs passed.',flush=True)


if __name__=='__main__':
    spec=importlib.util.spec_from_file_location('isolated_harness',Path(__file__).with_name('product_conversion_isolated.py'))
    harness=importlib.util.module_from_spec(spec);spec.loader.exec_module(harness)
    harness.scenario=scenario
    harness.main()
