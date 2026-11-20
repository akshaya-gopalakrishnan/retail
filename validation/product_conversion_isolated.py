"""Submit/cancel proof in disposable MariaDB + Redis; source site is read-only.

Run from the bench root with env/bin/python. This does NOT run Frappe's test
runner or its destructive before_tests hooks. No site configuration is edited.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import pymysql
import frappe

BENCH = Path(__file__).resolve().parents[3]
SITE = 'retail-test.localhost'


def scenario():
    from frappe.utils import nowdate, nowtime
    from retail.product_conversion import get_defaults
    company = 'nesto'
    group = frappe.db.get_value('Item Group', {'is_group': 0}, 'name')
    def item(label, unit, cost):
        doc = frappe.get_doc(dict(doctype='Item', item_code='PC Test '+label,
            item_name='PC Test '+label, item_group=group, stock_uom=unit,
            is_stock_item=1, custom_purchase_rate_entry=cost,
            custom_purchase_rate_includes_vat=0))
        doc.insert(ignore_permissions=True)
        return doc.name
    raw = item('Bulk', 'Kg', 10)
    package = item('Bottle', 'Nos', 1)
    a = item('Pack A', 'Nos', 7)
    b = item('Pack B', 'Nos', 9)
    warehouse = frappe.get_doc(dict(doctype='Warehouse', warehouse_name='PC Test Stores', company=company)).insert().name
    receipt = frappe.new_doc('Stock Entry')
    receipt.update(dict(company=company,purpose='Material Receipt',stock_entry_type='Material Receipt',
        posting_date=nowdate(),posting_time=nowtime(),set_posting_time=1))
    options = receipt.meta.get_field('naming_series').options.splitlines()
    receipt.naming_series = next((r for r in options if r), receipt.naming_series)
    for code,rate in ((raw,10),(package,1)):
        receipt.append('items',dict(item_code=code,qty=100,uom=frappe.db.get_value('Item',code,'stock_uom'),
            t_warehouse=warehouse,conversion_factor=1,basic_rate=rate,set_basic_rate_manually=1))
    receipt.insert();receipt.submit()
    bom = frappe.get_doc(dict(doctype='BOM',company=company,item=b,quantity=2,is_active=1,
        is_default=1,rm_cost_as_per='Valuation Rate',items=[dict(item_code=raw,qty=3),dict(item_code=package,qty=2)]))
    bom.insert();bom.submit()
    d = frappe.new_doc('Product Conversion')
    d.update(dict(company=company,posting_date=nowdate(),posting_time=nowtime(),**get_defaults(company)))
    d.source_warehouse=d.target_warehouse=warehouse
    d.append('items',dict(main_item=raw,item_code=a,qty=4,
        main_qty=8,main_qty_per_unit=2,labour_cost=8,packing_cost=4))
    d.refresh_costs()
    d.add_material(dict(row_key=d.items[0].row_key,item_code=package,qty=4,warehouse=warehouse))
    d.add_product(dict(source_type='BOM',bom_no=bom.name,qty=2,use_multi_level_bom=0,
        labour_cost=4,packing_cost=2,update_item_master=1))
    assert len(d.items)==2 and len(d.materials)==4
    assert (d.items[0].total_cost,d.items[1].total_cost)==(96,38), [(r.product_cost,r.total_cost) for r in d.items]
    d.insert();d.submit();d.reload()
    assert d.status=='Posted' and d.stock_entry
    entry=frappe.get_doc('Stock Entry',d.stock_entry)
    assert entry.docstatus==1
    assert (d.items[0].total_cost,d.items[1].total_cost)==(96,38), dict(
        products=[(r.product_cost,r.total_cost,r.unit_cost) for r in d.items],
        stock=[(r.item_code,r.qty,r.basic_rate,r.basic_amount,r.additional_cost,r.valuation_rate,r.amount,r.get('custom_repack_group')) for r in entry.items])
    assert abs(entry.total_incoming_value-134)<.001
    assert abs(entry.total_outgoing_value-116)<.001
    assert entry.total_additional_costs==18
    bins={code:frappe.db.get_value('Bin',{'item_code':code,'warehouse':warehouse},['actual_qty','valuation_rate'],as_dict=True) for code in (raw,package,a,b)}
    assert bins[raw].actual_qty==89 and bins[raw].valuation_rate==10,bins
    assert bins[package].actual_qty==94
    assert bins[a].actual_qty==4 and bins[a].valuation_rate==24,bins
    assert bins[b].actual_qty==2 and bins[b].valuation_rate==19,bins
    assert frappe.db.get_value('Item',a,'custom_purchase_net_rate')==7
    assert frappe.db.get_value('Item',b,'custom_purchase_net_rate')==19
    sle=frappe.get_all('Stock Ledger Entry',filters={'voucher_no':entry.name,'is_cancelled':0},fields=['item_code','actual_qty','stock_value_difference'])
    gl=frappe.get_all('GL Entry',filters={'voucher_no':entry.name,'is_cancelled':0},fields=['debit','credit'])
    assert len(sle)==6,sle
    assert gl and abs(sum(r.debit-r.credit for r in gl))<.001,gl
    print(json.dumps(dict(posted=d.name,stock_entry=entry.name,stock_ledger=sle,
        gl_debit=sum(r.debit for r in gl),gl_credit=sum(r.credit for r in gl),
        checked_master=19,unchecked_master=7)))
    # Confirm guarded direct cancellation cannot leave a Posted conversion dangling.
    try:entry.cancel()
    except frappe.ValidationError as exc:assert 'Product Conversion' in str(exc)
    else:raise AssertionError('Direct Stock Entry cancellation was not blocked')
    entry.reload()
    d.cancel();d.reload();entry.reload()
    assert d.status=='Cancelled' and entry.docstatus==2
    assert frappe.db.get_value('Bin',{'item_code':raw,'warehouse':warehouse},'actual_qty')==100
    assert frappe.db.get_value('Bin',{'item_code':package,'warehouse':warehouse},'actual_qty')==100
    assert frappe.db.get_value('Item',b,'custom_purchase_net_rate')==9
    print('Cancel restored stock and the unchanged master cost; direct entry cancellation blocked.')
    # A shared material must be checked across the whole document.
    fail=frappe.new_doc('Product Conversion')
    fail.update(dict(company=company,posting_date=nowdate(),posting_time=nowtime(),**get_defaults(company)))
    fail.source_warehouse=fail.target_warehouse=warehouse
    for _ in range(2):fail.add_product(dict(source_type='Main Item',main_item=raw,item_code=a,qty=60,qty_per_unit=1))
    fail.insert()
    try:fail.submit()
    except frappe.ValidationError as exc:assert 'Insufficient stock' in str(exc),exc
    else:raise AssertionError('Combined shortage was not blocked')
    print('Combined-material shortage blocked before posting.')

    # Native serial/batch bundles must retain the Stock Entry voucher identity.
    from frappe.utils import add_days
    tracked_raw = item('Tracked Bulk', 'Kg', 10)
    tracked_output = item('Tracked Pack', 'Nos', 5)
    batches = []
    for code, label in ((tracked_raw, 'PC-BULK-BATCH'), (tracked_output, 'PC-PACK-BATCH')):
        tracked = frappe.get_doc('Item', code)
        tracked.has_batch_no = 1
        tracked.create_new_batch = 0
        tracked.save()
        batch = frappe.get_doc(dict(doctype='Batch', batch_id=label, item=code,
            manufacturing_date=nowdate(), expiry_date=add_days(nowdate(),365))).insert()
        batches.append(batch.name)
    received = frappe.new_doc('Stock Entry')
    received.update(dict(company=company,purpose='Material Receipt',stock_entry_type='Material Receipt',
        posting_date=nowdate(),posting_time=nowtime(),set_posting_time=1,naming_series=receipt.naming_series))
    received.append('items',dict(item_code=tracked_raw,qty=10,uom='Kg',t_warehouse=warehouse,
        conversion_factor=1,basic_rate=10,set_basic_rate_manually=1,batch_no=batches[0],use_serial_batch_fields=1))
    received.insert();received.submit()
    tracked = frappe.new_doc('Product Conversion')
    tracked.update(dict(company=company,posting_date=nowdate(),posting_time=nowtime(),**get_defaults(company)))
    tracked.source_warehouse=tracked.target_warehouse=warehouse
    tracked.add_product(dict(source_type='Main Item',main_item=tracked_raw,item_code=tracked_output,
        qty=4,qty_per_unit=.5,labour_cost=1,packing_cost=1))
    tracked.materials[0].batch_no=batches[0]
    tracked.items[0].batch_no=batches[1]
    tracked.insert();tracked.submit();tracked.reload()
    from erpnext.stock.report.serial_and_batch_summary.serial_and_batch_summary import execute
    _, summary = execute(frappe._dict(company=company,from_date=nowdate(),to_date=nowdate(),
        voucher_type='Stock Entry',voucher_no=[tracked.stock_entry]))
    assert {r.batch_no for r in summary} == set(batches), summary
    assert tracked.items[0].total_cost==22
    tracked.cancel()
    print('Batch-tracked conversion, Serial and Batch Summary, and cancellation passed.')

    fifo_raw = item('FIFO Bulk', 'Kg', 10)
    fifo_item = frappe.get_doc('Item', fifo_raw)
    fifo_item.valuation_method = 'FIFO'
    fifo_item.save()
    for rate in (10,20):
        received = frappe.new_doc('Stock Entry')
        received.update(dict(company=company,purpose='Material Receipt',stock_entry_type='Material Receipt',
            posting_date=nowdate(),posting_time=nowtime(),set_posting_time=1,naming_series=receipt.naming_series))
        received.append('items',dict(item_code=fifo_raw,qty=5,uom='Kg',t_warehouse=warehouse,
            conversion_factor=1,basic_rate=rate,set_basic_rate_manually=1))
        received.insert();received.submit()
    fifo = frappe.new_doc('Product Conversion')
    fifo.update(dict(company=company,posting_date=nowdate(),posting_time=nowtime(),**get_defaults(company)))
    fifo.source_warehouse=fifo.target_warehouse=warehouse
    for code in (a,b):fifo.add_product(dict(source_type='Main Item',main_item=fifo_raw,item_code=code,qty=4,qty_per_unit=1))
    fifo.update_consumption(dict(row_key=fifo.items[0].row_key,
        rows=[dict(item_code=fifo_raw,qty=4,warehouse=warehouse)]))
    assert [r.product_cost for r in fifo.items]==[40,70], 'FIFO preview must consume successive layers'
    fifo.insert();fifo.submit();fifo.reload()
    assert [r.product_cost for r in fifo.items]==[40,70],dict(products=[(r.product_cost,r.total_cost) for r in fifo.items],
        ledger=frappe.get_all('Stock Ledger Entry',filters={'voucher_no':fifo.stock_entry,'is_cancelled':0},fields=['item_code','actual_qty','stock_value_difference','incoming_rate','outgoing_rate']))
    fifo.cancel()
    print('Shared FIFO material with two receipt costs allocated correctly across products.')


def main():
    os.chdir(BENCH/'sites')
    frappe.init(site=SITE)
    source=dict(frappe.conf)
    frappe.destroy()
    with tempfile.TemporaryDirectory(prefix='product-conversion-isolated-',dir='/tmp') as temporary:
        root=Path(temporary);os.chmod(root,0o700)
        data=root/'data';data.mkdir()
        socket=root/'mysql.sock';redis_socket=root/'redis.sock'
        subprocess.run(['mariadb-install-db','--no-defaults','--datadir='+str(data),
            '--auth-root-authentication-method=normal','--skip-test-db'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
        mysql_log=(root/'mysql.log').open('w')
        dbserver=subprocess.Popen(['mariadbd','--no-defaults','--datadir='+str(data),'--socket='+str(socket),
            '--skip-networking','--skip-log-bin','--innodb-buffer-pool-size=64M',
            '--pid-file='+str(root/'mysql.pid')],stdout=mysql_log,stderr=mysql_log)
        redis_log=(root/'redis.log').open('w')
        redis=subprocess.Popen(['redis-server','--port','0','--unixsocket',str(redis_socket),
            '--save','','--appendonly','no','--dir',temporary],stdout=redis_log,stderr=redis_log)
        try:
            for _ in range(150):
                try:
                    conn=pymysql.connect(user='root',unix_socket=str(socket));break
                except pymysql.Error:time.sleep(.1)
            else:raise RuntimeError('Isolated MariaDB failed to start')
            conn.cursor().execute('CREATE DATABASE conversion_validation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            conn.close()
            credentials=root/'source.cnf';credentials.touch(mode=0o600)
            credentials.write_text('[client]\n'+ '\n'.join(f'{key}={json.dumps(str(value))}' for key,value in {
                'user':source['db_name'],'password':source['db_password'],
                'host':source.get('db_host') or '127.0.0.1','port':source.get('db_port') or 3306}.items())+'\n')
            dump=root/'snapshot.sql';dump.touch(mode=0o600)
            with dump.open('wb') as output:
                subprocess.run(['mariadb-dump','--defaults-extra-file='+str(credentials),'--single-transaction',
                    '--skip-lock-tables','--skip-triggers','--no-tablespaces',source['db_name']],stdout=output,check=True)
            with dump.open('rb') as input_file:
                subprocess.run(['mariadb','--no-defaults','--socket='+str(socket),'-uroot','conversion_validation'],stdin=input_file,check=True)
            credentials.unlink();dump.unlink()
            frappe.init(site=SITE,force=True)
            frappe.conf.update(db_name='conversion_validation',db_socket=str(socket),db_host=None,
                developer_mode=0,redis_cache='unix://'+str(redis_socket)+'?db=0',
                redis_queue='unix://'+str(redis_socket)+'?db=1',mute_emails=True)
            from frappe.utils.redis_wrapper import setup_cache
            frappe.cache=setup_cache()
            from frappe.database import get_db
            frappe.local.db=get_db(socket=str(socket),user='root',password='',cur_db_name='conversion_validation')
            frappe.set_user('Administrator')
            assert frappe.db.sql('select database()')[0][0]=='conversion_validation'
            assert frappe.db.socket==str(socket)
            scenario()
            frappe.db.rollback();frappe.destroy()
            print('Isolated lifecycle validation passed. Source business data was not modified.')
        finally:
            redis.terminate();dbserver.terminate()
            for process in (redis,dbserver):
                try:process.wait(timeout=15)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            mysql_log.close();redis_log.close()


if __name__=='__main__':main()
