"""Rollback-only serial API integration using the established local POS fixture."""
import copy
import json
import frappe
from frappe.utils import nowdate, nowtime, add_days


def run_integration():
    if frappe.local.site != "retail-test.localhost":
        raise RuntimeError("Serial fixture is restricted to retail-test.localhost")
    frappe.set_user("Administrator")
    frappe.flags.in_test = True
    try:
        from retail.api import pos_sync
        from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
        base = json.loads(frappe.db.get_value('POS Sync Log', 'PSL-2644', 'request_json'))
        counter = pos_sync._counter(base['branch'], base['counter_code'], completed=True)
        token = frappe.generate_hash(length=10)
        item = frappe.get_doc(dict(doctype='Item', item_code='SERIAL-PATCH-'+token,
            item_name='Serial patch verification', item_group=frappe.db.get_value('Item Group', {'is_group':0}, 'name'),
            stock_uom='Nos', is_stock_item=1, is_sales_item=1, has_serial_no=1,
            item_defaults=[dict(company=counter.company, default_warehouse=counter.warehouse,
                income_account=frappe.get_cached_value('Company',counter.company,'default_income_account'),
                expense_account=frappe.get_cached_value('Company',counter.company,'default_expense_account'),
                buying_cost_center=counter.cost_center, selling_cost_center=counter.cost_center)])).insert()
        serial = 'SERIAL-'+token
        make_stock_entry(item_code=item.name, qty=1, to_warehouse=counter.warehouse,
            company=counter.company, rate=10, serial_no=serial, use_serial_batch_fields=1,
            posting_date=add_days(nowdate(),-1))
        # Existing master endpoint, including a future incremental cursor.
        master = pos_sync.get_pos_master_data(counter.branch,counter.counter_code,'2099-01-01 00:00:00')
        downloaded = next(r for r in master['items'] if r.item_code==item.name)
        assert downloaded.has_serial_no==1 and downloaded.serial_numbers==[serial], downloaded
        payload=frappe._dict(copy.deepcopy(base))
        payload.update(external_pos_reference='SERIAL-PATCH-'+token,posting_date=nowdate(),posting_time=nowtime(),
            items=[dict(item_code=item.name,qty=1,rate=100,uom='Nos',conversion_factor=1,serial_no=serial,
                        rate_includes_vat=0,vat_rate=0,amount=100,net_amount=100,vat_amount=0)],
            payments=[dict(mode_of_payment='Cash',amount=100)],grand_total=100,rounded_total=100,
            net_total=100,vat_amount=0,discount_amount=0)
        result=pos_sync.create_pos_invoice(payload)
        assert result.get('invoice_name'), (result,frappe.db.get_value('POS Accepted Transaction',result.get('accepted_transaction'),'exception_reason'))
        invoice=frappe.get_doc('POS Invoice',result['invoice_name'])
        assert invoice.docstatus==1 and invoice.items[0].serial_no==serial
        assert frappe.db.get_value('Serial No',serial,'warehouse') in ('',None)
        accounting=invoice.consolidated_invoice
        assert accounting and frappe.db.get_value('Sales Invoice',accounting,'docstatus')==1
        sle=frappe.db.get_value('Stock Ledger Entry',{'voucher_no':accounting,'item_code':item.name,'is_cancelled':0},['actual_qty','serial_and_batch_bundle'],as_dict=True)
        assert sle and sle.actual_qty==-1 and sle.serial_and_batch_bundle, sle
        assert frappe.db.exists('Serial and Batch Entry',{'parent':sle.serial_and_batch_bundle,'serial_no':serial})
        master=pos_sync.get_pos_master_data(counter.branch,counter.counter_code,'2099-01-01 00:00:00')
        assert next(r for r in master['items'] if r.item_code==item.name).serial_numbers==[]
        retry=pos_sync.create_pos_invoice(payload)
        assert retry.get('duplicate'),retry
        conflict=frappe._dict(copy.deepcopy(payload))
        conflict.external_pos_reference='SERIAL-CONFLICT-'+token
        conflict_result=pos_sync.create_pos_invoice(conflict)
        assert conflict_result.get('settlement_status')=='Reconciliation Exception', conflict_result
        assert not conflict_result.get('invoice_name'), conflict_result
        returned=frappe._dict(copy.deepcopy(payload))
        returned.update(external_pos_reference='SERIAL-RETURN-'+token,original_pos_invoice=invoice.name,
            original_external_pos_reference=payload.external_pos_reference)
        return_result=pos_sync.create_pos_return_invoice(returned)
        assert return_result.get('return_invoice'), (return_result,frappe.db.get_value('POS Accepted Transaction',return_result.get('accepted_transaction'),'exception_reason'))
        assert frappe.db.get_value('Serial No',serial,'warehouse')==counter.warehouse
        print('PASS: serialized return through existing API restores the selected serial to counter warehouse')
        print('PASS: incremental master serial snapshot, existing sales API acceptance, submitted POS and Sales Invoice, exact outgoing serial bundle, sold serial removed, idempotent retry')
    finally:
        frappe.db.rollback()
