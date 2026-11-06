"""Rollback-only integration checks for expiry stock arithmetic and permissions."""

import json
from datetime import datetime
from unittest import TestCase
from uuid import uuid4

import frappe
from frappe.utils import add_days, getdate, today

from retail.patches.items_expired_card import add_card
from retail.retail_app.report.expired_items import expired_items as report


class TestExpiredItems(TestCase):
	def setUp(self):
		self.old_user = frappe.session.user
		frappe.set_user("Administrator")
		self.savepoint = "expiry_" + uuid4().hex
		frappe.db.savepoint(self.savepoint)
		self.addCleanup(self.cleanup)
		self.company = report.prepare_filters().company
		if not self.company:
			self.skipTest("A company is required for stock report integration checks")
		self.temp_users = []
		self.day = getdate(today())
		self.expiry = add_days(self.day, -2)
		self.received = add_days(self.day, -20)
		self.sold = add_days(self.day, -4)
		self.item = self.insert("Item", item_name="Expiry integration item", stock_uom="Nos", is_stock_item=1)
		self.w1 = self.insert("Warehouse", company=self.company, lft=10000001, rgt=10000002, is_group=0)
		self.w2 = self.insert("Warehouse", company=self.company, lft=10000003, rgt=10000004, is_group=0)
		self.batch = self.make_batch()

	def cleanup(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=self.savepoint)
		for user in getattr(self, "temp_users", []):
			frappe.clear_cache(user=user)
		frappe.set_user(self.old_user)

	def insert(self, doctype, **values):
		values.setdefault("name", "expiry-test-" + uuid4().hex)
		values.setdefault("creation", datetime.now())
		values.setdefault("owner", "Administrator")
		columns = ", ".join(f"`{key}`" for key in values)
		frappe.db.sql(f"insert into `tab{doctype}` ({columns}) values ({', '.join(['%s'] * len(values))})", tuple(values.values()))
		return values["name"]

	def make_batch(self, **values):
		return self.insert("Batch", **dict(item=self.item, expiry_date=self.expiry, **values))

	def movement(self, qty, value, voucher_type="Purchase Receipt", *, batch=None, warehouse=None,
		date=None, legacy=False, cancelled=False, supplier=None, purpose=None, both_fields=False):
		batch = batch or self.batch
		warehouse = warehouse or self.w1
		date = getdate(date or self.received)
		voucher = "expiry-voucher-" + uuid4().hex
		if supplier:
			self.insert(voucher_type, name=voucher, supplier=supplier, docstatus=1, company=self.company)
		if purpose:
			self.insert("Stock Entry", name=voucher, purpose=purpose, stock_entry_type=purpose,
				docstatus=1, company=self.company)
		bundle = None
		if not legacy:
			bundle = self.insert("Serial and Batch Bundle", item_code=self.item, warehouse=warehouse,
				company=self.company, has_batch_no=1, docstatus=1)
			self.insert("Serial and Batch Entry", parent=bundle, parenttype="Serial and Batch Bundle",
				parentfield="entries", batch_no=batch, qty=qty, stock_value_difference=value, warehouse=warehouse)
		return self.insert("Stock Ledger Entry", company=self.company, item_code=self.item, warehouse=warehouse,
			posting_date=date, posting_datetime=datetime.combine(date, datetime.min.time()), docstatus=1,
			is_cancelled=int(cancelled), voucher_type=voucher_type, voucher_no=voucher,
			actual_qty=qty, stock_value_difference=value, serial_and_batch_bundle=bundle,
			batch_no=batch if legacy or both_fields else None)

	def rows(self, **filters):
		return report.execute(dict(company=self.company, item_code=self.item, as_of_date=str(self.day), **filters))[1]

	def test_bundle_sales_returns_transfers_and_expiry_issues(self):
		baseline = report.get_expired_items_count()["value"]
		self.movement(100, 1000, supplier="expiry-supplier-A", both_fields=True)
		self.movement(-20, -200, "Sales Invoice", date=self.sold)
		self.movement(-5, -50, "Delivery Note", date=self.sold)
		self.movement(2, 20, "Sales Invoice", date=self.day)
		self.movement(-30, -300, "Stock Entry", date=self.day, purpose="Material Transfer")
		self.movement(30, 300, "Stock Entry", warehouse=self.w2, date=self.day, purpose="Material Transfer")
		self.movement(-3, -30, "Stock Entry", date=self.day, purpose="Material Issue")
		self.movement(-2, -20, "Stock Entry", date=self.sold, purpose="Material Issue")
		self.movement(999, 9990, cancelled=True)
		rows = {row.warehouse: row for row in self.rows()}
		self.assertEqual(set(rows), {self.w1, self.w2})
		row = rows[self.w1]
		self.assertEqual((row.remaining_qty, row.expired_stock_value, row.cost_per_unit), (42, 420, 10))
		self.assertEqual((row.sold_qty, row.sales_return_qty, row.net_sold_qty, row.cogs), (25, 2, 23, 230))
		self.assertEqual((row.expiry_issue_qty, row.expiry_issue_cost), (3, 30))
		self.assertEqual(rows[self.w2].expiry_issue_cost, 0)
		self.assertEqual(rows[self.w2].supplier, "expiry-supplier-A")
		self.assertEqual(rows[self.w2].received_date, getdate(self.received))
		self.assertEqual(rows[self.w2].receipt_type, "Purchase Receipt")
		self.assertEqual(row.last_received_date, getdate(self.received))
		self.assertEqual(report.get_expired_items_count()["value"], baseline + 1)
		self.assertEqual(self.rows(warehouse=self.w2)[0].supplier, "expiry-supplier-A")

	def test_legacy_batches_and_expiry_cutoff(self):
		self.movement(7, 35, legacy=True)
		self.movement(-2, -10, "Sales Invoice", legacy=True, date=self.sold)
		for expiry in (self.day, add_days(self.day, 1)):
			batch = self.insert("Batch", item=self.item, expiry_date=expiry)
			self.movement(100, 1000, batch=batch)
		self.movement(50, 250, date=add_days(self.day, 1))
		row, = self.rows()
		self.assertEqual((row.batch_no, row.remaining_qty, row.expired_stock_value, row.cogs), (self.batch, 5, 25, 10))
		self.assertEqual(report.execute({
			"company": self.company, "item_code": self.item, "as_of_date": str(self.expiry)})[1], [])

	def test_depleted_negative_and_free_stock(self):
		self.movement(10, 100)
		self.movement(-10, -100, "Sales Invoice", date=self.sold)
		self.assertEqual(self.rows(), [])
		row, = self.rows(include_depleted=1)
		self.assertEqual((row.remaining_qty, row.expired_stock_value, row.cogs), (0, 0, 100))
		negative = self.make_batch()
		self.movement(-2, -20, "Sales Invoice", batch=negative, date=self.sold)
		rows = {r.batch_no: r for r in self.rows(include_depleted=1)}
		self.assertIsNone(rows[negative].expired_stock_value)
		free = self.make_batch()
		self.movement(2, 0, batch=free)
		row, = self.rows()
		self.assertEqual((row.batch_no, row.remaining_qty, row.cost_per_unit, row.expired_stock_value), (free, 2, 0, 0))

	def test_multiple_suppliers_filter_keeps_whole_batch_balance(self):
		self.movement(100, 1000, supplier="expiry-supplier-A")
		self.movement(10, 150, "Purchase Invoice", supplier="expiry-supplier-B", date=self.sold)
		self.movement(-5, -50, "Purchase Receipt", supplier="expiry-supplier-A", date=self.sold)
		row, = self.rows(supplier="expiry-supplier-B")
		self.assertEqual((row.remaining_qty, row.expired_stock_value, row.received_qty, row.supplier_return_qty), (105, 1100, 110, 5))
		self.assertEqual(set(row.supplier.split(", ")), {"expiry-supplier-A", "expiry-supplier-B"})
		self.assertEqual(self.rows(supplier="expiry-unrelated-supplier"), [])

	def test_warehouse_permissions_apply_to_card_report_and_origins(self):
		self.movement(5, 50, supplier="expiry-visible-supplier")
		self.movement(10, 100, warehouse=self.w2, supplier="expiry-hidden-supplier")
		user = "expiry-test-" + uuid4().hex + "@example.invalid"
		self.temp_users.append(user)
		self.insert("User", name=user, email=user, first_name="Expiry Test", enabled=1, user_type="System User")
		self.insert("Has Role", parent=user, parenttype="User", parentfield="roles", role="Stock User")
		self.insert("User Permission", user=user, allow="Warehouse", for_value=self.w1, apply_to_all_doctypes=1)
		frappe.clear_cache(user=user)
		frappe.set_user(user)
		row, = self.rows()
		self.assertEqual((row.warehouse, row.remaining_qty, row.supplier), (self.w1, 5, "expiry-visible-supplier"))
		self.assertEqual(report.get_expired_items_count()["value"], 1)
		self.assertEqual(self.rows(warehouse=self.w2), [])
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			report.get_expired_items_count()

	def test_workspace_change_is_idempotent_and_preserves_other_blocks(self):
		data = {"number_cards": [{"number_card_name": "Out of Stock Items"}], "content": json.dumps([
			{"id": "out", "type": "number_card", "data": {"number_card_name": "Out of Stock Items", "col": 4}},
			{"id": "custom", "type": "custom_block", "data": {"custom_block_name": "Keep Me", "col": 7}},
		])}
		add_card(data)
		once = json.dumps(data)
		add_card(data)
		self.assertEqual(json.dumps(data), once)
		blocks = json.loads(data["content"])
		self.assertEqual(blocks[1]["data"]["number_card_name"], "Expired Items")
		self.assertEqual(blocks[2], {"id": "custom", "type": "custom_block", "data": {"custom_block_name": "Keep Me", "col": 7}})
