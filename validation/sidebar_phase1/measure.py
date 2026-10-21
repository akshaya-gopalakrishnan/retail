import frappe, json, time, importlib.util, contextlib
from unittest.mock import patch
from collections import Counter
from pathlib import Path
from retail import workspace_permissions as after
from retail.access_defaults import PROFILES
import frappe.permissions, frappe.utils.user
# Capture the pre-change workspace_permissions.py and pass its path as argv[1].
import sys
spec=importlib.util.spec_from_file_location('sidebar_before',sys.argv[1]); before=importlib.util.module_from_spec(spec); spec.loader.exec_module(before)
site='retail-test.localhost'; sites='/home/adler/frappe-bench/sites'
cases=[('Administrator','Administrator',None,None),('Celesta Super Administrator','akshayagopal1@gmail.com',None,None),('Customer Administrator','john.cashier@gmail.com',None,None),('Store Manager preset','demo.manager@example.com',PROFILES['Store Manager'],None),('restricted module preset','demo.manager@example.com',PROFILES['Store Manager'],['Stock','Buying']),('Driver/Van live','vsdriver@gmail.com',None,None),('Van Sales User preset','demo.manager@example.com',PROFILES['Van Sales User'],None),('Cashier preset','demo.cashier1@example.com',PROFILES['Cashier'],None),('Normal User preset','demo.cashier2@example.com',PROFILES['Normal User'],None)]
results=[]
for label,user,roles,blocked in cases:
    outputs={}; stats={}
    for version,module in [('before',before),('after',after)]:
        for temperature in ['cold','warm']:
            frappe.init(site=site,sites_path=sites);frappe.connect();frappe.set_user(user)
            if temperature=='cold': frappe.clear_cache()
            with contextlib.ExitStack() as stack:
                if roles is not None:
                    role_list=list(roles)+['All','Guest','Desk User']
                    for target in [frappe,frappe.permissions,frappe.utils.user]: stack.enter_context(patch.object(target,'get_roles',return_value=role_list))
                if blocked is not None:
                    from frappe.core.doctype.user.user import User
                    stack.enter_context(patch.object(User,'get_blocked_modules',side_effect=lambda:list(blocked)))
                original=frappe.db.sql;queries=[]
                def sql(query,*args,**kwargs):
                    queries.append(str(query));return original(query,*args,**kwargs)
                with patch.object(frappe.db,'sql',side_effect=sql):
                    start=time.perf_counter(); output=module.get_workspace_sidebar_items(); elapsed=(time.perf_counter()-start)*1000
                discovery=[q for q in queries if ('`tabDocType`' in q and '`custom`' in q) or ('`tabReport`' in q and '`is_standard`' in q and 'order by' in q.lower())]
                stats[version+'_'+temperature]={'ms':round(elapsed,2),'sql':len(queries),'discovery_queries':len(discovery),'max_identical_discovery':max(Counter(discovery).values(),default=0)}
                outputs[version+'_'+temperature]=json.loads(frappe.as_json(output))
            frappe.db.rollback();frappe.destroy()
    equal=all(o==outputs['before_cold'] for o in outputs.values())
    row={'case':label,'identical_payloads':equal,'pages':len(outputs['after_cold']['pages']),**stats};results.append(row);print(json.dumps(row),flush=True)
    if not equal:
        Path('/tmp/sidebar_mismatch_'+str(len(results))+'.json').write_text(json.dumps(outputs,indent=2))
Path('/home/adler/frappe-bench/apps/retail/validation/sidebar_phase1/results.json').write_text(json.dumps(results,indent=2))
