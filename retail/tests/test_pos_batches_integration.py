"""Rollback-only checks using the established local POS fixture."""
import copy
import json

import frappe
from frappe.utils import add_days, nowdate, nowtime


def run_integration(with_serial=False, omit_tracking=False):
    if frappe.local.site != "retail-test.localhost":
        raise RuntimeError("Batch fixture is restricted to retail-test.localhost")
    frappe.set_user("Administrator")
    frappe.flags.in_test = True
    try:
        from retail.api import pos_sync
        from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
        base = json.loads(frappe.db.get_value("POS Sync Log", "PSL-2644", "request_json"))
        counter = pos_sync._counter(base["branch"], base["counter_code"], completed=True)
        token = frappe.generate_hash(length=10)
        item = frappe.get_doc(dict(doctype="Item", item_code="BATCH-PATCH-"+token,
            item_name="Batch patch verification", item_group=frappe.db.get_value("Item Group", {"is_group":0}, "name"),
            stock_uom="Nos", is_stock_item=1, is_sales_item=1, has_batch_no=1, has_serial_no=int(with_serial),
            item_defaults=[dict(company=counter.company, default_warehouse=counter.warehouse,
                income_account=frappe.get_cached_value("Company",counter.company,"default_income_account"),
                expense_account=frappe.get_cached_value("Company",counter.company,"default_expense_account"),
                buying_cost_center=counter.cost_center, selling_cost_center=counter.cost_center)])).insert()
        batch = frappe.get_doc(dict(doctype="Batch", batch_id="BATCH-"+token, item=item.name,
                                    expiry_date=add_days(nowdate(),30))).insert()
        serial = "BATCH-SERIAL-"+token if with_serial else None
        make_stock_entry(item_code=item.name,qty=2 if not with_serial else 1,
            to_warehouse=counter.warehouse,company=counter.company,rate=10,batch_no=batch.name,
            serial_no=serial,use_serial_batch_fields=1,posting_date=add_days(nowdate(),-1))
        def snapshot():
            master=pos_sync.get_pos_master_data(counter.branch,counter.counter_code,"2099-01-01 00:00:00")
            return next(r for r in master["items"] if r.item_code==item.name)
        downloaded=snapshot()
        assert downloaded.has_batch_no==1 and downloaded.batches[0]["batch_no"]==batch.name
        assert downloaded.batches[0]["available_qty"]==(1 if with_serial else 2)
        row=dict(item_code=item.name,qty=1,rate=100,uom="Nos",conversion_factor=1,batch_no=batch.name,
                 rate_includes_vat=0,vat_rate=0,amount=100,net_amount=100,vat_amount=0)
        if with_serial:
            row["serial_no"]=serial
        if omit_tracking:
            row.pop("serial_no", None)
            row.pop("batch_no", None)
        payload=frappe._dict(copy.deepcopy(base))
        payload.update(external_pos_reference="BATCH-SALE-"+token,posting_date=nowdate(),posting_time=nowtime(),
            items=[row],payments=[dict(mode_of_payment="Cash",amount=100)],grand_total=100,rounded_total=100,
            net_total=100,vat_amount=0,discount_amount=0)
        result=pos_sync.create_pos_invoice(payload)
        assert result.get("invoice_name"), (result,frappe.db.get_value("POS Accepted Transaction",result.get("accepted_transaction"),"exception_reason"))
        invoice=frappe.get_doc("POS Invoice",result["invoice_name"])
        sle=frappe.db.get_value("Stock Ledger Entry",dict(voucher_no=invoice.consolidated_invoice,
            item_code=item.name,is_cancelled=0),["actual_qty","serial_and_batch_bundle"],as_dict=True)
        assert sle.actual_qty==-1 and frappe.db.exists("Serial and Batch Entry",dict(parent=sle.serial_and_batch_bundle,batch_no=batch.name))
        after=snapshot().batches
        assert after==[] if with_serial else after[0]["available_qty"]==1
        assert pos_sync.create_pos_invoice(payload).get("duplicate")
        returned=frappe._dict(copy.deepcopy(payload))
        returned.update(external_pos_reference="BATCH-RETURN-"+token,original_pos_invoice=invoice.name,
                        original_external_pos_reference=payload.external_pos_reference)
        result=pos_sync.create_pos_return_invoice(returned)
        assert result.get("return_invoice"), (result,frappe.db.get_value("POS Accepted Transaction",result.get("accepted_transaction"),"exception_reason"))
        assert snapshot().batches[0]["available_qty"]==(1 if with_serial else 2)
        print("PASS: batch master, sale stock bundle, updated availability, retry and return; serialized:",with_serial,"omitted tracking:",omit_tracking)
    finally:
        frappe.db.rollback()
        frappe.clear_cache()
