"""Real GL/credit/source-balance checks, always rolled back on the development site."""
import copy
import json
from unittest.mock import patch

import frappe
from frappe.utils import add_days, flt, nowdate


def run_integration():
    if frappe.local.site != "retail-test.localhost":
        raise RuntimeError("Use retail-test.localhost only")
    from retail.api import pos_sync as api
    from retail import pos_payment_modifications as service
    from retail import pos_day_corrections as days
    from retail.retail_app.doctype.pos_branch_day_closing.pos_branch_day_closing import make_day_closing
    frappe.set_user("Administrator")
    frappe.flags.in_test = True
    results = []
    try:
        with patch.object(frappe, "enqueue"), patch.object(frappe, "publish_realtime"), patch.object(frappe.db, "commit"):
            token = frappe.generate_hash(length=10)
            # Copy only configuration; keep all test sales in an isolated branch.
            original = frappe.get_doc("POS Branch Counter", frappe.db.get_value("POS Branch Counter", {"is_active": 1}, "name"))
            company = frappe.get_doc("Company", original.company)
            branch = frappe.get_doc(dict(doctype="Branch", branch="Payment Revision " + token)).insert()
            profile = frappe.copy_doc(frappe.get_doc("POS Profile", original.pos_profile))
            profile.name = "Payment Revision " + token
            cash = frappe.db.get_value("Mode of Payment", {"type": "Cash", "enabled": 1}, "name")
            card = frappe.db.get_value("Mode of Payment", {"type": "Bank", "enabled": 1}, "name")
            assert cash and card, "Configure Cash and Bank modes on the test site"
            for mode in (cash, card):
                if mode not in {r.mode_of_payment for r in profile.payments}:
                    profile.append("payments", {"mode_of_payment": mode})
            profile.insert()
            counter = frappe.copy_doc(original)
            counter.branch = branch.name
            counter.counter_code = "REV" + token
            counter.counter_name = counter.counter_code
            counter.pos_profile = profile.name
            counter.integration_user = None
            counter.insert()
            customer = frappe.get_doc(dict(doctype="Customer", customer_name="Payment Revision " + token,
                customer_type="Individual", customer_group=frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
                territory=frappe.db.get_value("Territory", {"is_group": 0}, "name"),
                credit_limits=[dict(company=company.name, credit_limit=999999)])).insert()
            item = frappe.get_doc("Item", frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1,
                "has_serial_no": 0, "has_batch_no": 0, "is_stock_item": 1}, "name"))
            employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
            shift = frappe.get_doc(dict(doctype="POS Cashier Shift", branch=branch.name,
                cashier_employee=employee, opening_time=nowdate()+" 00:00:00", status="Open",
                opening_amount=0, closing_amount=0)).insert()
            opening = frappe.get_doc(dict(doctype="POS Opening Entry", company=company.name,
                pos_profile=profile.name, user="Administrator", period_start_date=nowdate()+" 00:00:00",
                balance_details=[dict(mode_of_payment=cash, opening_amount=0)])).insert()
            opening.submit()
            session = frappe.get_doc(dict(doctype="POS Counter Session", branch=branch.name,
                counter=counter.name, counter_code=counter.counter_code, cashier_employee=employee,
                cashier_shift=shift.name, started_at=nowdate()+" 00:00:00", status="Active",
                pos_opening_entry=opening.name)).insert()
            data = frappe._dict(external_pos_reference="rev-"+token, branch=branch.name,
                counter_code=counter.counter_code, cashier_employee=employee, cashier_shift=shift.name,
                counter_session=session.name, pos_shift_no=opening.name, customer=customer.name,
                posting_date=nowdate(), business_date=nowdate(), posting_time="10:30:00", update_stock=1,
                net_total=100, vat_amount=0, grand_total=100, discount_amount=0,
                items=[dict(item_code=item.name, qty=1, uom=item.stock_uom, rate=100, amount=100,
                    net_amount=100, rate_includes_vat=0, vat_rate=0, vat_amount=0, discount_amount=0)],
                payments=[dict(mode_of_payment=cash, amount=100)])
            response = api.create_pos_invoice(data)
            assert response.get("accepted"), response
            tx = frappe.get_doc("POS Accepted Transaction", response["accepted_transaction"])
            assert tx.sales_invoice, (tx.status, tx.exception_reason)
            pos = frappe.get_doc("POS Invoice", tx.pos_invoice)
            si = frappe.get_doc("Sales Invoice", tx.sales_invoice)
            original_payload = pos.custom_pos_completed_payload
            original_acceptance = tx.payload_json
            stock_before = frappe.get_all("Stock Ledger Entry", filters={"voucher_no": si.name},
                fields=["name", "actual_qty", "stock_value_difference"], order_by="name")
            assert stock_before, "Fixture must exercise a real stock movement"
            closing = frappe.get_doc(days.DAY, make_day_closing(branch.name, nowdate()).name)

            def correction(number, **changes):
                return frappe._dict({**copy.deepcopy(data), "modified": True,
                    "operation_reference": "rev-"+token+"-mod-"+str(number), "expected_payment_revision": number-1,
                    "payment_revision": number, "reason": "Rollback-only integration check", **changes})

            def success(request, outstanding=0):
                result = api.create_pos_invoice(request)
                assert result.get("status") == "Success", result
                assert result["modified"]
                if request.get("payment_revision") is not None:
                    assert result["payment_revision"] == request.payment_revision
                retry = api.create_pos_invoice(request)
                assert retry.get("duplicate") is True, retry
                pos.reload(); si.reload(); tx.reload()
                assert abs(si.outstanding_amount-outstanding) < .001, (si.outstanding_amount, outstanding)
                assert abs(pos.outstanding_amount-outstanding) < .001
                assert pos.custom_pos_modified and pos.custom_payment_revision == result["payment_revision"]
                assert pos.custom_pos_completed_payload == original_payload
                assert tx.payload_json == original_acceptance
                assert pos.grand_total == si.grand_total == 100
                assert frappe.get_all("Stock Ledger Entry", filters={"voucher_no": si.name},
                    fields=["name", "actual_qty", "stock_value_difference"], order_by="name") == stock_before
                gl = frappe.get_all("GL Entry", filters={"voucher_no": si.name, "is_cancelled": 0}, fields=["debit", "credit"])
                assert gl and abs(sum(r.debit-r.credit for r in gl)) < .001
                return result

            def rejected(request, text=None):
                previous = pos.custom_payment_revision
                result = api.create_pos_invoice(request)
                assert result.get("status") == "Failed", result
                if text:
                    assert text.lower() in result["error"].lower(), result
                pos.reload(); si.reload()
                assert pos.custom_payment_revision == previous
                return result

            first = correction(1, payments=[dict(mode_of_payment=card, amount=100, reference_no="CARD-TEST")])
            success(first)
            assert api.create_pos_invoice(data).get("duplicate") is True
            assert si.payments[0].reference_no == "CARD-TEST"
            assert api._refresh_cashier_shift_cash_totals(shift.name).expected_cash == 0
            minimal = copy.deepcopy(first)
            minimal.operation_reference += "-minimal"
            for field in ("expected_payment_revision", "payment_revision", "reason", "modified_at", "modification_type"):
                minimal.pop(field, None)
            # No new metadata except the flag and operation reference is required.
            # Keep the existing sequence's first revision intact for later checks.
            frappe.db.savepoint("minimal_correction_test")
            minimal_result = success(minimal)
            assert minimal_result["payment_revision"] == 2
            assert minimal_result["reason"] == "POS payment correction"
            frappe.db.rollback(save_point="minimal_correction_test")
            pos.reload(); si.reload(); tx.reload()
            results.append("Only modified and operation_reference required; server revision/reason defaults and exact retry verified")
            results.append("Cash to card; omitted modification_type; exact correction and original-sale retries; real GL and stock unchanged")
            conflict = copy.deepcopy(first); conflict.payments[0]["amount"] = 99
            rejected(conflict, "Reference conflict")
            stale = correction(2); stale.expected_payment_revision = 0; stale.payment_revision = 1
            rejected(stale, "changed")
            changed = correction(2); changed["items"][0]["qty"] = 2
            rejected(changed, "cannot change items")
            rejected(correction(2, modification_type="ItemsCorrection"), "Only PaymentCorrection")
            rejected(correction(2, payments=[dict(mode_of_payment=cash, amount=99)], credit_sale_amount=0), "match")
            results.append("Conflicting retries, stale revisions, commercial edits, unknown modification type and unbalanced payments rejected")
            success(correction(2, modification_type="PaymentCorrection", payments=[dict(mode_of_payment=cash, amount=40), dict(mode_of_payment=card, amount=60)]))
            closing.reload()
            assert json.loads(closing.payment_totals)[cash] == 40
            assert api._refresh_cashier_shift_cash_totals(shift.name).expected_cash == 40
            success(correction(3, payments=[], credit_sale_amount=100), outstanding=100)
            assert settlements_total(tx.name, "Credit Sale") == 100
            success(correction(4, payments=[dict(mode_of_payment=card, amount=80)], credit_sale_amount=20), outstanding=20)
            assert settlements_total(tx.name, "Credit Sale") == 20
            success(correction(5, payments=[dict(mode_of_payment=cash, amount=100)], credit_sale_amount=0))
            assert settlements_total(tx.name, "Credit Sale") == 0
            results.append("Split payments, paid-to-credit, partial credit and credit-to-paid refresh receivables, allocations and closing totals")
            # Inject failure after payment rows changed; every row and ledger effect must roll back.
            before_rows = service.native_signature(si)
            with patch("retail.pos_settlement_corrections.repost", side_effect=RuntimeError("injected repost failure")):
                rejected(correction(6, payments=[dict(mode_of_payment=card, amount=100)]), "injected")
            assert service.native_signature(si) == before_rows
            results.append("Failure after writing payment rows rolls back revision, payment rows and accounting")
            voucher = frappe.get_doc(dict(doctype="Gift Voucher Ledger", voucher_code="PGV-"+frappe.generate_hash(length=32).upper(),
                company=company.name, currency=company.default_currency, customer=customer.name,
                voucher_amount=100, balance_amount=100, status="Unused", issued_date=nowdate(), expiry_date=add_days(nowdate(), 30))).insert()
            success(correction(6, payments=[dict(mode_of_payment=card, amount=80), dict(mode_of_payment="Promotion Voucher", amount=20, reference_no=voucher.name)]))
            assert frappe.db.get_value("Gift Voucher Ledger", voucher.name, "balance_amount") == 80
            success(correction(7, payments=[dict(mode_of_payment=cash, amount=100)]))
            assert frappe.db.get_value("Gift Voucher Ledger", voucher.name, "balance_amount") == 100
            results.append("Promotion voucher added, debited exactly once on retry, then restored on the next revision")
            from retail import loyalty, voucher_cards
            program = frappe.get_doc(dict(doctype="Loyalty Program", loyalty_program_name="Revision "+token,
                loyalty_program_type="Single Tier Program", from_date=nowdate(), auto_opt_in=1,
                conversion_factor=1, expiry_duration=365, company=company.name,
                expense_account=company.default_expense_account, cost_center=company.cost_center,
                collection_rules=[dict(tier_name="Base", min_spent=0, collection_factor=1)])).insert()
            frappe.db.set_value("Customer", customer.name, "loyalty_program", program.name)
            frappe.clear_document_cache("Customer", customer.name)
            frappe.get_doc(dict(doctype="Loyalty Point Entry", company=company.name, customer=customer.name,
                loyalty_program=program.name, loyalty_program_tier="Base", loyalty_points=500,
                purchase_amount=500, posting_date=nowdate(), expiry_date=add_days(nowdate(), 365),
                invoice_type="Sales Invoice", invoice=si.name)).insert()
            def available():
                return sum(value for _, value in loyalty.available_buckets(
                    loyalty.ledger_entries(customer.name, program.name, company.name), nowdate()))
            success(correction(8, payments=[dict(mode_of_payment=card, amount=80),
                dict(mode_of_payment="Loyalty", amount=20, points=20, reference_no=program.name)]))
            assert available() == 480, available()
            # The original post-submit hook must not debit a corrected receipt again.
            from retail.pos_offline_promotions import apply as apply_promotions
            apply_promotions(pos)
            assert available() == 480
            success(correction(9, payments=[dict(mode_of_payment=cash, amount=100)]))
            assert available() == 500, available()
            success(correction(10, payments=[dict(mode_of_payment=card, amount=70)],
                loyalty_redemption=dict(loyalty_program=program.name, points=30, amount=30)))
            assert available() == 540, available()  # 500 - 30 redeemed + 70 earned.
            success(correction(11, payments=[dict(mode_of_payment=cash, amount=100)]))
            assert available() == 600, available()  # redemption restored; earning recalculated to 100.
            results.append("Payment-row and legacy loyalty redemption, retry protection, append-only restoration and recalculated earnings")
            batch = frappe.get_doc(dict(doctype="Voucher Card Batch", title="Revision "+token,
                company=company.name, currency=company.default_currency, voucher_amount=100, card_count=1,
                valid_from=nowdate(), expiry_date=add_days(nowdate(), 30), all_products=1,
                activate_all_cards=1, print_from=1, print_to=1)).insert()
            batch.db_set("generation_status", "Queued")
            voucher_cards.generate_worker(batch.name)
            card_code = frappe.db.get_value("Gift Voucher Ledger", {"voucher_card_batch": batch.name}, "name")
            success(correction(12, payments=[dict(mode_of_payment=card, amount=80),
                dict(mode_of_payment="Voucher Card", amount=20, reference_no=card_code)]))
            assert frappe.db.get_value("Gift Voucher Ledger", card_code, "balance_amount") == 80
            success(correction(13, payments=[dict(mode_of_payment=cash, amount=100)]))
            assert frappe.db.get_value("Gift Voucher Ledger", card_code, "balance_amount") == 100
            results.append("Voucher card debit and reversal retain source movement records")
            # Credit-note allocations use their native JE and are reversed before replacement.
            returned = copy.deepcopy(data)
            returned.update(external_pos_reference="rev-"+token+"-return", payments=[],
                return_settlement_type="Reusable Customer Credit")
            ret = api.create_pos_return_invoice(returned)
            assert ret.get("accepted"), ret
            credit_tx = frappe.get_doc("POS Accepted Transaction", ret["accepted_transaction"])
            assert credit_tx.sales_invoice, (credit_tx.status, credit_tx.exception_reason)
            success(correction(14, payments=[dict(mode_of_payment=card, amount=80)],
                credit_note_redemptions=[dict(credit_note_external_reference=returned.external_pos_reference, amount=20)]))
            assert frappe.db.get_value("Sales Invoice", credit_tx.sales_invoice, "outstanding_amount") == -80
            success(correction(15, payments=[dict(mode_of_payment=cash, amount=100)]))
            assert frappe.db.get_value("Sales Invoice", credit_tx.sales_invoice, "outstanding_amount") == -100
            assert settlements_total(tx.name, "Credit Note Redeemed") == 0
            status = api.get_sync_status(external_references=[data.external_pos_reference])["references"][data.external_pos_reference]
            assert status["pos_invoice"]["payment_revision"] == 15
            assert status["pos_invoice"]["modified"] is True
            results.append("Credit note allocation and native JE reversal restore source balance; sync status exposes current revision")
            # No correction may bypass the ordinary counter authorization, even on retry.
            from retail import pos_external_refs
            with patch.object(pos_external_refs, "authorize", side_effect=frappe.PermissionError("counter authorization denied")):
                rejected(first, "authorization denied")
            cleared = si.payments[0].name
            frappe.db.set_value("Sales Invoice Payment", cleared, "clearance_date", nowdate())
            rejected(correction(16, payments=[dict(mode_of_payment=card, amount=100)]), "bank cleared")
            frappe.db.set_value("Sales Invoice Payment", cleared, "clearance_date", None)
            missing = correction(16, payments=[dict(mode_of_payment=card, amount=80),
                dict(mode_of_payment="Promotion Voucher", amount=20, reference_no="MISSING-"+token)])
            rejected(missing)
            assert service.native_signature(si) == [(cash, counter.cash_account, 100)]
            # Exercise the credit endpoint and deprecated sale alias with the additive flag.
            last = correction(16, payments=[dict(mode_of_payment=card, amount=100)])
            alias_result = api.create_credit_pos_invoice(last)
            assert alias_result.get("status") == "Success", alias_result
            assert api.create_pos_sales_invoice(last).get("duplicate") is True
            pos.reload(); si.reload()
            results.append("Correction retries reauthorize; bank clearing and missing sources reject atomically; credit endpoint and sale alias share the revision")
            # Closed days require the existing manager reopen workflow.
            frappe.db.set_value(days.DAY, closing.name, "docstatus", 1)
            failed = rejected(correction(17, payments=[dict(mode_of_payment=cash, amount=100)]))
            assert failed.get("error_code") == "DayClosed", failed
            frappe.db.set_value(days.DAY, closing.name, "docstatus", 0)
            results.append("Closed-day correction rejected with DayClosed")
            assert frappe.db.count("POS Invoice", {"external_pos_reference": data.external_pos_reference}) == 1
    finally:
        frappe.db.rollback()
    return results


def settlements_total(transaction, kind):
    return sum(flt(r.requested_amount) for r in frappe.get_all("POS Settlement Allocation",
        filters={"transaction": transaction, "settlement_type": kind}, fields=["requested_amount"]))


def run_unit_checks():
    """Frappe number formatting requires initialized site context for these tests."""
    import unittest
    from retail.test_pos_completed_sale import TestCompletedValidation
    from retail.tests.test_pos_mixed_payments import TestMixedPayments
    from retail.test_pos_day_correction_permissions import TestDayCorrectionPermissions
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(case) for case in (
        TestCompletedValidation, TestMixedPayments, TestDayCorrectionPermissions))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise AssertionError("Focused POS compatibility checks failed")
    return {"passed": result.testsRun}
