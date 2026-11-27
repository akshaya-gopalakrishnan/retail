"""Bill-number lifecycle and browser proof; only the disposable clone is written."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import frappe


def scenario():
    from retail.domains.sales import bill_number as bill
    from retail.domains.transactions.trading_vat import ensure_setup as vat_setup
    from retail.core_compat.runtime import install
    from frappe.utils import nowdate
    vat_setup(); bill.ensure_setup(); install()
    company = frappe.db.get_value('Company', {}, 'name')
    abbr = frappe.db.get_value('Company', company, 'abbr')
    key = 'retail-trading-bill:' + company
    frappe.db.sql('DELETE FROM tabSeries WHERE name=%s', key)
    frappe.db.sql('INSERT INTO tabSeries (name, current) VALUES (%s,79)', key)
    customer = frappe.get_doc(dict(doctype='Customer', customer_name='Bill Number Proof', customer_type='Individual',
        customer_group=frappe.db.get_value('Customer Group', {'is_group':0}, 'name'),
        territory=frappe.db.get_value('Territory', {'is_group':0}, 'name'))).insert()
    template = frappe.db.get_value('Item Tax Template', {'company':company, 'disabled':0}, 'name')
    item = frappe.get_doc(dict(doctype='Item', item_code='Bill Number Proof', item_name='Bill Number Proof',
        item_group=frappe.db.get_value('Item Group', {'is_group':0}, 'name'), stock_uom='Nos', is_stock_item=0,
        custom_tax=template, custom_sales_rate_entry=4, custom_sales_rate_includes_vat=1)).insert()
    def switch(enabled):
        frappe.db.set_value('Company', company, 'custom_enable_trading_sales_vat', enabled)
        frappe.clear_document_cache('Company', company)
    def invoice():
        doc = frappe.new_doc('Sales Invoice')
        doc.update(dict(company=company, customer=customer.name, update_stock=0, posting_date=nowdate(),
            selling_price_list='Standard Selling', currency=frappe.get_cached_value('Company',company,'default_currency'), conversion_rate=1))
        doc.append('items',dict(item_code=item.name, qty=1, rate=4, uom='Nos', conversion_factor=1))
        return doc
    switch(1)
    first = invoice()
    first.custom_bill_number='CLIENT-OVERRIDE'
    with patch.object(bill,'nowdate',return_value='2026-12-31'):
        first.insert()
    assert first.custom_bill_number == abbr+'2610080', first.custom_bill_number
    assert first.title == first.custom_bill_number and first.name.startswith('SI-')
    original=first.custom_bill_number
    first.custom_bill_number='CHANGED'; first.custom_bill_sequence='9999'
    with patch.object(bill,'nowdate',return_value='2027-01-01'):
        first.save()
    assert first.custom_bill_number == original and first.custom_bill_sequence=='80'
    first.submit()
    switch(0)
    with patch.object(bill,'nowdate',return_value='2027-01-01'):
        second=invoice().insert()
    assert second.custom_bill_number == abbr+'2700081', second.custom_bill_number
    assert first.name != second.name and second.title==second.custom_bill_number
    assert second.total_taxes_and_charges==0
    second.submit()
    from bs4 import BeautifulSoup
    html=frappe.render_template(frappe.get_doc('Print Format','Sales Invoice - A4').html,
        dict(doc=second,letter_head='',footer='',no_letterhead=1))
    printed=BeautifulSoup(html,'html.parser')
    assert printed.select_one('.invoice-details .detail-value').get_text(strip=True)==second.custom_bill_number
    assert printed.select_one('.customer-name').get_text(strip=True)==customer.customer_name
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
    returned=make_sales_return(second.name)
    returned.insert(); returned.submit()
    assert returned.custom_bill_number and returned.custom_bill_number!=second.custom_bill_number
    second.reload()
    assert second.title==second.custom_bill_number and second.get_title()==second.custom_bill_number
    # Contending allocations use two independent real transactions in the clone.
    concurrency(company)
    import os
    os.environ['VAT_BILL_NUMBERS']='1'
    spec=importlib.util.spec_from_file_location('vat_validation',Path(__file__).with_name('trading_vat_isolated.py'))
    validation=importlib.util.module_from_spec(spec);spec.loader.exec_module(validation)
    validation.browser(company,customer.name,item.name)
    print('PASS: branch-free format, company abbreviation, 2026 to 2027 continuity 80→81, VAT flag, immutable snapshots/title, print, returns and concurrent allocation.',flush=True)


def concurrency(company):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from frappe.database import get_db
    config=dict(frappe.conf)
    socket=frappe.db.socket
    site=frappe.local.site
    frappe.db.commit()
    barrier=threading.Barrier(2)
    def allocate():
        frappe.init(site=site,force=True)
        frappe.conf.update(config)
        frappe.local.db=get_db(socket=socket,user='root',password='',cur_db_name='conversion_validation')
        try:
            barrier.wait(timeout=10)
            frappe.db.get_value('Company',company,'name',for_update=True)
            from frappe.model.naming import getseries
            value=getseries('retail-trading-bill:'+company,2)
            frappe.db.commit()
            return value
        finally:
            frappe.destroy()
    with ThreadPoolExecutor(max_workers=2) as pool:
        values=list(pool.map(lambda _:allocate(),range(2)))
    assert len(set(values))==2, values


if __name__=='__main__':
    spec=importlib.util.spec_from_file_location('harness',Path(__file__).with_name('product_conversion_isolated.py'))
    harness=importlib.util.module_from_spec(spec);spec.loader.exec_module(harness)
    harness.scenario=scenario
    harness.main()
