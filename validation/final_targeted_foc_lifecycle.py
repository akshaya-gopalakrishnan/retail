import json, traceback
from pathlib import Path
import frappe, retail
from frappe.utils import flt, nowdate
from retail.domains.foc import prepare_foc_items
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
frappe.init(site='retail-test.localhost',sites_path='/home/adler/frappe-bench/sites')
frappe.connect(); frappe.set_user('Administrator'); frappe.flags.in_test=True
result={'source':retail.__file__,'tests':[]}
def equal(label, actual, expected, precision=6):
    if round(flt(actual), precision) != round(flt(expected), precision):
        raise AssertionError(f'{label}: actual={actual!r}, expected={expected!r}, precision={precision}')


def ledger(doc):
    sle = frappe.get_all('Stock Ledger Entry', filters={
        'voucher_type': doc.doctype, 'voucher_no': doc.name, 'is_cancelled': 0},
        fields=['name','voucher_detail_no','actual_qty','stock_value_difference','incoming_rate','stock_queue'],
        order_by='creation asc')
    gl = frappe.db.sql('''select g.name,g.account,a.account_type,g.debit,g.credit
        from `tabGL Entry` g join `tabAccount` a on a.name=g.account
        where g.voucher_type=%s and g.voucher_no=%s and g.is_cancelled=0''',
        (doc.doctype, doc.name), as_dict=True)
    keys = [(g.account, g.debit, g.credit) for g in gl]
    assert len(keys) == len(set(keys)), 'Duplicate active GL entries'
    equal('balanced GL', sum(g.debit-g.credit for g in gl), 0)
    assert len(gl) == (4 if doc.doctype == 'Sales Invoice' else 2), 'Missing/extra active GL'
    stock_gl = sum(g.debit-g.credit for g in gl if g.account_type == 'Stock')
    cogs_gl = sum(g.debit-g.credit for g in gl if g.account_type == 'Cost of Goods Sold')
    value = sum(s.stock_value_difference for s in sle)
    details = [s.voucher_detail_no for s in sle]
    assert len(details) == len(set(details)), f'Duplicate SLE detail: {details}'
    assert set(details) == {r.name for r in doc.items}, f'Missing/orphan SLE: {details}'
    equal('SLE value vs stock GL', value, stock_gl)
    data = dict(voucher_type=doc.doctype, voucher=doc.name,
        items=[{k:r.get(k) for k in ('name','qty','custom_foc_qty','custom_foc_parent','rate','stock_qty','base_net_amount')} for r in doc.items],
        sle=sle, gl=gl, received_or_sold_qty=sum(s.actual_qty for s in sle),
        sle_value=value, stock_gl=stock_gl, cogs_gl=cogs_gl)
    if doc.doctype == 'Sales Invoice':
        from retail.retail_app.report.profitability import sales_cost_join, sales_cost_sql, invoice_profitability
        from retail.retail_app.report.daily_profit_report.daily_profit_report import execute
        costs = frappe.db.sql(f'''select sii.name,{sales_cost_sql()} cost from `tabSales Invoice` si
            join `tabSales Invoice Item` sii on sii.parent=si.name {sales_cost_join()}
            where si.name=%s''',doc.name,as_dict=True)
        service = invoice_profitability(doc,{r.name:r.cost for r in costs},vat_accounts=set())
        if doc.get('custom_is_van_sale'):
            from retail.retail_app.report.van_profit_report.van_profit_report import execute
        rows = execute(dict(company=doc.company,from_date=doc.posting_date,to_date=doc.posting_date,
                            sales_invoice=doc.name,group_by='Invoice'))[1]
        report = next(r for r in rows if r.get('sales_group') == doc.name) if not doc.get('custom_is_van_sale') else frappe._dict(cost_amount=sum(flt(r.get('cost_amount')) for r in rows if r.get('item_code') == doc.items[0].item_code))
        data.update(service_cogs=service.cost_amount, report_cogs=report.cost_amount)
        equal('SLE COGS vs expense GL', -value, cogs_gl)
        equal('service COGS', service.cost_amount, -value)
        equal('report COGS', report.cost_amount, -value)
    return data

