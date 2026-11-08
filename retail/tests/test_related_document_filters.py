"""Permission-aware list connections, using rolled-back synthetic transactions."""

import json
import unittest
from unittest.mock import patch
from uuid import uuid4

import frappe

from retail import document_item_filters as filters
from retail import related_document_filters as related


class TestRelatedDocumentFilters(unittest.TestCase):
	def setUp(self):
		self.user = frappe.session.user
		frappe.set_user("Administrator")
		self.form = frappe.local.form_dict
		self.token = "related-test-" + uuid4().hex
		frappe.db.savepoint("related_filter_test")

	def tearDown(self):
		frappe.db.rollback(save_point="related_filter_test")
		frappe.local.form_dict = self.form
		frappe.flags[filters.FLAG] = None
		frappe.set_user(self.user)

	def insert(self, doctype, suffix, **values):
		doc = frappe.get_doc(dict(doctype=doctype, name=self.token + suffix, **values))
		doc.db_insert()
		return doc.name

	def item(self, doctype, parent, suffix, **values):
		return self.insert(doctype + " Item", suffix, parent=parent, parenttype=doctype,
			parentfield="items", item_code="RELATED-ITEM", **values)

	def chain(self):
		so = self.insert("Sales Order", "-so")
		po = self.insert("Purchase Order", "-po")
		self.item("Purchase Order", po, "-po-row", sales_order=so)
		receipts, invoices = [], []
		for i in range(2):
			pr = self.insert("Purchase Receipt", f"-pr-{i}")
			pi = self.insert("Purchase Invoice", f"-pi-{i}")
			self.item("Purchase Receipt", pr, f"-pr-row-{i}", purchase_order=po)
			# Exercise indirect links even when the invoice has no PO field.
			for j in range(2):
				self.item("Purchase Invoice", pi, f"-pi-row-{i}-{j}", purchase_receipt=pr)
			receipts.append(pr)
			invoices.append(pi)
		return so, po, receipts, invoices

	def request(self, source, count=False, target="Purchase Invoice", **criteria):
		frappe.local.form_dict = frappe._dict(doctype=target, fields=["name"],
			filters=[["name", "like", self.token + "%"]], order_by="name asc", start=0,
			page_length=20, retail_item_filters={"related_document": json.dumps(source), **criteria})
		return filters.get_count() if count else filters.get()

	def names(self, result):
		return {row[result["keys"].index("name")] for row in result["values"]} if result else set()

	def test_forward_reverse_branches_counts_pagination_and_item_intersection(self):
		so, po, receipts, invoices = self.chain()
		for source in (("Sales Order", so), ("Purchase Order", po),
			("Purchase Receipt", receipts[0]), ("Purchase Invoice", invoices[0])):
			self.assertEqual(self.names(self.request(source)), set(invoices))
			self.assertEqual(self.request(source, count=True), 2)
		self.assertEqual(self.names(self.request(("Purchase Order", po), item_code="RELATED-ITEM")), set(invoices))
		self.assertEqual(self.request(("Purchase Order", po), count=True, item_code="OTHER"), 0)
		self.request(("Purchase Order", po))
		frappe.local.form_dict.update(start=1, page_length=1)
		self.assertEqual(self.names(filters.get()), {sorted(invoices)[1]})
		self.assertIsNone(frappe.flags.get(filters.FLAG))

	def test_shared_supplier_is_not_a_connection_and_unlinked_source_is_empty(self):
		po = self.insert("Purchase Order", "-po", supplier="SAME-SUPPLIER")
		pi = self.insert("Purchase Invoice", "-pi", supplier="SAME-SUPPLIER")
		self.assertEqual(self.names(self.request(("Purchase Order", po))), set())
		self.assertEqual(self.request(("Purchase Order", po), count=True), 0)
		self.assertEqual(related.purchase_invoices(["Purchase Invoice", pi]), [pi])

	def test_dynamic_reference_checks_type_when_ids_collide(self):
		pi = self.insert("Purchase Invoice", "-shared")
		pr = self.insert("Purchase Receipt", "-shared")
		payment = self.insert("Payment Entry", "-payment")
		self.insert("Payment Entry Reference", "-reference", parent=payment,
			parenttype="Payment Entry", parentfield="references",
			reference_doctype="Purchase Invoice", reference_name=pi)
		self.assertEqual(related.purchase_invoices(["Payment Entry", payment]), [pi])
		self.assertEqual(related.purchase_invoices(["Purchase Receipt", pr]), [])

	def test_source_intermediate_and_target_list_permissions_are_enforced(self):
		so, po, receipts, invoices = self.chain()
		native = frappe.get_list

		def restricted(doctype, *args, **kwargs):
			if doctype == blocked:
				return []
			return native(doctype, *args, **kwargs)

		for blocked in ("Purchase Order", "Purchase Receipt", "Purchase Invoice"):
			with patch.object(related.frappe, "get_list", side_effect=restricted):
				self.assertEqual(related.purchase_invoices(["Sales Order", so]), [])
		blocked = "Sales Order"
		with patch.object(related.frappe, "get_list", side_effect=restricted):
			with self.assertRaises(frappe.PermissionError):
				related.purchase_invoices(["Sales Order", so])
		# Final native list/count permissions apply in addition to graph permissions.
		with patch("frappe.model.db_query.DatabaseQuery.get_permission_query_conditions", return_value="1=0"):
			with self.assertRaises(frappe.PermissionError):
				self.request(("Sales Order", so))

	def test_unreadable_child_reference_cannot_be_used_for_traversal(self):
		so, po, receipts, invoices = self.chain()
		native = related.get_permitted_fields

		def permitted(doctype, *args, **kwargs):
			fields = native(doctype, *args, **kwargs)
			return [field for field in fields if field != "sales_order"] if doctype == "Purchase Order Item" else fields

		with patch.object(related, "get_permitted_fields", side_effect=permitted):
			self.assertEqual(related.purchase_invoices(["Sales Order", so]), [])

	def test_validation_scope_context_restoration_and_graph_limit(self):
		for value in ("not json", {}, ["Supplier", "S-1"], ["Purchase Order", ""],
			["Purchase Order", "x" * 141], ["Purchase Order", []]):
			with self.assertRaises(frappe.ValidationError):
				related.normalize(value)
		with self.assertRaises(frappe.ValidationError):
			filters.normalize("POS Invoice", {"related_document": '["Purchase Order", "PO-1"]'})
		so, po, receipts, invoices = self.chain()
		with patch.object(related, "MAX_DOCUMENTS", 1):
			with self.assertRaises(frappe.ValidationError):
				self.request(("Purchase Order", po))
		self.assertIsNone(frappe.flags.get(filters.FLAG))
		self.assertIn("related_document", frappe.local.form_dict.retail_item_filters)

	def test_search_uses_id_type_and_native_permissions(self):
		so, po, receipts, invoices = self.chain()
		# An older exact ID must remain selectable among newer substring matches.
		frappe.db.set_value("Purchase Order", po, "modified", "2000-01-01", update_modified=False)
		for i in range(10):
			self.insert("Purchase Order", f"-po-{i}")
		results = related.search(po)
		self.assertEqual(json.loads(results[0]["value"]), ["Purchase Order", po])
		self.assertIn("Purchase Order", results[0]["label"])
		with patch("frappe.model.db_query.DatabaseQuery.get_permission_query_conditions", return_value="1=0"):
			self.assertEqual(related.search(po), [])

	def test_all_sales_purchase_lists_share_forward_reverse_search_and_counts(self):
		so, po, receipts, invoices = self.chain()
		quotation = self.insert("Quotation", "-quotation")
		supplier_quotation = self.insert("Supplier Quotation", "-supplier-quotation")
		delivery = self.insert("Delivery Note", "-delivery")
		invoice = self.insert("Sales Invoice", "-sales-invoice", is_consolidated=0)
		self.item("Sales Order", so, "-so-row", prevdoc_docname=quotation)
		self.item("Purchase Order", po, "-supplier-row", supplier_quotation=supplier_quotation)
		self.item("Delivery Note", delivery, "-delivery-row", against_sales_order=so)
		self.item("Sales Invoice", invoice, "-sales-invoice-row", delivery_note=delivery)
		expected = {"Quotation": {quotation}, "Supplier Quotation": {supplier_quotation},
			"Sales Order": {so}, "Purchase Order": {po}, "Delivery Note": {delivery},
			"Sales Invoice": {invoice}, "Purchase Receipt": set(receipts), "Purchase Invoice": set(invoices)}
		for target in related.LIST_DOCTYPES:
			for source in (("Quotation", quotation), ("Purchase Invoice", invoices[0])):
				self.assertEqual(self.names(self.request(source, target=target)), expected[target])
				self.assertEqual(self.request(source, target=target, count=True), len(expected[target]))
			# The user's ordinary filters still intersect, never get replaced.
			frappe.local.form_dict.filters.append(["name", "=", "DOES-NOT-EXIST"])
			self.assertEqual(filters.get_count(), 0)

	def test_new_lists_do_not_gain_item_filters_and_pi_permission_is_not_required(self):
		for dt in set(related.LIST_DOCTYPES) - set(filters.DOCTYPES):
			with self.assertRaises(frappe.ValidationError):
				filters.normalize(dt, {"item_code": "ITEM"})
			self.assertEqual(filters.normalize(dt, {}), {})
		so, po, receipts, invoices = self.chain()
		native = frappe.has_permission

		def can_read(doctype, *args, **kwargs):
			if doctype == "Purchase Invoice":
				if kwargs.get("throw"):
					raise frappe.PermissionError
				return False
			return native(doctype, *args, **kwargs)

		with patch.object(related.frappe, "has_permission", side_effect=can_read):
			results = related.search(so, doctype="Sales Order")
			self.assertEqual(json.loads(results[0]["value"]), ["Sales Order", so])
			self.assertEqual(self.names(self.request(("Purchase Order", po), target="Sales Order")), {so})
			with self.assertRaises(frappe.PermissionError):
				related.search(so, doctype="Purchase Invoice")
		with self.assertRaises(frappe.ValidationError):
			related.search(so, doctype="Supplier")

	def test_shared_hooks_append_without_displacing_existing_list_scripts(self):
		for dt in related.LIST_DOCTYPES:
			self.assertIn("public/js/list/document_item_filters.js", frappe.get_hooks("doctype_list_js")[dt])
			self.assertIn("retail.document_item_filters.query_conditions",
				frappe.get_hooks("permission_query_conditions")[dt])
		self.assertIn("public/js/sales_invoice_list.js", frappe.get_hooks("doctype_list_js")["Sales Invoice"])
		self.assertIn("public/js/sales_order_list.js", frappe.get_hooks("doctype_list_js")["Sales Order"])
