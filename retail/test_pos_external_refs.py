"""Offline POS regressions against real documents; all business data is rolled back."""
import copy
import io
import json
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import nowdate, nowtime

from retail.api import pos_sync
from retail.pos_external_refs import resolve
from retail.pos_operations import find


class TestOfflineReferences(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.flags.in_test = True
		# Simulate separate HTTP transactions inside this rollback-only fixture.
		# A failed request rolls back its own writes, retaining prior request data.
		original_run, original_rollback = pos_sync._run, frappe.db.rollback
		def request(*args, **kwargs):
			frappe.db.savepoint("offline_test_request")
			def rollback(*, save_point=None):
				return original_rollback(save_point=save_point or "offline_test_request")
			with patch.object(frappe.db, "rollback", side_effect=rollback):
				return original_run(*args, **kwargs)
		self.request_patch = patch.object(pos_sync, "_run", side_effect=request)
		self.request_patch.start()
		self.addCleanup(self.request_patch.stop)
		self.token = frappe.generate_hash(length=10)
		self.base = json.loads(frappe.db.get_value("POS Sync Log", "PSL-2644", "request_json"))
		original_counter = pos_sync._counter(self.base["branch"], self.base["counter_code"])
		self.branch = frappe.get_doc({"doctype": "Branch", "branch": "Offline Test " + self.token}).insert()
		self.employee = frappe.get_doc({"doctype": "Employee", "first_name": "Offline Test " + self.token,
			"company": original_counter.company, "gender": "Male", "date_of_birth": "1990-01-01",
			"date_of_joining": "2020-01-01", "status": "Active"}).insert()
		profile = frappe.copy_doc(frappe.get_doc("POS Profile", original_counter.pos_profile))
		profile.name = "Offline Profile " + self.token
		profile.set("applicable_for_users", [])
		profile.insert()
		self.counter = frappe.copy_doc(original_counter)
		self.counter.branch = self.branch.name
		self.counter.counter_code = "OF1"
		self.counter.terminal_id = "OFT1"
		self.counter.pos_profile = profile.name
		self.counter.integration_user = None
		self.counter.insert()
		self.opening = {"external_pos_reference": self.ref("OPEN"),
			"external_shift_reference": self.ref("SHIFT"), "external_session_reference": self.ref("CS"),
			"branch": self.branch.name, "counter_code": "OF1", "pos_terminal_id": "OFT1",
			"cashier_employee": self.employee.name, "business_date": nowdate(),
			"opening_balances": [{"mode_of_payment": "Cash", "opening_amount": 100}]}
		self.base.update(branch=self.branch.name, counter_code="OF1", pos_terminal_id="OFT1",
			cashier_employee=self.employee.name, posting_date=nowdate(), posting_time=nowtime(),
			external_shift_reference=self.ref("SHIFT"), external_session_reference=self.ref("CS"))
		for field in ("cashier_shift", "cashier_shift_id", "counter_session", "counter_session_id", "pos_shift_no", "original_pos_invoice"):
			self.base.pop(field, None)

	def tearDown(self):
		frappe.db.rollback()
		frappe.set_user("Administrator")

	def ref(self, kind):
		return f"OFFLINE-{self.token}-{kind}"

	def success(self, result):
		self.assertEqual(result.get("status", "Success"), "Success", result)
		return result

	def open(self):
		return self.success(pos_sync.open_cashier_shift(copy.deepcopy(self.opening)))

	def sale(self, kind="SALE", **changes):
		payload = {**copy.deepcopy(self.base), "external_pos_reference": self.ref(kind), **changes}
		return payload, self.success(pos_sync.create_pos_invoice(payload))

	def test_offline_sale_reconnect_mapping_and_replay(self):
		queued = {**copy.deepcopy(self.base), "external_pos_reference": self.ref("SALE")}
		before = copy.deepcopy(queued)
		opening = self.open()
		for field in ("external_shift_reference", "external_session_reference"):
			self.assertEqual(opening[field], self.opening[field])
		self.assertEqual(frappe.db.get_value("POS Cashier Shift", opening["cashier_shift"], "external_shift_reference"), self.ref("SHIFT"))
		self.assertEqual(frappe.db.get_value("POS Counter Session", opening["counter_session"], "external_session_reference"), self.ref("CS"))
		result = self.success(pos_sync.create_pos_invoice(queued))
		self.assertEqual(queued, before)
		invoice = frappe.get_doc("POS Invoice", result["invoice_name"])
		self.assertEqual(json.loads(invoice.custom_pos_completed_payload), before)
		self.assertEqual(invoice.pos_cashier_shift, opening["cashier_shift"])
		self.assertEqual(invoice.pos_counter_session, opening["counter_session"])
		self.assertEqual(invoice.pos_shift_no, opening["pos_opening_entry"])
		self.assertEqual(frappe.db.get_value("Sales Invoice", invoice.consolidated_invoice, "docstatus"), 1)
		self.assertTrue(pos_sync.create_pos_invoice(queued)["duplicate"])
		self.assertTrue(pos_sync.open_cashier_shift(self.opening)["duplicate"])
		self.assertEqual(frappe.db.count("POS Invoice", {"external_pos_reference": self.ref("SALE")}), 1)

	def test_missing_opening_is_dependency_not_audit_only(self):
		payload = {**self.base, "external_pos_reference": self.ref("EARLY")}
		result = pos_sync.create_pos_invoice(payload)
		self.assertEqual(result.get("error_code"), "BlockedDependency", result)
		self.assertFalse(frappe.db.exists("POS Invoice", {"external_pos_reference": payload["external_pos_reference"]}))
		self.assertFalse(find("POS Sale", payload["external_pos_reference"]))
		self.open()
		self.success(pos_sync.create_pos_invoice(payload))

	def test_changed_opening_payload_conflicts(self):
		self.open()
		changed = copy.deepcopy(self.opening)
		changed["opening_balances"][0]["opening_amount"] = 200
		result = pos_sync.open_cashier_shift(changed)
		self.assertEqual(result["status"], "Failed")
		self.assertIn("Reference conflict", result["error"])

	def test_mismatched_session_is_rejected_before_sale_posting(self):
		self.open()
		result = pos_sync.create_pos_invoice({**self.base, "external_pos_reference": self.ref("BAD"), "pos_terminal_id": "OTHER"})
		self.assertEqual(result["status"], "Failed")
		self.assertIn("another terminal", result["error"])

	def test_cash_deposit_credit_collection_return(self):
		self.open()
		identity = {k: self.base[k] for k in ("branch", "counter_code", "pos_terminal_id", "cashier_employee", "external_shift_reference", "external_session_reference", "posting_date")}
		cash = {**identity, "external_pos_reference": self.ref("CASHIN"), "movement_type": "Cash In", "amount": 10}
		movement = self.success(pos_sync.create_pos_cash_movement(cash))
		self.assertTrue(pos_sync.create_pos_cash_movement(cash)["duplicate"])
		self.assertTrue(movement["cash_movement"].startswith("PCM-"))
		deposit = {**identity, "external_pos_reference": self.ref("DEPOSIT"), "customer": self.base["customer"], "payment_mode": "Cash", "amount": 5}
		self.success(pos_sync.create_customer_deposit(deposit))
		self.assertTrue(pos_sync.create_customer_deposit(deposit)["duplicate"])
		credit_payload, credit = self.sale("CREDIT", payments=[])
		collection = {**identity, "external_pos_reference": self.ref("COLLECT"), "invoice_external_reference": self.ref("CREDIT"), "payment_mode": "Cash", "amount": 1}
		collected = self.success(pos_sync.pay_customer_invoice(collection))
		self.assertTrue(pos_sync.pay_customer_invoice(collection)["duplicate"])
		self.assertEqual(collected["invoice_name"], credit["invoice_name"])
		returned = {**credit_payload, "external_pos_reference": self.ref("RETURN"), "original_external_pos_reference": self.ref("CREDIT"),
			"posting_time": frappe.utils.add_to_date(frappe.utils.now_datetime(), seconds=2).strftime("%H:%M:%S")}
		before = copy.deepcopy(returned)
		result = self.success(pos_sync.create_pos_return_invoice(returned))
		self.assertEqual(returned, before)
		refund = frappe.get_doc("POS Invoice", result["return_invoice"])
		self.assertEqual(json.loads(refund.custom_pos_completed_payload), before)
		self.assertEqual(refund.return_against, credit["invoice_name"])
		self.assertTrue(pos_sync.create_pos_return_invoice(returned)["duplicate"])

	def test_one_collection_settles_ten_invoices_and_reverses(self):
		self.open()
		from retail.pos_credit import remaining_amount
		identity = {k: self.base[k] for k in ("branch", "counter_code", "pos_terminal_id",
			"cashier_employee", "external_shift_reference", "external_session_reference", "posting_date")}
		allocations, original_balances = [], {}
		for index in range(10):
			_, result = self.sale(f"CREDIT-{index}", payments=[], credit_note_redemptions=[])
			invoice = frappe.get_doc("POS Invoice", result["invoice_name"])
			original_balances[invoice.name] = remaining_amount(invoice)
			self.assertGreaterEqual(original_balances[invoice.name], 1)
			allocations.append(dict(invoice_external_reference=self.ref(f"CREDIT-{index}"),
				invoice_doctype="POS Invoice", allocated_amount=1))
		payload = {**identity, "external_pos_reference": self.ref("MULTI-COLLECT"),
			"customer": self.base["customer"], "payment_mode": "Cash", "amount": 10, "invoices": allocations}
		bad = copy.deepcopy(payload)
		bad["external_pos_reference"] = self.ref("MULTI-BAD")
		bad["invoices"][-1]["allocated_amount"] = 100000000
		self.assertEqual(pos_sync.pay_customer_invoice(bad)["status"], "Failed")
		self.assertFalse(frappe.db.exists("Payment Entry", {"external_pos_reference": bad["external_pos_reference"]}))
		result = self.success(pos_sync.pay_customer_invoice(payload))
		payment = frappe.get_doc("Payment Entry", result["payment_entry"])
		self.assertEqual(payment.docstatus, 1)
		self.assertEqual(len(payment.references), 10)
		self.assertEqual(payment.paid_amount, 10)
		self.assertEqual(payment.unallocated_amount, 0)
		self.assertEqual(sum(row.allocated_amount for row in payment.references), 10)
		for row in result["invoices"]:
			invoice = frappe.get_doc("POS Invoice", row["invoice_name"])
			self.assertEqual(invoice.outstanding_amount, original_balances[invoice.name] - 1)
			self.assertEqual(remaining_amount(invoice), row["invoice_outstanding_amount"])
		self.assertTrue(pos_sync.pay_customer_invoice(payload)["duplicate"])
		self.assertEqual(frappe.db.count("Payment Entry", {"external_pos_reference": payload["external_pos_reference"]}), 1)
		payment.cancel()
		for name, balance in original_balances.items():
			invoice = frappe.get_doc("POS Invoice", name)
			self.assertEqual(invoice.outstanding_amount, balance)
			self.assertEqual(remaining_amount(invoice), balance)

	def test_pause_transfer_close_day_and_lost_responses(self):
		opened = self.open()
		pause = {"external_pos_reference": self.ref("PAUSE"), "external_shift_reference": self.ref("SHIFT"),
			"external_session_reference": self.ref("CS"), "business_date": nowdate(), "release_counter": 1,
			"closing_balances": [{"mode_of_payment": "Cash", "closing_amount": 100}]}
		self.success(pos_sync.pause_cashier_shift(pause))
		second = frappe.copy_doc(self.counter)
		second.counter_code, second.terminal_id = "OF2", "OFT2"
		second.insert()
		resume = {**self.opening, "external_pos_reference": self.ref("RESUME"), "external_session_reference": self.ref("CS2"),
			"counter_code": "OF2", "pos_terminal_id": "OFT2"}
		resumed = self.success(pos_sync.resume_cashier_shift(resume))
		self.assertEqual(resumed["cashier_shift"], opened["cashier_shift"])
		self.assertNotEqual(resumed["counter_session"], opened["counter_session"])
		close = {**pause, "external_pos_reference": self.ref("CLOSE"), "external_session_reference": self.ref("CS2")}
		self.success(pos_sync.close_cashier_shift(close))
		day = {"branch": self.branch.name, "business_date": nowdate(), "external_pos_reference": self.ref("DAY")}
		closed = self.success(pos_sync.submit_branch_day_closing(day))
		self.assertEqual(closed["docstatus"], 1)
		self.assertTrue(closed["name"].startswith("PDC-"))
		for method, payload in [(pos_sync.open_cashier_shift,self.opening), (pos_sync.pause_cashier_shift,pause),
			(pos_sync.resume_cashier_shift,resume), (pos_sync.close_cashier_shift,close), (pos_sync.submit_branch_day_closing,day)]:
			self.assertTrue(method(payload)["duplicate"])
		status = pos_sync.get_sync_status({"external_references": [self.ref("DAY"), self.ref("OPEN")]})
		self.assertTrue(all(r["status"] == "Synced" for r in status["references"].values()), status)

	def closed_shift_for_reopen(self):
		opened = self.open()
		self.success(pos_sync.close_cashier_shift({**self.opening, "external_pos_reference": self.ref("CLOSE")}))
		payload = {"external_pos_reference": self.ref("REOPEN"), "external_shift_reference": self.ref("SHIFT"),
			"branch": self.branch.name, "business_date": nowdate(), "reopen_reason": "Correct cash count"}
		return opened, payload

	def test_reopen_external_reference_replay_conflict_and_recovery(self):
		opened, payload = self.closed_shift_for_reopen()
		before = copy.deepcopy(payload)
		result = self.success(pos_sync.reopen_cashier_shift(payload))
		self.assertEqual(payload, before)
		self.assertEqual(result["cashier_shift"], opened["cashier_shift"])
		self.assertEqual(result["external_shift_reference"], self.ref("SHIFT"))
		self.assertEqual(result["shift_status"], "Paused")
		self.assertTrue(pos_sync.reopen_cashier_shift(payload)["duplicate"])
		changed = pos_sync.reopen_cashier_shift({**payload, "reopen_reason": "Different reason"})
		self.assertIn("Reference conflict", changed["error"])
		self.success(pos_sync.close_cashier_shift({**self.opening, "external_pos_reference": self.ref("CLOSE2")}))
		self.assertTrue(pos_sync.reopen_cashier_shift(payload)["duplicate"])
		shift = frappe.get_doc("POS Cashier Shift", opened["cashier_shift"])
		self.assertEqual(shift.status, "Closed")
		self.assertEqual(shift.reopen_count, 1)
		status = pos_sync.get_sync_status({"external_references": [self.ref("REOPEN")]})
		self.assertEqual(status["references"][self.ref("REOPEN")]["status"], "Synced")
		self.success(pos_sync.reopen_cashier_shift({**payload, "external_pos_reference": self.ref("REOPEN2")}))
		self.assertEqual(frappe.db.get_value("POS Cashier Shift", shift.name, "reopen_count"), 2)

	def test_reopen_checks_identity_authorization_and_closed_day(self):
		opened, payload = self.closed_shift_for_reopen()
		other_branch = frappe.get_doc({"doctype": "Branch", "branch": "Other " + self.token}).insert()
		for extra, message in [({"cashier_shift": "PSH-wrong"}, "conflicts"),
			({"branch": other_branch.name}, "another branch"),
			({"business_date": "2000-01-01"}, "Business date"),
			({"external_shift_reference": self.ref("MISSING")}, "Shift opening has not synced")]:
			result = pos_sync.reopen_cashier_shift({**payload, **extra})
			self.assertEqual(result["status"], "Failed", result)
			self.assertIn(message, result["error"])
		self.success(pos_sync.submit_branch_day_closing({"branch": self.branch.name,
			"business_date": nowdate(), "external_pos_reference": self.ref("DAY")}))
		self.assertIn("Cancel day closing", pos_sync.reopen_cashier_shift(payload)["error"])
		self.assertFalse(find("Shift Reopen", self.ref("REOPEN")))
		from retail.pos_day_corrections import reopen_day_closing
		day = frappe.db.get_value("POS Branch Day Closing", {"branch": self.branch.name, "business_date": nowdate(), "docstatus": 1}, "name")
		self.success(reopen_day_closing({"day_closing": day,
			"operation_reference": self.ref("DAY-REOPEN"), "reason": "Correct count"}))
		self.success(pos_sync.reopen_cashier_shift(payload))
		with patch.object(pos_sync, "_counter", side_effect=frappe.PermissionError("Counter access denied")):
			result = pos_sync.reopen_cashier_shift(payload)
		self.assertEqual(result["status"], "Failed")
		self.assertNotIn("cashier_shift", result)

	def test_reopen_legacy_erp_id_and_required_operation_reference(self):
		opened, payload = self.closed_shift_for_reopen()
		with self.assertRaises(frappe.ValidationError):
			pos_sync.reopen_cashier_shift({k:v for k,v in payload.items() if k != "external_pos_reference"})
		legacy = {"cashier_shift": opened["cashier_shift"], "reopen_reason": "Legacy correction"}
		self.success(pos_sync.reopen_cashier_shift(legacy))
		self.assertEqual(frappe.db.get_value("POS Cashier Shift", opened["cashier_shift"], "status"), "Paused")

	def test_reopen_legacy_success_receipt_is_not_applied_again(self):
		opened, payload = self.closed_shift_for_reopen()
		legacy = {"cashier_shift": opened["cashier_shift"], "reopen_reason": "Old correction",
			"external_pos_reference": self.ref("OLDREOPEN")}
		response = {"status": "Success", "cashier_shift": opened["cashier_shift"], "shift_status": "Paused"}
		pos_sync._sync_log("Shift Reopen", legacy["external_pos_reference"], legacy,
			response=response, status="Success", docname=opened["cashier_shift"])
		self.assertTrue(pos_sync.reopen_cashier_shift(legacy)["duplicate"])
		self.assertEqual(frappe.db.get_value("POS Cashier Shift", opened["cashier_shift"], "status"), "Closed")

	def test_unreleased_session_resume_keeps_identity(self):
		opened = self.open()
		self.success(pos_sync.pause_cashier_shift({**self.opening, "external_pos_reference": self.ref("PAUSE"), "release_counter": 0}))
		resumed = self.success(pos_sync.resume_cashier_shift({**self.opening, "external_pos_reference": self.ref("RESUME")}))
		self.assertEqual(resumed["counter_session"], opened["counter_session"])
		self.assertEqual(resumed["action"], "Continued")

	def test_identity_is_immutable(self):
		opened = self.open()
		for dt, name, field in [("POS Cashier Shift", opened["cashier_shift"], "external_shift_reference"),
			("POS Counter Session", opened["counter_session"], "external_session_reference")]:
			doc = frappe.get_doc(dt,name)
			doc.set(field, self.ref("CHANGED"))
			with self.assertRaises(frappe.ValidationError):
				doc.save()

	def test_legacy_erp_ids_still_work(self):
		legacy = {k:v for k,v in self.opening.items() if k not in ("external_shift_reference", "external_session_reference")}
		opened = self.success(pos_sync.open_cashier_shift(legacy))
		payload = {k:v for k,v in self.base.items() if k not in ("external_shift_reference", "external_session_reference")}
		payload.update(external_pos_reference=self.ref("LEGACY"), cashier_shift=opened["cashier_shift"],
			counter_session=opened["counter_session"], pos_shift_no=opened["pos_opening_entry"])
		self.success(pos_sync.create_pos_invoice(payload))

	def test_failure_rolls_back_receipt_and_retries_same_payload(self):
		self.open()
		payload = {**self.base, "external_pos_reference": self.ref("FAILED")}
		with patch.object(pos_sync, "_append_invoice_items", side_effect=RuntimeError("Simulated failure")):
			self.assertEqual(pos_sync.create_pos_invoice(payload)["status"], "Failed")
		self.assertFalse(find("POS Sale", self.ref("FAILED")))
		self.success(pos_sync.create_pos_invoice(payload))
		self.assertEqual(frappe.db.count("POS Invoice", {"external_pos_reference": self.ref("FAILED")}), 1)

	def test_cash_and_payment_conflicts_do_not_repost(self):
		self.open()
		identity = {k: self.base[k] for k in ("branch", "counter_code", "pos_terminal_id", "cashier_employee", "external_shift_reference", "external_session_reference")}
		for method, extra in [(pos_sync.create_pos_cash_movement, {"movement_type": "Cash In"}),
			(pos_sync.create_customer_deposit, {"customer": self.base["customer"], "payment_mode": "Cash"})]:
			payload = {**identity, **extra, "external_pos_reference": self.ref(method.__name__), "amount": 5}
			self.success(method(payload))
			failed = method({**payload, "amount": 6})
			self.assertEqual(failed["status"], "Failed")
			self.assertIn("Reference conflict", failed["error"])
			self.assertTrue(method(payload)["duplicate"])

	def test_day_close_changed_payload_conflicts_and_status_keeps_mapping(self):
		self.open()
		self.success(pos_sync.close_cashier_shift({**self.opening, "external_pos_reference": self.ref("CLOSE")}))
		payload = {"branch": self.branch.name, "business_date": nowdate(), "external_pos_reference": self.ref("DAY")}
		closed = self.success(pos_sync.submit_branch_day_closing(payload))
		failed = pos_sync.submit_branch_day_closing({**payload, "business_date": "2026-01-01"})
		self.assertEqual(failed["status"], "Failed")
		self.assertIn("Reference conflict", failed["error"])
		status = pos_sync.get_sync_status({"external_references": [self.ref("DAY")]})["references"][self.ref("DAY")]
		self.assertEqual(status["status"], "Synced")
		self.assertEqual(status["response"]["name"], closed["name"])

	def test_replay_requires_counter_authorization(self):
		self.open()
		with patch.object(pos_sync, "_counter", side_effect=frappe.PermissionError("Counter access denied")):
			result = pos_sync.open_cashier_shift(self.opening)
		self.assertEqual(result["status"], "Failed")
		self.assertNotIn("cashier_shift", result)

	def test_historical_completed_sale_retains_links(self):
		opened = self.open()
		self.success(pos_sync.close_cashier_shift({**self.opening, "external_pos_reference": self.ref("CLOSE")}))
		_, result = self.sale("LATE")
		invoice = frappe.get_doc("POS Invoice", result["invoice_name"])
		self.assertEqual(invoice.pos_cashier_shift, opened["cashier_shift"])
		self.assertEqual(invoice.pos_counter_session, opened["counter_session"])
		self.assertEqual(invoice.pos_shift_no, opened["pos_opening_entry"])

	def test_old_business_date_is_preserved_on_reconnect(self):
		self.opening["business_date"] = "2026-09-01"
		opened = self.open()
		self.assertEqual(str(frappe.db.get_value("POS Cashier Shift", opened["cashier_shift"], "opening_time"))[:10], "2026-09-01")
		self.assertEqual(str(frappe.db.get_value("POS Opening Entry", opened["pos_opening_entry"], "posting_date")), "2026-09-01")

	def test_missing_resumed_session_blocks_invoice(self):
		self.open()
		payload = {**self.base, "external_pos_reference": self.ref("MISSINGSESSION"), "external_session_reference": self.ref("CS-NOT-SYNCED")}
		result = pos_sync.create_pos_invoice(payload)
		self.assertEqual(result.get("error_code"), "BlockedDependency", result)
		self.assertFalse(frappe.db.exists("POS Invoice", {"external_pos_reference": payload["external_pos_reference"]}))

	def test_return_waits_for_original_sale_then_retries_unchanged(self):
		self.open()
		payload = {**self.base, "external_pos_reference": self.ref("RETURNFIRST"), "original_external_pos_reference": self.ref("SALELATER"),
			"posting_time": frappe.utils.add_to_date(frappe.utils.now_datetime(), seconds=5).strftime("%H:%M:%S")}
		result = pos_sync.create_pos_return_invoice(payload)
		self.assertEqual(result.get("error_code"), "BlockedDependency", result)
		self.sale("SALELATER")
		self.success(pos_sync.create_pos_return_invoice(payload))

	def test_external_id_uniqueness_is_enforced_by_database(self):
		opened = self.open()
		for dt, name, field in [("POS Cashier Shift", opened["cashier_shift"], "external_shift_reference"),
			("POS Counter Session", opened["counter_session"], "external_session_reference")]:
			original = frappe.get_doc(dt,name)
			duplicate = frappe.copy_doc(original)
			duplicate.set(field, original.get(field))
			duplicate.status = "Closed"
			frappe.db.savepoint("identity_unique_test")
			with self.assertRaises(frappe.UniqueValidationError):
				duplicate.insert()
			frappe.db.rollback(save_point="identity_unique_test")


def run_integration():
	if frappe.local.site != "retail-test.localhost":
		raise RuntimeError("These rollback-only fixtures are restricted to retail-test.localhost")
	stream = io.StringIO()
	result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TestOfflineReferences))
	print(stream.getvalue())
	if not result.wasSuccessful():
		raise AssertionError(f"{len(result.failures)} failures, {len(result.errors)} errors")
	return {"passed": result.testsRun, "business_data": "rolled back"}
