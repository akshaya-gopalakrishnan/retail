"""Invoice submit/cancel cache proof in disposable MariaDB/Redis only."""
import importlib.util
from pathlib import Path
from time import perf_counter
import frappe


def scenario():
    from retail.retail_app import retail_dashboard as d
    from retail.desk_speed import clear_caches
    from frappe.utils import nowdate
    assert frappe.db.sql('select database()')[0][0] == 'conversion_validation'
    frappe.flags.in_test = False
    frappe.form_dict = frappe._dict()
    company = frappe.db.get_value('Company', {}, 'name')
    customer = frappe.db.get_value('Customer', {'disabled': 0, 'custom_is_van_customer': 0}, 'name')
    item = frappe.get_doc(dict(doctype='Item', item_code='Desk Speed Cache Proof', item_name='Desk Speed Cache Proof',
        item_group=frappe.db.get_value('Item Group', {'is_group':0}, 'name'), stock_uom='Nos', is_stock_item=0, custom_sales_rate_entry=17, custom_sales_rate_includes_vat=0)).insert()
    frappe.db.commit()
    contexts = [dict(company=company)]
    clear_caches()
    before = d.get_business_home_profit_cards(contexts)[0]
    started = perf_counter();cached = d.get_business_home_profit_cards(contexts)[0];elapsed = perf_counter()-started
    assert before == cached
    doc = frappe.new_doc('Sales Invoice')
    doc.update(dict(company=company, customer=customer, update_stock=0, posting_date=nowdate(),
        selling_price_list='Standard Selling', currency=frappe.get_cached_value('Company',company,'default_currency'), conversion_rate=1))
    doc.append('items', dict(item_code=item.name, qty=1, uom='Nos', conversion_factor=1))
    # This scenario tests cache invalidation, not the separate password UI.
    # Grant only that unrelated approval guard inside the disposable fixture.
    from unittest.mock import patch
    with patch('retail.backend_sales_admin.approved', return_value=True):
        doc.insert(); doc.submit()
    frappe.db.commit()
    after = d.get_business_home_profit_cards(contexts)[0]
    assert abs(after['sales'] - before['sales'] - doc.base_net_total) < .001, (before,after,doc.base_net_total)
    assert after['count'] == before['count'] + 1
    doc.cancel();frappe.db.commit()
    cancelled = d.get_business_home_profit_cards(contexts)[0]
    assert cancelled['sales'] == before['sales'] and cancelled['count'] == before['count']
    print(dict(cache_hit_ms=round(elapsed*1000,2), added_sales=after['sales']-before['sales'],
               submit_invalidation=True,cancel_invalidation=True), flush=True)
    # A native aggregate must retain its saved filters/calculation.
    from retail.sidebar_services import workspace_dependencies
    from frappe.desk.doctype.number_card.number_card import get_result
    names=workspace_dependencies()['Number Card']
    for name in names:
        card=frappe.get_cached_doc('Number Card',name)
        if card.type=='Document Type':
            filters=frappe.parse_json(card.filters_json or '[]')
            expected=get_result(card.as_dict(),filters)
            actual=d.get_business_home_profit_cards([{'card_name':name,'filters':filters}])[0]['value']
            assert expected==actual,(name,expected,actual)
    print('PASS: native card results match; actual submitted/cancelled invoice refreshes cached values.',flush=True)


if __name__=='__main__':
    spec=importlib.util.spec_from_file_location('harness',Path(__file__).with_name('product_conversion_isolated.py'))
    harness=importlib.util.module_from_spec(spec);spec.loader.exec_module(harness)
    harness.scenario=scenario
    harness.main()