def sle_rows(doc):
    return frappe.get_all('Stock Ledger Entry', filters={'item_code':doc.items[0].item_code,
        'warehouse':doc.items[0].warehouse, 'voucher_no':doc.name},
        fields=['name','voucher_type','voucher_no','voucher_detail_no','actual_qty',
                'stock_value_difference','is_cancelled','posting_date','posting_time','creation'], order_by='creation asc')

def gl_rows(doc):
    return frappe.db.sql("""select g.name,g.account,a.account_type,g.debit,g.credit,g.is_cancelled,
        g.voucher_type,g.voucher_no,g.posting_date,g.creation
        from `tabGL Entry` g join `tabAccount` a on a.name=g.account
        where g.voucher_type=%s and g.voucher_no=%s order by g.creation,g.name""",
        (doc.doctype,doc.name),as_dict=True)

def snapshot(item):
    rows = frappe.get_all('Stock Ledger Entry',filters={'item_code':item.name,'warehouse':wh.name},
        fields=['name','voucher_type','voucher_no','actual_qty','stock_value_difference','is_cancelled',
                'qty_after_transaction','stock_value'],order_by='posting_date,posting_time,creation')
    return dict(bin=frappe.db.get_value('Bin',{'item_code':item.name,'warehouse':wh.name},
        ['actual_qty','stock_value'],as_dict=True),sle=rows)

