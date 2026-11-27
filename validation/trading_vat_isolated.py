"""Trading VAT proof using the disposable database/Redis harness."""
import importlib.util
from pathlib import Path
import frappe


def scenario():
    from retail.domains.transactions import trading_vat as policy
    from retail.domains.transactions.vat import set_vat_rates, get_transaction_vat_tax_rows
    from retail.core_compat.runtime import install
    from erpnext.stock.get_item_details import get_item_details
    policy.ensure_setup()
    install()
    company = frappe.db.get_value('Company', {}, 'name')
    template = frappe.db.get_value('Item Tax Template', {'company': company, 'disabled': 0}, 'name')
    assert template
    account = frappe.get_doc('Item Tax Template', template).taxes[0].tax_type
    frappe.db.set_value('Item Tax Template Detail', {'parent': template}, 'tax_rate', 5)
    frappe.clear_document_cache('Item Tax Template', template)
    item = frappe.get_doc(dict(doctype='Item', item_code='Trading VAT Proof', item_name='Trading VAT Proof',
        item_group=frappe.db.get_value('Item Group', {'is_group': 0}, 'name'), stock_uom='Nos',
        is_stock_item=0, custom_tax=template, custom_sales_rate_entry=4,
        custom_sales_rate_includes_vat=1)).insert()
    customer = frappe.get_doc(dict(doctype='Customer', customer_name='Trading VAT Proof', customer_type='Individual',
        customer_group=frappe.db.get_value('Customer Group', {'is_group': 0}, 'name'),
        territory=frappe.db.get_value('Territory', {'is_group': 0}, 'name'))).insert()
    def switch(enabled):
        frappe.db.set_value('Company', company, policy.COMPANY_FIELD, enabled)
        frappe.clear_document_cache('Company', company)
    def invoice(rate):
        doc = frappe.new_doc('Sales Invoice')
        doc.update(dict(company=company, customer=customer.name, update_stock=0, selling_price_list='Standard Selling',
                   currency=frappe.get_cached_value('Company', company, 'default_currency'), conversion_rate=1))
        doc.append('items', dict(item_code=item.name, qty=1, rate=rate, price_list_rate=rate,
            uom='Nos', conversion_factor=1, item_tax_template=template))
        return doc
    switch(1)
    enabled = invoice(4/1.05)
    enabled.insert()
    assert enabled.total_taxes_and_charges == .19, enabled.as_dict()
    assert enabled.grand_total == 4, enabled.grand_total
    enabled.submit()
    old_draft = invoice(4/1.05)
    old_draft.insert()
    direct_submit = invoice(4/1.05)
    direct_submit.insert()
    switch(0)
    direct_submit.submit()
    assert direct_submit.grand_total == 4 and direct_submit.total_taxes_and_charges == 0
    old_draft.save()
    assert old_draft.grand_total == 4 and old_draft.items[0].rate == 4 and old_draft.total_taxes_and_charges == 0
    draft = invoice(4)
    draft.insert()
    assert draft.items[0].rate == 4 and draft.items[0].custom_vat_amount == 0
    assert draft.total_taxes_and_charges == 0 and draft.grand_total == 4
    assert not draft.items[0].item_tax_template and not draft.taxes
    assert get_transaction_vat_tax_rows(draft.as_json())['vat_disabled']
    details = get_item_details(frappe._dict(doctype='Sales Invoice', company=company, customer=customer.name,
        item_code=item.name, qty=1, uom='Nos', price_list='Standard Selling',
        selling_price_list='Standard Selling', currency=draft.currency, price_list_currency=draft.currency,
        conversion_rate=1, plc_conversion_rate=1), draft)
    assert round(details.price_list_rate, 2) == 4, details
    from retail.domains.transactions.vat import get_transaction_item_vat_rate
    assert get_transaction_item_vat_rate(item.name, parent_doctype='Sales Invoice', company=company) == 0
    assert get_transaction_item_vat_rate(item.name, parent_doctype='Sales Invoice', company=company, is_pos=1) == 5
    draft.submit()
    from bs4 import BeautifulSoup
    printed = BeautifulSoup(frappe.render_template(frappe.get_doc('Print Format', 'Sales Invoice - A4').html,
        dict(doc=draft, letter_head='', footer='', no_letterhead=1)), 'html.parser')
    assert printed.select_one('.invoice-title').get_text(strip=True) == 'Sales Invoice'
    assert not printed.select('td.col-tax, th.col-tax, td.col-tax-rate, th.col-tax-rate, td.col-rate-incl, th.col-rate-incl')
    assert [th.get_text(strip=True) for th in printed.select('.item-table th')] == ['Sr No', 'Item', 'Qty / UOM', 'Rate', 'Amount']
    taxed_print = BeautifulSoup(frappe.render_template(frappe.get_doc('Print Format', 'Sales Invoice - A4').html,
        dict(doc=enabled, letter_head='', footer='', no_letterhead=1)), 'html.parser')
    assert [th.get_text(strip=True) for th in taxed_print.select('.item-table th')] == ['Sr No', 'Item', 'Qty / UOM', 'VAT%', 'VAT', 'Rate Excl. VAT', 'Rate Incl. VAT', 'Total Excl. VAT', 'Total Incl. VAT']
    assert taxed_print.select_one('td.col-amount-excl').get_text(strip=True) == '3.81'
    import subprocess
    baseline = subprocess.check_output(['git', '-C', str(Path(__file__).resolve().parents[1]), 'show',
        'HEAD:retail/templates/editable_print_formats/sales_invoice.html'], text=True)
    baseline_print = BeautifulSoup(frappe.render_template(baseline,
        dict(doc=enabled, letter_head='', footer='', no_letterhead=1)), 'html.parser')
    for selector in ('.totals-table',):
        assert taxed_print.select_one(selector).get_text(' ', strip=True) == baseline_print.select_one(selector).get_text(' ', strip=True)
    assert printed.select_one('td.col-amount').get_text(strip=True) == '4.00'
    assert not frappe.db.exists('GL Entry', {'voucher_type': 'Sales Invoice', 'voucher_no': draft.name, 'account': account})
    assert frappe.db.get_value('Sales Invoice', enabled.name, 'total_taxes_and_charges') == .19
    shipping = invoice(4)
    shipping.append('taxes', dict(charge_type='Actual', description='Freight',
        account_head=frappe.db.get_value('Account', {'company':company, 'is_group':0, 'root_type':'Income'}, 'name'),
        tax_amount=2, cost_center=draft.cost_center))
    shipping.insert()
    assert shipping.total_taxes_and_charges == 2 and shipping.grand_total == 6
    assert shipping.items[0].custom_vat_amount == 0
    switch(1)
    draft.reload()
    assert policy.vat_disabled(draft), 'Submitted invoice must retain its policy'
    from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
    returned = make_sales_return(draft.name)
    returned.insert(); returned.submit()
    assert returned.grand_total == -4 and returned.total_taxes_and_charges == 0
    switch(0)
    taxed_return = make_sales_return(enabled.name)
    taxed_return.insert(); taxed_return.submit()
    assert taxed_return.total_taxes_and_charges == -.19 and taxed_return.grand_total == -4
    assert not policy.vat_disabled(frappe._dict(doctype='Sales Invoice', company=company, is_pos=1))
    assert not policy.vat_disabled(frappe._dict(doctype='Sales Invoice', company=company, is_consolidated=1))
    assert not policy.vat_disabled(frappe._dict(doctype='Purchase Invoice', company=company))
    assert frappe.get_doc('Item', item.name).custom_tax == template
    browser(company, customer.name, item.name)
    print('PASS: enabled/disabled invoices, native price lookup 4.00, submit/GL, historical VAT, returns in both directions, POS/purchase exclusions and Item preservation.', flush=True)


