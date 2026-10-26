"""Readable report names alongside stable record IDs; never change grouping or facts."""
import frappe

from retail.chart_labels import names_for

LINK_NAMES = {
    'Item': ('item_name', 'Item Name'),
    'Employee': ('employee_name', 'Employee Name'),
    'Customer': ('customer_name', 'Customer Name'),
    'Supplier': ('supplier_name', 'Supplier Name'),
    'POS Branch Counter': ('counter_name', 'Counter Name'),

}
DATA_NAMES = {
    'cashier': ('cashier_name', 'Cashier Name'),
    'pos_cashier': ('cashier_name', 'Cashier Name'),
    'responsible_user': ('responsible_user_name', 'Responsible Person'),
    'created_by': ('created_by_name', 'Created By Name'),
    'cancelled_by': ('cancelled_by_name', 'Cancelled By Name'),
    'counter': ('counter_name', 'Counter Name'),
    'pos_counter': ('counter_name', 'Counter Name'),

}


def user_names(values):
    values = sorted({v for v in values if isinstance(v, str) and v})
    if not values or not frappe.has_permission('User', 'read'):
        return {}
    return {r.name: r.full_name or r.name for r in frappe.get_list(
        'User', filters={'name': ['in', values]}, fields=['name', 'full_name'], limit_page_length=0)}


def enrich_result(result):
    """Idempotently add missing name columns to an already permission-filtered result."""
    if not isinstance(result, dict):
        return result
    columns, rows = result.get('columns'), result.get('result')
    if not isinstance(columns, list) or not isinstance(rows, list):
        return result
    fields = {c.get('fieldname') for c in columns if isinstance(c, dict)}
    output = []
    cache = {}

    def lookup(doctype, values):
        ids = frozenset(v for v in values if isinstance(v, str) and v)
        key = (doctype, ids)
        if key not in cache:
            cache[key] = user_names(ids) if doctype == 'User' else names_for(doctype, ids)
        return cache[key]

    for column in columns:
        output.append(column)
        if not isinstance(column, dict) or column.get('hidden'):
            continue
        source, doctype = column.get('fieldname'), column.get('options')
        if column.get('fieldtype') == 'Link' and doctype in LINK_NAMES:
            target, label = LINK_NAMES[doctype]
            if doctype == 'Employee' and source in ('cashier_employee', 'pos_cashier_employee'):
                target, label = 'cashier_name', 'Cashier Name'
            # A cashier/driver name is already the readable Employee companion.
            if doctype == 'Employee' and fields.intersection({'cashier_name', 'driver_name'}):
                continue
        elif column.get('fieldtype') == 'Link' and doctype == 'User':
            target, label = source + '_name', column.get('label', 'User') + ' Name'
        elif column.get('fieldtype') == 'Data' and source in DATA_NAMES:
            target, label = DATA_NAMES[source]
            doctype = 'POS Branch Counter' if source in ('counter', 'pos_counter') else 'User'
        else:
            continue
        if target in fields:
            continue
        values = [r.get(source) for r in rows if isinstance(r, dict)]
        mapping = lookup(doctype, values)
        employees = {}
        cashier_field = source in ('cashier', 'pos_cashier', 'cashier_employee', 'pos_cashier_employee')
        user_mapping = {}
        if cashier_field or source == 'responsible_user':
            employee_ids = values + [r.get('cashier_employee') or r.get('pos_cashier_employee')
                                     for r in rows if isinstance(r, dict)]
            if cashier_field:
                employee_ids += [r.get('cashier') or r.get('pos_cashier') for r in rows if isinstance(r, dict)]
                user_mapping = lookup('User', employee_ids)
            employees = lookup('Employee', employee_ids)
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = row.get(source)
            # Cashier strings can be Employee IDs or User IDs; never treat one as the other.
            employee = row.get('cashier_employee') or row.get('pos_cashier_employee')
            cashier = (row.get('cashier') or row.get('pos_cashier')) if cashier_field else None
            row[target] = (row.get(target) or employees.get(employee) or employees.get(value)
                           or employees.get(cashier) or user_mapping.get(cashier)
                           or mapping.get(value) or value or cashier)
        fields.add(target)
        output.append(dict(fieldname=target, label=label, fieldtype='Data', width=190))
        if column.get('label') in ('Item', 'Cashier', 'Cashier Employee', 'Counter', 'Customer', 'Supplier'):
            column = dict(column, label=column['label'] + ' Code')
            output[-2] = column
    result['columns'] = output
    return result
