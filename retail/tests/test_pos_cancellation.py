"""Cancellation safety checks and an explicit rollback-only site scenario."""
import copy
import json
import unittest
from unittest.mock import Mock, patch

import frappe
from frappe.utils import flt, nowdate

from retail import pos_cancellation as cancellation, pos_settlements as settlements


class TestPOSCancellation(unittest.TestCase):
    def test_redemption_cannot_be_cancelled_without_reversing_its_source(self):
        invoice = frappe._dict(name="POS-1", docstatus=1, is_return=0, company="Company", pos_counter="COUNTER")
        counter = frappe._dict(name="COUNTER", company="Company")
        for payment in ("Loyalty", "Promotion Voucher", "Voucher Card"):
            with self.subTest(payment=payment), patch("retail.pos_completed_sale.payload_for",
                    return_value={"payments": [{"mode_of_payment": payment, "amount": 10}]}), \
                    patch.object(frappe, "throw", side_effect=frappe.ValidationError):
                with self.assertRaises(frappe.ValidationError):
                    cancellation.validate_sale(invoice, None, counter)

    def test_cancelled_credit_is_excluded_from_summaries(self):
        rows = [frappe._dict(status=status, settlement_type="Credit Sale", requested_amount=amount,
            applied_amount=0, unresolved_amount=0) for status, amount in (("Cancelled", 50), ("Reconciled", 20))]
        self.assertEqual(settlements._summarize_allocations(rows)["credit_sales"], 20)

    def test_cancelled_transaction_cannot_be_recovered(self):
        transaction = frappe._dict(status="Cancelled")
        handler = Mock()
        with patch.object(frappe, "throw", side_effect=frappe.ValidationError):
            with self.assertRaises(frappe.ValidationError):
                settlements.post(transaction, handler)
        handler.assert_not_called()
        with patch.object(frappe, "get_all") as query:
            settlements.resolve_transaction(transaction)
        query.assert_not_called()

    def test_failed_cancellation_rolls_back_claim_and_effects(self):
        from retail.api import pos_sync as api
        payload = frappe._dict(operation_reference="cancel-1", pos_invoice_name="POS-1", reason="Wrong bill",
            branch="Branch", counter_code="Counter")
        counter = frappe._dict(name="COUNTER", branch="Branch", company="Company")
        identity = frappe._dict(company="Company", customer="Customer", pos_branch="Branch",
            pos_counter="COUNTER", external_pos_reference="sale-1")
        db = Mock(get_value=Mock(return_value=identity))
        with patch.object(api, "_assert_pos_user"), patch.object(api, "_counter", return_value=counter), \
                patch.object(frappe, "db", db), patch.object(frappe, "session", frappe._dict(user="Integration")), \
                patch.object(cancellation.pos_operations, "execute", side_effect=RuntimeError("Native reversal failed")):
            with self.assertRaisesRegex(RuntimeError, "Native reversal failed"):
                cancellation.cancel(payload)
        db.rollback.assert_called_once_with(save_point="pos_cancel_request")

    def test_other_counter_is_denied_before_operation(self):
        from retail.api import pos_sync as api
        payload = frappe._dict(operation_reference="cancel-1", pos_invoice_name="POS-1", reason="Wrong bill",
            branch="Branch", counter_code="Counter")
        with patch.object(api, "_assert_pos_user"), patch.object(api, "_counter", return_value=frappe._dict(
                name="OTHER", branch="Branch", company="Company")), patch.object(frappe, "db", Mock(
                get_value=Mock(return_value=frappe._dict(company="Company", pos_branch="Branch", pos_counter="COUNTER")))), \
                patch.object(frappe, "throw", side_effect=frappe.PermissionError), \
                patch.object(cancellation.pos_operations, "execute") as operation:
            with self.assertRaises(frappe.PermissionError):
                cancellation.cancel(payload)
        operation.assert_not_called()


