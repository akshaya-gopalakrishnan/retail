"""Rollback-only end-to-end checks using the local POS integration fixture."""
import copy
import json
from unittest.mock import patch

import frappe
from frappe.utils import flt, nowdate, nowtime


def run_integration(naming_only=False):
    if frappe.local.site != "retail-test.localhost":
        raise RuntimeError("This fixture is restricted to retail-test.localhost")
    from retail.api import pos_sync
    from retail.pos_realtime import post_invoice, make_closing_entry_from_opening, closing_invoices
    from erpnext.stock.utils import get_stock_balance

    frappe.set_user("Administrator")
    frappe.flags.in_test = True
    results = []
    token = frappe.generate_hash(length=12)
    base = json.loads(frappe.db.get_value("POS Sync Log", "PSL-2644", "request_json"))
    base.update(posting_date=nowdate(), posting_time=nowtime())
    # Keep the real completed-sale payload, pricing and hooks.
    def sale(suffix, **changes):
        payload = {**copy.deepcopy(base), "external_pos_reference": f"realtime-{token}-{suffix}", **changes}
        response = pos_sync.create_pos_invoice(payload)
        assert response["status"] == "Success", response
        return payload, frappe.get_doc("POS Invoice", response["invoice_name"])

    def ledger(invoice):
        assert invoice.consolidated_invoice, invoice.name
        si = frappe.get_doc("Sales Invoice", invoice.consolidated_invoice)
        assert si.docstatus == 1 and si.update_stock
        assert abs(si.grand_total - invoice.grand_total) < 0.01, (si.grand_total, invoice.grand_total)
        assert abs(si.paid_amount - invoice.paid_amount) < 0.01
        assert abs(si.outstanding_amount - invoice.outstanding_amount) < 0.01
        assert abs(si.total_taxes_and_charges - invoice.total_taxes_and_charges) < 0.01
        gl = frappe.get_all("GL Entry", filters={"voucher_type": "Sales Invoice", "voucher_no": si.name,
            "is_cancelled": 0}, fields=["debit", "credit"])
        assert gl and abs(sum(r.debit-r.credit for r in gl)) < 0.01, gl
        sle = frappe.get_all("Stock Ledger Entry", filters={"voucher_type": "Sales Invoice",
            "voucher_no": si.name, "is_cancelled": 0}, fields=["item_code", "warehouse", "actual_qty"])
        for item in invoice.items:
            if frappe.get_cached_value("Item", item.item_code, "is_stock_item"):
                assert abs(sum(r.actual_qty for r in sle if r.item_code == item.item_code
                    and r.warehouse == item.warehouse) + sum(i.stock_qty for i in invoice.items
                    if i.item_code == item.item_code and i.warehouse == item.warehouse)) < 0.000001, sle
        return si

    try:
        backend_counter = frappe.db.get_value("Series", "retail-short-code:SI", "current", order_by="name")
        payload, doc = sale("paid")
        si = ledger(doc)
        assert doc.name.startswith("POS-") and si.name.startswith("PSI-"), (doc.name, si.name)
        assert frappe.db.get_value("Series", "retail-short-code:SI", "current", order_by="name") == backend_counter
        assert doc.custom_pos_transaction_type == "POS Invoice"
        logs = frappe.get_all("POS Sync Log", filters={"external_reference": payload["external_pos_reference"]},
            fields=["linked_invoice_type", "linked_invoice", "custom_accounting_invoice"])
        assert len(logs) == 1, logs
        assert logs[0].linked_invoice_type == "POS Invoice" and logs[0].linked_invoice == doc.name
        assert logs[0].custom_accounting_invoice == si.name
        item = doc.items[0]
        bin_qty = frappe.db.get_value("Bin", {"item_code": item.item_code, "warehouse": item.warehouse}, "actual_qty")
        assert bin_qty == get_stock_balance(item.item_code, item.warehouse)
        feed = [frappe._dict(item_code=item.item_code)]
        pos_sync._apply_current_stock_to_items(feed, item.warehouse)
        assert feed[0].current_stock == bin_qty
        assert post_invoice(doc) == si.name
        assert pos_sync.create_pos_invoice(payload)["duplicate"] is True
        assert frappe.db.count("POS Sync Log", {"external_reference": payload["external_pos_reference"]}) == 1
        assert frappe.db.count("POS Invoice Reference", {"parenttype": "POS Invoice Merge Log", "pos_invoice": doc.name}) == 1
        from retail.retail_app.report.profitability import profitability_rows
        rows = profitability_rows(frappe._dict(pos_invoice=doc.name), "POS Invoice")
        assert rows and all(r.cost_amount is not None for r in rows), rows
        assert abs(sum(r.net_sales for r in rows) - doc.base_net_total) < 0.01
        assert {r.sales_invoice for r in rows} == {si.name}
        results.append("paid receipt: immediate balanced GL, stock ledger, Bin, stock API and report costs; retry posts once")

        _, partial = sale("partial", payments=[{**base["payments"][0], "amount": 1}])
        ledger(partial)
        _, credit = sale("credit", payments=[])
        ledger(credit)
        assert partial.custom_pos_transaction_type == credit.custom_pos_transaction_type == "Credit Sale"
        assert int(partial.name.split("-")[1]) == int(doc.name.split("-")[1]) + 1
        assert int(credit.name.split("-")[1]) == int(partial.name.split("-")[1]) + 1
        results.append("partial and credit receipts: stock, cash and outstanding balances posted immediately")

        if naming_only:
            assert frappe.db.get_value("Series", "retail-short-code:SI", "current", order_by="name") == backend_counter
            return {"passed": results + ["independent POS and accounting sequences; backend SI counter unchanged"],
                "business_data": "rolled back"}

        # The refund uses its original receipt and reverses stock immediately.
        returned_payload = {**copy.deepcopy(payload), "external_pos_reference": f"realtime-{token}-return",
            "original_pos_invoice": doc.name, "posting_time": nowtime()}
        returned = pos_sync.create_pos_return_invoice(returned_payload)
        assert returned["status"] == "Success", returned
        refund = frappe.get_doc("POS Invoice", returned["return_invoice"])
        assert refund.custom_pos_transaction_type == "Return"
        refund_si = ledger(refund)
        assert refund_si.return_against == si.name
        results.append("return: linked credit note and positive stock movement posted immediately")

        # Create a reconciliation window containing only this test's receipts.
        opening = frappe.get_doc({"doctype": "POS Opening Entry", "company": doc.company,
            "pos_profile": doc.pos_profile, "user": doc.owner,
            "period_start_date": f"{doc.posting_date} {doc.posting_time}",
            "balance_details": [{"mode_of_payment": base["payments"][0]["mode_of_payment"], "opening_amount": 10}]})
        opening.insert(); opening.submit()
        closing = make_closing_entry_from_opening(opening)
        closing.insert()
        receipts = {r.pos_invoice for r in closing.pos_transactions}
        assert {doc.name, partial.name, credit.name, refund.name} <= receipts, receipts
        gl_before = frappe.db.count("GL Entry")
        sle_before = frappe.db.count("Stock Ledger Entry")
        closing.submit()
        assert frappe.db.count("GL Entry") == gl_before
        assert frappe.db.count("Stock Ledger Entry") == sle_before
        assert not ({d.name for d in closing_invoices(closing.period_start_date, closing.period_end_date,
            closing.pos_profile, closing.user)} & receipts)
        closing.cancel()
        assert frappe.db.count("GL Entry") == gl_before
        assert frappe.db.count("Stock Ledger Entry") == sle_before
        assert frappe.db.get_value("Sales Invoice", si.name, "docstatus") == 1
        results.append("closing includes posted receipts; submit/cancel create no extra ledger effects")

        # Reverse a standalone receipt without a closing dependency.
        partial.reload()
        partial_si = partial.consolidated_invoice
        partial.cancel()
        assert frappe.db.get_value("Sales Invoice", partial_si, "docstatus") == 2
        results.append("receipt cancellation reverses its individual accounting posting")

        # Reproduce the existing sub-cent allocation discrepancy on a refund.
        original = frappe.get_doc("POS Invoice", "POS-62")
        post_invoice(original)
        old_refund = frappe.get_doc("POS Invoice", "POS-63")
        post_invoice(old_refund)
        ledger(old_refund)
        results.append("sub-cent return-rate allocation posts without changing the currency-rounded refund")

        # A ledger failure must not acknowledge or retain a submitted receipt.
        from erpnext.accounts.doctype.pos_invoice_merge_log.pos_invoice_merge_log import POSInvoiceMergeLog
        bad = {**copy.deepcopy(base), "external_pos_reference": f"realtime-{token}-failure"}
        with patch.object(POSInvoiceMergeLog, "process_merging_into_sales_invoice", side_effect=frappe.ValidationError("Ledger failure")):
            response = pos_sync.create_pos_invoice(bad)
        assert response["status"] == "Failed", response
        assert not frappe.db.exists("POS Invoice", {"external_pos_reference": bad["external_pos_reference"]})
        results.append("posting failure rolls back the receipt; no false success")
        return {"passed": results, "business_data": "rolled back"}
    finally:
        frappe.db.rollback()


