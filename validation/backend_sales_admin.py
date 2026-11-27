import frappe
frappe.init(site='retail-test.localhost', sites_path='/home/adler/frappe-bench/sites')
frappe.connect()
from retail import backend_sales_admin as policy
from unittest.mock import patch
try:
    assert frappe.db.exists('Role', 'Admin')
    doc = frappe.get_doc({'doctype':'Sales Invoice', 'is_return':1, 'items':[]})
    with patch.object(policy, 'allowed', return_value=False):
        try:
            policy.validate(doc)
            raise AssertionError('Return allowed')
        except frappe.PermissionError:
            print('PASS return denied without Admin')
        doc.is_return=0
        doc.discount_amount=5
        try:
            policy.validate(doc)
            raise AssertionError('Discount allowed')
        except frappe.PermissionError:
            print('PASS discount denied without Admin')
    with patch.object(policy, 'allowed', return_value=True):
        policy.validate(doc)
        print('PASS Admin operation gate')
    for field in ('is_pos', 'is_consolidated', 'custom_is_van_sale'):
        doc.set(field, 1)
        assert not policy.applies(doc)
        doc.set(field, 0)
    print('PASS POS and van excluded')
    names=frappe.get_all('Sales Invoice', filters={'docstatus':0,'is_return':0,'is_pos':0,'is_consolidated':0}, pluck='name',limit=1)
    if names:
        doc=frappe.get_doc('Sales Invoice',names[0])
        doc._doc_before_save=None
        doc.discount_amount=0
        doc.additional_discount_percentage=0
        with patch.object(policy,'allowed',return_value=False):
            try:
                policy.validate(doc)
                print('PASS draft pricing calculation')
            except frappe.PermissionError:
                print('PASS existing override rejected when treated as new')
finally:
    frappe.db.rollback()
    frappe.destroy()
