"""Read-only live invoice-execution benchmark; no fixture/accounting writes.

Before disables only the memo by calling the unchanged standalone invoice path.
Repeated names measure executions, not a claim of 1,000 distinct live invoices.
Run from sites: ../env/bin/python ../apps/retail/validation/measure_profitability_vat_memo.py
"""
import json
import time
from unittest.mock import patch
import frappe
from retail.retail_app.report import profitability as p


def run():
    frappe.init(site='retail-test.localhost')
    frappe.connect()
    frappe.set_user('Administrator')
    output = {'site': 'retail-test.localhost', 'dataset': 'Repeated live submitted invoice executions; no writes', 'results': []}
    original_list = frappe.get_list
    original_rows, original_vat, original_sql = p.invoice_rows, p.recorded_vat_accounts, frappe.db.sql
    try:
        seeds = frappe.get_list('Sales Invoice', filters={'docstatus': 1}, fields=['name', 'company'], limit_page_length=10)
        assert seeds, 'No submitted invoice dataset'
        company = seeds[0].company
        names = [s.name for s in seeds if s.company == company]
        output.update(company=company, seed_invoices=names)
        filters = dict(company=company, from_date='2000-01-01', to_date='2099-12-31')
        # Warm metadata/document caches equally; Account lookup itself stays unchanged.
        with patch.object(frappe, 'get_list', side_effect=lambda dt, *a, **kw: names if dt == 'Sales Invoice' else original_list(dt, *a, **kw)):
            p.profitability_rows(filters)
        for n in (10, 100, 500, 1000):
            executions = [names[i % len(names)] for i in range(n)]
            results = []
            for memo in (False, True):
                counts = {'sql': 0, 'vat_lookups': 0}
                def sql(*args, **kwargs):
                    counts['sql'] += 1
                    return original_sql(*args, **kwargs)
                def vat(*args, **kwargs):
                    counts['vat_lookups'] += 1
                    return original_vat(*args, **kwargs)
                def rows(doc, **kwargs):
                    return original_rows(doc, **kwargs) if memo else original_rows(doc)
                with patch.object(frappe, 'get_list', side_effect=lambda dt, *a, **kw: executions if dt == 'Sales Invoice' else original_list(dt, *a, **kw)), patch.object(
                        frappe.db, 'sql', side_effect=sql), patch.object(p, 'recorded_vat_accounts', side_effect=vat), patch.object(
                        p, 'invoice_rows', side_effect=rows):
                    start = time.perf_counter()
                    data = p.profitability_rows(filters)
                    counts['seconds'] = round(time.perf_counter()-start, 4)
                results.append((data, counts))
            assert results[0][0] == results[1][0], 'Row/status inequality'
            assert results[0][1]['vat_lookups'] == n and results[1][1]['vat_lookups'] == 1
            result = dict(executions=n, before=results[0][1], after=results[1][1], exact_equal=True)
            output['results'].append(result)
            print(json.dumps(result), flush=True)
        # Compare actual permission-aware selections and dimension filters too.
        output['live_filters'] = []
        seed_doc = frappe.get_doc('Sales Invoice', names[0])
        dimensions = [{}, {'company': company}, {'company': '__NO_MATCH__'}]
        for key, field in [('branch', 'branch'), ('counter', 'custom_counter')]:
            dimensions.append({key: seed_doc.get(field) or '__NO_MATCH__'})
        for dims in dimensions:
            actual_filters = dict(from_date='2000-01-01', to_date='2099-12-31', **dims)
            with patch.object(p, 'invoice_rows', side_effect=lambda d, **kw: original_rows(d)):
                before = p.profitability_rows(actual_filters)
            after = p.profitability_rows(actual_filters)
            assert before == after
            output['live_filters'].append(dict(filters=dims, rows=len(after), exact_equal=True))
        with patch.object(p, 'invoice_rows', side_effect=lambda d, **kw: original_rows(d)):
            before = p.profitability_rows(dict(from_date='2000-01-01', to_date='2099-12-31'), doctype='POS Invoice')
        after = p.profitability_rows(dict(from_date='2000-01-01', to_date='2099-12-31'), doctype='POS Invoice')
        assert before == after
        output['live_pos'] = dict(rows=len(after), exact_equal=True)
        with open('../apps/retail/validation/profitability_vat_memo_measurements.json', 'w') as f:
            json.dump(output, f, indent=2)
    finally:
        frappe.db.rollback()
        frappe.destroy()


if __name__ == '__main__':
    run()
