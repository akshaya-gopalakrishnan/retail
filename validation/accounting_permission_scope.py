"""Read-only native permission and ownership audit on retail-test.localhost."""
from unittest.mock import patch

import frappe
from frappe.permissions import get_role_permissions

frappe.init(site='retail-test.localhost')
frappe.connect()
try:
    from retail.access_defaults import CUSTOMER_ADMIN_SETUP_DOCTYPES
    from retail.sidebar_registry import target_entries
    checked = 0
    with patch('frappe.get_roles', return_value=['Customer Administrator', 'All', 'Desk User']):
        for name in frappe.get_all('DocType', filters={'istable': 0}, pluck='name'):
            if name in CUSTOMER_ADMIN_SETUP_DOCTYPES:
                continue
            assert not any(row.role == 'Customer Administrator' for row in frappe.get_meta(name).permissions), name
            checked += 1
        frappe.local.role_permissions = {}
        perms = get_role_permissions('User', user='role-scope-audit@example.test')
        assert all(perms.get(action) for action in ('read', 'write', 'create', 'delete'))
    for name in ('Account', 'GL Entry', 'Cost Center', 'Budget'):
        assert [row['workspace'] for row in target_entries('doctype', name)] == ['Accounts']
    for name, owner in (('Sales Invoice', 'Sales Invoices'), ('Purchase Invoice', 'Purchase Invoices'), ('POS Invoice', 'POS Invoices')):
        owners = {row['workspace'] for row in target_entries('doctype', name)}
        assert owner in owners and 'Accounts' not in owners
    print('PASS: no Customer Administrator business grants across', checked, 'DocTypes; User CRUD retained; invoice/POS ownership independent.')
finally:
    frappe.db.rollback()
    frappe.destroy()