def run_rounding_regression():
    """Replay POS-83 with a fractional total; never retain business records."""
    if frappe.local.site != "retail-test.localhost":
        raise RuntimeError("This fixture is restricted to retail-test.localhost")
    from retail.api import pos_sync

    frappe.set_user("Administrator")
    frappe.flags.in_test = True
    try:
        payload = json.loads(frappe.db.get_value("POS Sync Log", "PSL-2918", "request_json"))
        payload["external_pos_reference"] = "rounding-regression-" + frappe.generate_hash(length=12)
        response = pos_sync.create_pos_invoice(payload)
        assert response["status"] == "Success", response
        receipt = frappe.get_doc("POS Invoice", response["invoice_name"])
        accounting = frappe.get_doc("Sales Invoice", receipt.consolidated_invoice)
        assert accounting.disable_rounded_total == 1
        assert receipt.outstanding_amount == accounting.outstanding_amount == 144.76
        assert flt(accounting.grand_total, 2) == flt(receipt.grand_total, 2) == 3203.81
        assert flt(accounting.paid_amount, 2) == 3059.05
        gl = frappe.get_all("GL Entry", filters={"voucher_type": "Sales Invoice",
            "voucher_no": accounting.name, "is_cancelled": 0}, fields=["debit", "credit"])
        assert gl and abs(sum(row.debit - row.credit for row in gl)) < 0.01
        assert pos_sync.create_pos_invoice(payload)["duplicate"] is True
        return {"passed": "POS-83 fractional total, matching outstanding, balanced GL and idempotent retry",
            "business_data": "rolled back"}
    finally:
        frappe.db.rollback()