def run_integration():
    """Uses real documents and ledgers on the active test site; always rolls back."""
    if frappe.local.site != "retail-test.localhost":
        raise RuntimeError("Only retail-test.localhost is supported")
    from retail.api import pos_sync as api
    from retail.pos_operations import find
    frappe.set_user("Administrator")
    token = frappe.generate_hash(length=10)
    seed = frappe.get_all("POS Accepted Transaction", filters={"sync_type": "Sales Invoice"},
        fields=["payload_json"], limit=1)[0]
    original = frappe.parse_json(seed.payload_json)
    counter = api._counter(original["branch"], original["counter_code"], completed=True)
    stock = frappe.db.sql("""select b.item_code, i.stock_uom from tabBin b join tabItem i on i.name=b.item_code
        where b.warehouse=%s and b.actual_qty>2 and i.has_batch_no=0 and i.has_serial_no=0
        and i.disabled=0 and i.is_sales_item=1 limit 1""", counter.warehouse, as_dict=True)
    assert stock, "Test requires an ordinary stock item with at least 3 units in the counter warehouse"
    item = stock[0]
    cash = next(p.mode_of_payment for p in frappe.get_doc("POS Profile", counter.pos_profile).payments
        if frappe.db.get_value("Mode of Payment", p.mode_of_payment, "type") == "Cash")
    base = dict(branch=counter.branch, counter_code=counter.counter_code, customer=counter.default_customer,
        cashier_employee=original.get("cashier_employee"), posting_date=nowdate(), business_date=nowdate(),
        update_stock=1, grand_total=10, net_total=10, vat_amount=0,
        items=[dict(item_code=item.item_code, uom=item.stock_uom, conversion_factor=1, qty=1,
            rate=10, amount=10, net_amount=10, vat_rate=0, vat_amount=0, rate_includes_vat=0)],
        payments=[dict(mode_of_payment=cash, amount=10)])
    results = []

    def post(suffix, **changes):
        data = frappe._dict({**copy.deepcopy(base), "external_pos_reference": f"cancel-proof-{token}-{suffix}",
            "pos_bill_no": f"CANCEL-PROOF-{token}", **changes})
        result = api.create_pos_invoice(data)
        assert result.get("accepted_transaction"), result
        tx = frappe.get_doc("POS Accepted Transaction", result["accepted_transaction"])
        assert tx.pos_invoice and tx.sales_invoice, (tx.status, tx.exception_reason)
        return data, tx

    def request(tx, suffix):
        return frappe._dict(branch=counter.branch, counter_code=counter.counter_code,
            pos_invoice_name=tx.pos_invoice, original_external_pos_reference=tx.external_pos_reference,
            operation_reference=f"cancel-proof-{token}-op-{suffix}", reason="Cancellation integration proof")

    def expect_failure(data, text):
        try:
            api.cancel_pos_invoice(data)
        except Exception as exc:
            assert text.lower() in str(exc).lower(), (text, str(exc))
        else:
            raise AssertionError("Cancellation unexpectedly succeeded")

    try:
        with patch.object(frappe, "enqueue"), patch.object(frappe, "publish_realtime"), \
                patch.object(frappe.db, "commit", side_effect=AssertionError("Unexpected internal commit")):
            before = flt(frappe.db.get_value("Bin", {"item_code": item.item_code, "warehouse": counter.warehouse}, "actual_qty"))
            data, tx = post("cash")
            assert flt(frappe.db.get_value("Bin", {"item_code": item.item_code, "warehouse": counter.warehouse}, "actual_qty")) == before - 1
            sale_payload = frappe.db.get_value("POS Invoice", tx.pos_invoice, "custom_pos_completed_payload")
            req = request(tx, "cash")
            req.pop("pos_invoice_name")
            req.pos_bill_no = data.pos_bill_no
            req.reason = ""
            # A failure after native cancellation must restore both invoices/stock.
            with patch("retail.pos_settlements.audit", side_effect=RuntimeError("Forced audit failure")):
                expect_failure(req, "Forced audit failure")
            assert frappe.db.get_value("POS Invoice", tx.pos_invoice, "docstatus") == 1
            assert frappe.db.get_value("Sales Invoice", tx.sales_invoice, "docstatus") == 1
            assert not find("POS Cancellation", req.operation_reference)
            result = api.cancel_pos_invoice(req)
            assert result["docstatus"] == 2 and result["sales_invoice"] == tx.sales_invoice, result
            for doctype, name in (("POS Invoice", tx.pos_invoice), ("Sales Invoice", tx.sales_invoice)):
                assert frappe.db.get_value(doctype, name, "docstatus") == 2
            for doctype in ("GL Entry", "Stock Ledger Entry"):
                assert not frappe.db.exists(doctype, {"voucher_type": "Sales Invoice", "voucher_no": tx.sales_invoice, "is_cancelled": 0})
            assert flt(frappe.db.get_value("Bin", {"item_code": item.item_code, "warehouse": counter.warehouse}, "actual_qty")) == before
            assert frappe.db.get_value("POS Invoice", tx.pos_invoice, "custom_pos_completed_payload") == sale_payload
            assert api.cancel_pos_invoice(req)["duplicate"]
            assert api.cancel_pos_invoice({**req, "operation_reference": req.operation_reference + "-again"})["already_cancelled"]
            expect_failure({**req, "reason": "Changed reason"}, "Reference conflict")
            assert api.create_pos_invoice(data)["duplicate"]
            assert api._existing_invoice(data.external_pos_reference).docstatus == 2
            tx.reload()
            settlements.resolve_transaction(tx)
            assert frappe.db.get_value(tx.doctype, tx.name, "status") == "Cancelled"
            results.append("Cash sale: POS/SI/merge cancellation, GL/SLE reversal, restored stock, immutable payload/reference, retries and atomic rollback")
            # Reusing the display bill number with a NEW permanent reference posts.
            _, replacement = post("replacement")
            assert replacement.pos_invoice != tx.pos_invoice
            results.append("Same pos_bill_no with a new external reference creates a new invoice")
            _, credit = post("credit", payments=[], credit_sale_amount=10)
            assert frappe.db.get_value("Sales Invoice", credit.sales_invoice, "outstanding_amount") == 10
            credit_request = request(credit, "credit")
            credit_request.pop("reason")
            api.cancel_pos_invoice(credit_request)
            assert frappe.db.get_value("POS Accepted Transaction", credit.name, "status") == "Cancelled"
            allocations = frappe.get_all("POS Settlement Allocation", filters={"transaction": credit.name},
                fields=["status", "settlement_type", "requested_amount", "applied_amount", "unresolved_amount"])
            assert allocations and all(row.status == "Cancelled" for row in allocations)
            assert settlements._summarize_allocations(allocations)["credit_sales"] == 0
            results.append("Empty reason on cash cancellation and omitted reason on credit cancellation both succeed; cancelled credit is excluded from summaries")
            # Native cancellation from Desk/generic API remains blocked.
            doc = frappe.get_doc("POS Invoice", replacement.pos_invoice)
            try:
                doc.cancel()
            except frappe.ValidationError as exc:
                assert "cannot be cancelled" in str(exc)
            else:
                raise AssertionError("Generic cancellation bypassed the endpoint")
            assert not frappe.flags.get("retail_pos_cancellation")
            results.append("Generic cancellation remains blocked; endpoint scope is restored")
            # A completed return may already be accepted before its native posting.
            pending = settlements.insert(dict(doctype="POS Accepted Transaction", sync_type="Return",
                external_pos_reference=f"cancel-proof-{token}-pending-return", company=counter.company,
                branch=counter.branch, counter=counter.name, business_date=nowdate(), customer=base["customer"],
                status="Pending Dependency", payload_json=json.dumps({
                    "original_external_pos_reference": replacement.external_pos_reference})))
            expect_failure(request(replacement, "pending-return"), "depends on this bill")
            assert frappe.db.get_value("POS Invoice", replacement.pos_invoice, "docstatus") == 1
            # Roll back the pending fixture only, then post a real native return.
            frappe.db.set_value(pending.doctype, pending.name, "status", "Cancelled")
            return_payload = {**copy.deepcopy(base), "external_pos_reference": f"cancel-proof-{token}-return",
                "original_external_pos_reference": replacement.external_pos_reference}
            returned = api.create_pos_return_invoice(return_payload)
            return_tx = frappe.get_doc("POS Accepted Transaction", returned["accepted_transaction"])
            assert return_tx.pos_invoice, (return_tx.status, return_tx.exception_reason)
            expect_failure(request(replacement, "submitted-return"), "submitted return")
            assert frappe.db.get_value("Sales Invoice", replacement.sales_invoice, "docstatus") == 1
            results.append("Accepted pending returns and submitted native returns both block sale cancellation without partial reversal")
            # Cancellation can arrive before the sale, without any ERP invoice ID.
            old_reference = f"cancel-proof-{token}-not-synced"
            early_request = frappe._dict(branch=counter.branch, counter_code=counter.counter_code,
                pos_bill_no=f"EARLY-{token}", original_external_pos_reference=old_reference,
                operation_reference=f"cancel-proof-{token}-early-cancel", reason="")
            count_before = frappe.db.count("POS Invoice")
            early = api.cancel_pos_invoice(early_request)
            assert early["cancellation_status"] == "Cancelled Before Sync" and early["pos_invoice_name"] is None
            assert frappe.db.count("POS Invoice") == count_before
            assert api.cancel_pos_invoice(early_request)["duplicate"]
            assert api.cancel_pos_invoice({**early_request, "operation_reference": early_request.operation_reference + "-again"})["already_cancelled"]
            late = frappe._dict({**copy.deepcopy(base), "external_pos_reference": old_reference,
                "pos_bill_no": early_request.pos_bill_no})
            late_result = api.create_pos_invoice(late)
            assert late_result["status"] == "Failed" and "cancelled" in late_result["error"], late_result
            assert not frappe.db.exists("POS Invoice", {"external_pos_reference": old_reference})
            assert not frappe.db.exists("POS Accepted Transaction", {"external_pos_reference": old_reference})
            _, next_sale = post("early-replacement", pos_bill_no=early_request.pos_bill_no)
            expect_failure({**early_request, "operation_reference": early_request.operation_reference + "-wrong",
                "pos_bill_no": "ANOTHER-BILL"}, "Reference conflict")
            assert frappe.db.get_value("POS Invoice", next_sale.pos_invoice, "docstatus") == 1
            results.append("Cancel-before-sale records a permanent block; late original is rejected, new reference with the same bill number posts, retries cannot cancel the replacement")
            # Accepted-but-unposted bills must also stop being recoverable.
            accepted_ref = f"cancel-proof-{token}-accepted-unposted"
            accepted = settlements.insert(dict(doctype="POS Accepted Transaction", sync_type="Sales Invoice",
                external_pos_reference=accepted_ref, company=counter.company, branch=counter.branch,
                counter=counter.name, customer=base["customer"], business_date=nowdate(),
                status="Reconciliation Exception", payload_json=json.dumps({**base,
                    "external_pos_reference": accepted_ref, "pos_bill_no": "UNPOSTED-" + token})))
            api.cancel_pos_invoice(dict(branch=counter.branch, counter_code=counter.counter_code,
                original_external_pos_reference=accepted_ref, pos_bill_no="UNPOSTED-" + token,
                operation_reference=f"cancel-proof-{token}-cancel-accepted"))
            assert frappe.db.get_value(accepted.doctype, accepted.name, "status") == "Cancelled"
            results.append("Accepted-but-unposted cancellation marks the original acceptance Cancelled so recovery cannot post it")
    finally:
        frappe.db.rollback()
    return results