try:
    tag = 'FOC-LIFECYCLE-' + frappe.generate_hash(length=8)
    result['run'] = tag
    company = frappe.get_doc('Company','nesto')
    wh = frappe.get_doc(dict(doctype='Warehouse',warehouse_name=tag,company=company.name,
        parent_warehouse='All Warehouses - N',account=company.default_inventory_account)).insert()
    customer = frappe.get_doc(dict(doctype='Customer',customer_name=tag,customer_type='Company',
        customer_group=frappe.db.get_value('Customer Group',{'is_group':0},'name'),
        territory=frappe.db.get_value('Territory',{'is_group':0},'name'))).insert()
    supplier = frappe.get_doc(dict(doctype='Supplier',supplier_name=tag,supplier_group=
        frappe.db.get_value('Supplier Group',{'is_group':0},'name'),supplier_type='Company')).insert()

    def make_item(method):
        return frappe.get_doc(dict(doctype='Item',item_code=tag+'-'+method,item_name=tag+'-'+method,
            item_group='Retail Bakery Items',stock_uom='Nos',is_stock_item=1,valuation_method=method,
            custom_item_name_arabic=tag,custom_tax='UAE VAT Zero - N',
            custom_purchase_tax_template='UAE VAT Zero - N')).insert()


    def pair(doc):
        assert len(doc.items)==2, ('row count',len(doc.items))
        paid,free=doc.items
        assert paid.custom_foc_key == free.custom_foc_parent
        equal('free qty',free.qty,paid.custom_foc_qty)
        equal('free amount',free.base_net_amount,0)

    def tracking(item,expected):
        if item.has_serial_no:
            actual=frappe.get_all('Serial No',filters={'item_code':item.name,'warehouse':wh.name},pluck='name')
            equal('serial warehouse count',len(actual),expected)
        if item.has_batch_no:
            from erpnext.stock.doctype.batch.batch import get_batch_qty
            equal('batch warehouse count',get_batch_qty(batch_no=batch,warehouse=wh.name),expected)
        equal('Bin qty',frappe.db.get_value('Bin',{'item_code':item.name,'warehouse':wh.name},'actual_qty'),expected)

    def tx(dt,item,time,session=None):
        doc=frappe.get_doc(dict(doctype=dt,company=company.name,posting_date=nowdate(),set_posting_time=1,
            posting_time=time,currency='AED',conversion_rate=1,update_stock=1,customer=customer.name,
            supplier=supplier.name,debit_to=company.default_receivable_account,credit_to=company.default_payable_account,
            cost_center=company.cost_center,items=[dict(item_code=item.name,qty=2,rate=10 if dt=='Purchase Invoice' else 20,
            custom_foc_qty=1,warehouse=wh.name,uom='Nos',conversion_factor=1,cost_center=company.cost_center,
            income_account=company.default_income_account,expense_account=company.default_expense_account)]))
        if session: doc.update(dict(custom_is_van_sale=1,custom_van_session=session.name))
        prepare_foc_items(doc)
        for i,row in enumerate(doc.items):
            if item.has_serial_no:
                row.use_serial_batch_fields=1
                row.serial_no='\n'.join(serials[:2] if i==0 else serials[2:])
            if item.has_batch_no:
                row.use_serial_batch_fields=1; row.batch_no=batch
        doc.insert(); pair(doc)
        ids=[r.name for r in doc.items]; doc.save(); pair(doc)
        assert ids==[r.name for r in doc.items]
        doc.submit(); doc.reload(); pair(doc)
        return doc

    def cancel_check(doc):
        doc.cancel(); doc.reload(); pair(doc)
        assert not frappe.get_all('Stock Ledger Entry',filters={'voucher_no':doc.name,'voucher_type':doc.doctype,'is_cancelled':0})
        assert not frappe.get_all('GL Entry',filters={'voucher_no':doc.name,'voucher_type':doc.doctype,'is_cancelled':0})
        for account in {r.account for r in gl_rows(doc)}:
            equal('cancel GL reversal',sum(r.debit-r.credit for r in gl_rows(doc) if r.account==account),0)

    for kind in ['Van','Serial','Batch']:
        record={'kind':kind,'stages':[]}; result['tests'].append(record)
        frappe.db.savepoint('case_start')
        try:
            session=None; batch=None; serials=[]
            if kind=='Van':
                user=frappe.get_doc(dict(doctype='User',email=tag.lower()+'@example.invalid',first_name=tag,enabled=1,send_welcome_email=0,roles=[dict(role='Van Sales User')])).insert()
                driver=frappe.get_doc(dict(doctype='Driver',full_name=tag,status='Active')).insert()
                fleet=frappe.get_doc(dict(doctype='Van Fleet',van_registration_no=tag,vehicle_name=tag,
                    van_warehouse=wh.name,vehicle_status='Active',default_driver=driver.name)).insert()
                session=frappe.get_doc(dict(doctype='Van Session',session_date=nowdate(),van=fleet.name,
                    van_warehouse=wh.name,driver=driver.name,status='Open',custom_salesperson=user.name)).insert()
                session.submit()
            item=make_item('FIFO-'+kind) if False else frappe.get_doc(dict(doctype='Item',item_code=tag+'-'+kind,
                item_name=tag+'-'+kind,item_group='Retail Bakery Items',stock_uom='Nos',is_stock_item=1,
                valuation_method='FIFO',custom_item_name_arabic=tag,custom_tax='UAE VAT Zero - N',
                custom_purchase_tax_template='UAE VAT Zero - N',has_serial_no=int(kind=='Serial'),
                has_batch_no=int(kind=='Batch'))).insert()
            serials=[tag+'-S'+str(i) for i in range(3)]
            if kind=='Batch':
                batch=frappe.get_doc(dict(doctype='Batch',batch_id=tag+'-B',item=item.name)).insert().name
            record['stage']='receive'
            purchase=tx('Purchase Invoice',item,'08:00:00'); record['stages'].append(ledger(purchase)); tracking(item,3)
            record['stage']='sell'
            sale=tx('Sales Invoice',item,'09:00:00',session); record['stages'].append(ledger(sale)); tracking(item,0)
            record['stage']='return mapping'
            ret=make_sales_return(sale.name)
            record['mapped_rows']=[{k:r.get(k) for k in ['qty','custom_foc_qty','custom_foc_key','custom_foc_parent']} for r in ret.items]
            ret.set_posting_time=1; ret.posting_time='10:00:00'
            ret.insert(); pair(ret); ret.save(); pair(ret); ret.submit(); ret.reload(); pair(ret)
            record['stages'].append(ledger(ret)); tracking(item,3)
            record['stage']='cancel return'
            cancel_check(ret); tracking(item,0)
            record['stage']='cancel sale'
            cancel_check(sale); tracking(item,3)
            record['stage']='cancel receipt'
            cancel_check(purchase); tracking(item,0)
            record['status']='passed'
        except Exception:
            record['status']='failed'; record['error']=traceback.format_exc()
        finally:
            frappe.db.rollback(save_point='case_start')
finally:
    frappe.db.rollback()
    result['rolled_back']=True
    Path('/tmp/targeted_foc_results.json').write_text(json.dumps(result,default=str,indent=2))
    print(json.dumps(result,default=str))
    frappe.destroy()