def browser(company, customer, item):
    import json, os, shutil, subprocess, threading
    import frappe.app
    from frappe.sessions import Session
    from werkzeug.serving import make_server, WSGIRequestHandler
    root = Path(frappe.db.socket).parent / 'browser-sites'
    site = 'retail-test.localhost'
    (root / site / 'logs').mkdir(parents=True)
    (root / 'logs').mkdir()
    shutil.copy(Path(frappe.local.sites_path) / 'apps.txt', root / 'apps.txt')
    (root / 'assets').symlink_to(Path('/home/adler/frappe-bench/sites/assets'))
    frappe.db.commit()
    password = frappe.generate_hash(length=30)
    frappe.db.sql("CREATE USER 'conversion_validation'@'localhost' IDENTIFIED BY %s", password)
    frappe.db.sql("GRANT ALL ON conversion_validation.* TO 'conversion_validation'@'localhost'")
    config = dict(frappe.conf)
    config.update(db_user='conversion_validation', db_password=password, db_socket=frappe.db.socket,
                  developer_mode=0, maintenance_mode=0, mute_emails=True)
    (root / site / 'site_config.json').write_text(json.dumps(config))
    (root / site / 'site_config.json').chmod(0o600)
    frappe.db.commit()
    frappe.init(site=site, sites_path=str(root), force=True)
    frappe.connect()
    assert frappe.db.sql('select database()')[0][0] == 'conversion_validation'
    frappe.set_user('Administrator')
    frappe.local.request = frappe._dict(cookies={})
    frappe.local.request_ip = '127.0.0.1'
    frappe.local.form_dict = frappe._dict()
    sid = Session(user='Administrator', user_type='System User', full_name='Administrator').sid
    frappe.db.commit()
    frappe.app._sites_path = str(root)
    frappe.app._site = site
    class Quiet(WSGIRequestHandler):
        def log(self, *args, **kwargs):
            pass
    server = make_server('127.0.0.1', 0, frappe.app.application_with_statics(), threaded=True, request_handler=Quiet)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        subprocess.run(['node', str(Path(__file__).with_name('trading_vat_browser.cjs'))],
            env=dict(os.environ, RETAIL_URL='http://retail-test.localhost:'+str(server.server_port),
                     RETAIL_SID=sid, VAT_COMPANY=company, VAT_CUSTOMER=customer, VAT_ITEM=item),
            check=True, timeout=150)
    finally:
        server.shutdown()


if __name__ == '__main__':
    spec = importlib.util.spec_from_file_location('harness', Path(__file__).with_name('product_conversion_isolated.py'))
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    harness.scenario = scenario
    harness.main()
