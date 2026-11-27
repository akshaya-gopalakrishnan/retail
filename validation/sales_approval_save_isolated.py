"""Real approval and Save through Chromium, only in disposable DB/Redis."""
import importlib.util
import inspect
import os
from pathlib import Path
import frappe

BASE = Path(__file__).parent

def scenario():
    assert frappe.db.sql('select database()')[0][0] == 'conversion_validation'
    from retail import backend_sales_admin as policy
    original_validate = policy.validate
    def traced_validate(doc, method=None):
        try:
            return original_validate(doc, method)
        except frappe.PermissionError:
            if getattr(doc, '_action', None):
                print('SAVE APPROVAL DIFF', {'header':policy.header_snapshot(doc),
                      'rows':[policy.row_snapshot(row) for row in doc.items],
                      'grants':[{'header':g.get('header'),'rows':g.get('rows')} for g in policy.valid_grants(doc)]}, flush=True)
            raise
    policy.validate = traced_validate
    from frappe.utils.password import update_password
    password = frappe.generate_hash(length=28)
    update_password('cashier@gmail.com', password)
    os.environ['APPROVAL_TEST_PASSWORD'] = password
    spec = importlib.util.spec_from_file_location('vat_browser', BASE/'trading_vat_isolated.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = inspect.getsource(module.browser).replace("'trading_vat_browser.cjs'", "'sales_approval_save_isolated.cjs'")
    exec(source, module.__dict__)
    module.browser('', '', '')

if __name__ == '__main__':
    spec = importlib.util.spec_from_file_location('harness', BASE/'product_conversion_isolated.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.scenario = scenario
    module.main()
