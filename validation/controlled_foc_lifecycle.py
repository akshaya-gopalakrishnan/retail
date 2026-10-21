"""Run isolated FOC posting checks; all fixture/transaction DML is rolled back.
Run from sites: ../env/bin/python ../apps/retail/validation/controlled_foc_lifecycle.py
FOC schema must be installed separately before running (DDL commits in MariaDB).
Stops at the first lifecycle failure; never runs profitability regressions here.
"""
import json
from pathlib import Path
import traceback
import sys
import shutil
import subprocess
import tempfile

# Load the unchanged candidate in this test process only; never activate it in apps.
_candidate = tempfile.TemporaryDirectory(prefix='foc-cancellation-')
_source = Path(__file__).resolve().parents[1]
shutil.copytree(_source / 'retail', Path(_candidate.name) / 'retail',
                ignore=shutil.ignore_patterns('__pycache__'))
subprocess.run(['patch', '-p1', '-i', str(_source / 'validation/foc_candidate.patch')],
               cwd=_candidate.name, check=True, capture_output=True)
sys.path.insert(0, _candidate.name)
import frappe
from frappe.utils import flt, nowdate

OUT = Path('/home/adler/frappe-bench/apps/retail/validation/controlled_foc_results.json')
result = {'site': 'retail-test.localhost', 'tests': [], 'status': 'running'}
frappe.init(site=result['site'], sites_path='/home/adler/frappe-bench/sites')
frappe.connect()
frappe.set_user('Administrator')
frappe.flags.in_test = True
stage = 'fixtures'

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
        rows = execute(dict(company=doc.company,from_date=doc.posting_date,to_date=doc.posting_date,
                            sales_invoice=doc.name,group_by='Invoice'))[1]
        report = next(r for r in rows if r.sales_group == doc.name)
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

    def transaction(dt,item,qty,rate,foc=0,time='10:00:00'):
        row = dict(item_code=item.name,qty=qty,rate=rate,custom_foc_qty=foc,
                   warehouse=wh.name,uom='Nos',conversion_factor=1,cost_center=company.cost_center,
                   income_account=company.default_income_account,
                   expense_account=company.default_expense_account)
        doc = frappe.get_doc(dict(doctype=dt,company=company.name,posting_date=nowdate(),
            set_posting_time=1,posting_time=time,currency='AED',conversion_rate=1,
            update_stock=1,customer=customer.name,supplier=supplier.name,
            debit_to=company.default_receivable_account,credit_to=company.default_payable_account,
            cost_center=company.cost_center,items=[row]))
        doc.insert()
        # Saving the draft twice must reuse the free row and not inflate quantities.
        ids = [r.name for r in doc.items]
        doc.save()
        assert ids == [r.name for r in doc.items], 'FOC draft save duplicated/recreated rows'
        doc.submit()
        doc.reload()
        equal('paid quantity',doc.items[0].qty,qty)
        equal('paid rate',doc.items[0].rate,rate)
        equal('FOC quantity metadata',doc.items[0].custom_foc_qty,foc)
        assert len(doc.items) == (2 if foc else 1)
        return doc

    for method in ('FIFO',):
        stage = f'{method}: A purchase'
        item = make_item(method)
        purchase = transaction('Purchase Invoice',item,10,10,2)
        record = ledger(purchase)
        equal('received quantity',record['received_or_sold_qty'],12)
        equal('purchase stock value',record['sle_value'],100)
        result['tests'].append(dict(stage=stage,**record))
        stage = f'{method}: B/C partial sale'
        # Six units makes the Moving Average expected cost exactly AED 50.
        sale = transaction('Sales Invoice',item,6,20,time='11:00:00')
        record = ledger(sale)
        equal('expected core COGS',record['cogs_gl'],60 if method=='FIFO' else 50)
        result['tests'].append(dict(stage=stage,**record))
        stage = f'{method}: D split-SLE FOC sale'
        before_sale = snapshot(item)
        split = transaction('Sales Invoice',item,3,20,1,time='12:00:00')
        record = ledger(split)
        equal('sold paid and free quantity',record['received_or_sold_qty'],-4)
        assert len(record['sle']) == 2
        result['tests'].append(dict(stage=stage,**record))
        if method == 'FIFO':
            stage = 'E cancellation'
            before_cancel = snapshot(item)
            original_sle = sle_rows(split)
            original_gl = gl_rows(split)
            original_status = split.docstatus
            split.cancel()
            split.reload()
            after_cancel = snapshot(item)
            after_sle = sle_rows(split)
            originals = {r.name for r in original_sle}
            reposts = frappe.get_all('Repost Item Valuation', filters={'warehouse':wh.name}, fields=['*'])
            voucher_reposts = frappe.get_all('Repost Item Valuation', filters={'voucher_no':split.name}, fields=['*'])
            evidence = dict(stage=stage, voucher=split.name, original_status=original_status,
                cancelled_status=split.docstatus, items=record['items'], original_sle=original_sle,
                original_sle_after=[r for r in after_sle if r.name in originals],
                cancellation_sle=[r for r in after_sle if r.name not in originals],
                original_gl=original_gl, after_gl=gl_rows(split), before_sale=before_sale,
                after_sale=before_cancel, after_cancel=after_cancel,
                reposts=list({r.name:r for r in reposts+voucher_reposts}.values()))
            result['tests'].append(evidence)
            equal('cancelled document status', split.docstatus, 2)
            assert len(evidence['cancellation_sle']) == 2
            for original in original_sle:
                reversal = [r for r in evidence['cancellation_sle']
                            if r.voucher_detail_no == original.voucher_detail_no]
                assert len(reversal) == 1
                equal('detail quantity reversal', reversal[0].actual_qty, -original.actual_qty)
            assert all(r.is_cancelled for r in after_sle)
            equal('audit quantity net', sum(r.actual_qty for r in after_sle), 0)
            # Cancelled SLE values are audit data, not additive valuation movements.
            # Core excludes BOTH the original and cancellation rows from valuation.
            for label, snap in [('before', before_sale), ('sale', before_cancel), ('cancel', after_cancel)]:
                active = [r for r in snap['sle'] if not r.is_cancelled]
                equal(label+' active quantity vs Bin', sum(r.actual_qty for r in active), snap['bin'].actual_qty)
                equal(label+' active value vs Bin', sum(r.stock_value_difference for r in active), snap['bin'].stock_value)
            equal('sale quantity movement', before_cancel['bin'].actual_qty-before_sale['bin'].actual_qty, -4)
            equal('sale value movement', before_cancel['bin'].stock_value-before_sale['bin'].stock_value, -40)
            equal('cancel quantity restoration', after_cancel['bin'].actual_qty-before_cancel['bin'].actual_qty, 4)
            equal('cancel value restoration', after_cancel['bin'].stock_value-before_cancel['bin'].stock_value, 40)
            equal('lifecycle net quantity', after_cancel['bin'].actual_qty-before_sale['bin'].actual_qty, 0)
            equal('lifecycle net value', after_cancel['bin'].stock_value-before_sale['bin'].stock_value, 0)
            assert not any(not g.is_cancelled for g in evidence['after_gl'])
            for account in {g.account for g in evidence['after_gl']}:
                equal('GL reversal '+account, sum(g.debit-g.credit for g in evidence['after_gl'] if g.account==account), 0)
            assert all(r.status == 'Completed' for r in evidence['reposts'])
            evidence['assertions'] = 'passed'

    stage = 'Moving Average: purchase'
    item = make_item('Moving Average')
    purchase = transaction('Purchase Invoice',item,10,10,2)
    record = ledger(purchase)
    equal('MA received quantity',record['received_or_sold_qty'],12)
    equal('MA initial stock value',record['sle_value'],100)
    result['tests'].append(dict(stage=stage,**record))
    stage = 'Moving Average: different-rate purchase'
    purchase2 = transaction('Purchase Invoice',item,8,20,time='11:00:00')
    record = ledger(purchase2)
    equal('second receipt value',record['sle_value'],160)
    state = snapshot(item)
    equal('MA total quantity',state['bin'].actual_qty,20)
    equal('MA total value',state['bin'].stock_value,260)
    result['tests'].append(dict(stage=stage,**record))
    stage = 'Moving Average: partial sale'
    sale = transaction('Sales Invoice',item,5,30,time='12:00:00')
    record = ledger(sale)
    equal('MA COGS 5 * (260/20)',record['cogs_gl'],65)
    state = snapshot(item)
    equal('MA remaining quantity',state['bin'].actual_qty,15)
    equal('MA remaining value',state['bin'].stock_value,195)
    result['tests'].append(dict(stage=stage,**record,stock_after=state))

    stage = 'Reposting: backdated purchase'
    from erpnext.stock.doctype.repost_item_valuation.repost_item_valuation import repost
    before_ids = {r.name for r in frappe.get_all('Repost Item Valuation')}
    original_sale_sle = {r.name for r in sle_rows(sale)}
    frappe.flags.dont_execute_stock_reposts = True
    backdated = transaction('Purchase Invoice',item,6,5,time='09:00:00')
    frappe.flags.dont_execute_stock_reposts = False
    pending = [r for r in frappe.get_all('Repost Item Valuation',fields=['name','status'])
               if r.name not in before_ids]
    assert pending, 'Backdated receipt did not trigger repost'
    assert all(r.status == 'Queued' for r in pending), pending
    for row in pending:
        repost(frappe.get_doc('Repost Item Valuation',row.name))
    completed = [frappe.get_doc('Repost Item Valuation',r.name) for r in pending]
    assert all(r.status == 'Completed' for r in completed)
    expected_cogs = 5 * (290/26)
    records = [ledger(d) for d in (backdated,purchase,purchase2,sale)]
    equal('reposted core COGS',records[-1]['cogs_gl'],expected_cogs,2)
    assert original_sale_sle == {r.name for r in sle_rows(sale)}, 'Repost duplicated/replaced sale SLE'
    state = snapshot(item)
    equal('reposted quantity',state['bin'].actual_qty,21)
    equal('reposted stock value',state['bin'].stock_value,290-expected_cogs,2)
    active = [r for r in state['sle'] if not r.is_cancelled]
    assert len(active) == 5, 'Duplicate/orphan/missing SLE'
    expected_vouchers = {(d.doctype,d.name) for d in (backdated,purchase,purchase2,sale)}
    assert {(r.voucher_type,r.voucher_no) for r in active} == expected_vouchers
    equal('final SLE value vs Bin',sum(r.stock_value_difference for r in active),state['bin'].stock_value)
    equal('final stock GL vs Bin',sum(r['stock_gl'] for r in records),state['bin'].stock_value,2)
    result['tests'].append(dict(stage=stage,transactions=records,stock_after=state,
        reposts=[dict(name=r.name,status=r.status) for r in completed],
        expected_cogs=expected_cogs,assertions='passed'))
    result['status']='passed'
except Exception as exc:
    result.update(status='failed',failed_stage=stage,error=str(exc),traceback=traceback.format_exc())
finally:
    frappe.db.rollback()
    result['transactions_rolled_back']=True
    OUT.write_text(json.dumps(result,default=str,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='tests'},default=str,indent=2))
    print('completed checks:',len(result['tests']))
    frappe.destroy()
    _candidate.cleanup()
if result['status'] != 'passed':
    raise SystemExit(1)
