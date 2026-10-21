"""Transaction-only scale benchmark. Raw fixture copies never commit or repost."""
import json
import time
from unittest.mock import patch

import frappe
from retail.retail_app import retail_dashboard as dashboard


def run():
    frappe.init(site='retail-test.localhost')
    frappe.connect()
    frappe.set_user('Administrator')
    output = []
    try:
        names = frappe.get_list('Sales Invoice', filters={'docstatus': 1}, pluck='name', limit_page_length=10)
        seeds = [frappe.get_doc('Sales Invoice', name) for name in names]
        original_sql, original_doc = frappe.db.sql, frappe.get_doc
        day = '2099-10-08'
        for n in range(1000):
            source = seeds[n % len(seeds)]
            doc = frappe.get_doc(source.as_dict())
            doc.name = f'BH-SHARING-TEST-{n}'
            doc.posting_date = day
            item_map = {}
            for child in doc.get_all_children():
                old_name = child.name
                child.name = frappe.generate_hash(length=20)
                child.parent = doc.name
                item_map[old_name] = child.name
            for field in doc.meta.fields:
                if field.unique:
                    doc.set(field.fieldname, None)
            doc.db_insert()
            for child in doc.get_all_children():
                child.db_insert()
            for doctype in ('GL Entry', 'Stock Ledger Entry'):
                for name in frappe.get_all(doctype, filters={'voucher_type': 'Sales Invoice', 'voucher_no': source.name}, pluck='name'):
                    entry = frappe.get_doc(doctype, name)
                    entry.name = frappe.generate_hash(length=20)
                    entry.voucher_no = doc.name
                    entry.posting_date = day
                    if doctype == 'Stock Ledger Entry':
                        entry.voucher_detail_no = item_map.get(entry.voucher_detail_no, entry.voucher_detail_no)
                    for field in entry.meta.fields:
                        if field.unique:
                            entry.set(field.fieldname, None)
                    entry.db_insert()
            if n + 1 not in (10, 100, 500, 1000):
                continue
            counts = {'sql': 0, 'loads': 0}
            def sql(*args, **kwargs):
                counts['sql'] += 1
                return original_sql(*args, **kwargs)
            def get_doc(*args, **kwargs):
                if args and args[0] == 'Sales Invoice' and len(args) > 1:
                    counts['loads'] += 1
                return original_doc(*args, **kwargs)
            def measure(fn):
                counts.update(sql=0, loads=0)
                start = time.perf_counter()
                result = fn()
                return result, dict(seconds=round(time.perf_counter()-start, 4), **counts)
            frappe.form_dict = frappe._dict()
            with patch.object(dashboard, 'get_today', return_value=frappe.utils.getdate(day)), patch.object(
                    frappe.db, 'sql', side_effect=sql), patch.object(frappe, 'get_doc', side_effect=get_doc):
                old, before = measure(lambda: dict(sales=dashboard.get_today_sales(),
                    profit=dashboard.get_profit_number_card(), count=dashboard.get_invoice_count_today(),
                    returns=dashboard.get_return_amount_today()))
                new, after = measure(lambda: dashboard.get_business_home_profit_cards([{}, {'today_only': True}]))
                assert new == [old, old], (old, new)
            row = dict(invoices=n+1, before=before, after=after, exact_equal=True, values=old)
            output.append(row)
            print(json.dumps(row), flush=True)
        with open('../apps/retail/validation/business_home_profit_sharing_measurements.json', 'w') as f:
            json.dump({'fixture': 'transaction-only copies of ten submitted invoices and their GL/SLE; rolled back', 'results': output}, f, indent=2)
    finally:
        frappe.db.rollback()
        frappe.destroy()


if __name__ == '__main__':
    run()
