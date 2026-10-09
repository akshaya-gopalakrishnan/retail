import json
import unittest
from unittest.mock import Mock, patch

import frappe
from retail import sidebar_permissions as access
from retail.sidebar_registry import registry, entries

class TestSidebarPermissions(unittest.TestCase):
    def setUp(self):
        self.patch(frappe.local, "session", new=frappe._dict(user="sidebar-a@example.test"), create=True)
        self.patch(frappe.local, "flags", new=frappe._dict(), create=True)
        self.patch(frappe.local, "form_dict", new=frappe._dict(), create=True)
        self.patch(frappe.local, "request", new=frappe._dict(path="/api/method/frappe.client.get_list", method="GET"), create=True)
        self.patch(frappe.local, "db", new=Mock(has_column=Mock(return_value=True), exists=Mock(return_value=False)), create=True)
        self.patch(access, "is_super_admin", return_value=False)
        self.admin = self.patch(access, "require_super_admin", side_effect=frappe.PermissionError)
        self.patch(frappe, "_", side_effect=lambda message: message)
        self.patch(frappe, "throw", side_effect=frappe.PermissionError)
        self.native = self.patch(frappe, "has_permission", return_value=True)
        self.configurations = {}
        self.patch(frappe, "get_cached_doc", side_effect=lambda dt, user: frappe._dict({access.FIELD: self.configurations.get(user)}))

    def patch(self, obj, name, **kwargs):
        p = patch.object(obj, name, **kwargs)
        self.addCleanup(p.stop)
        return p.start()

    def select(self, *workspaces, user=None):
        identifiers = {entry["id"] for entry in entries() if entry["workspace"] in workspaces}
        for group in registry():
            if any(child["id"] in identifiers for child in group["children"]):
                identifiers.add(group["id"])
        self.configurations[user or frappe.session.user] = json.dumps({"version": 1, "allowed": sorted(identifiers)})

    def test_exact_menu_labels_and_order(self):
        expected = {
            "Business Home": [],
            "Items": ["Items List", "Item Family List", "Item Groups", "Price Lists", "Brands"],
            "Sales": ["Customers", "Quotations", "Sales Orders", "Sales Invoices", "Sales Returns", "Delivery Notes"],
            "Purchases": ["Suppliers", "Request for Quotations", "Supplier Quotations", "Purchase Orders", "Purchase Receipts", "Purchase Invoices", "Purchase Returns", "Material Requests"],
            "Stocks": ["Warehouses", "Stock Adjustments", "Stock Take", "Serials & Batches", "Stock Status"],
            "Accounts": ["Bank Accounts", "Payments", "Taxes", "Journal Entries", "Accounts Receivable", "Accounts Payable"],
            "Manufacturing": ["BOM", "Production Plan", "Work Orders", "Job Cards", "Stock Entries", "Quality Inspection", "Reports", "Setup"],
            "POS": ["POS Invoices", "POS Profiles", "POS Counters", "POS Cashier Shifts", "POS Counter Sessions", "POS Opening Entries", "POS Closing Entries", "POS Branch Day Closings", "POS Sync Logs", "POS Reports"],
            "Van Sales": ["Fleet", "Driver", "Van Sessions", "Van Stock View", "Stock Request", "Van Stock Entries", "Van Sales Invoice", "Van Payments", "Van Customers", "Items", "Warehouses", "Van Sales Reports"],
            "Reports": ["Sales Reports", "Purchase Reports", "Stock Reports", "Accounts Reports", "POS Sales Reports", "Manufacturing Module"],
            "Promotions": ["Promo Price", "Buy X Get Y Promotion", "Gift Voucher Promotion", "Gift Voucher Ledger", "Loyalty Program"],
            "Settings": ["Business Profile", "Branding", "System Rules", "User List", "Employee List"],
        }
        self.assertEqual([(group["label"], [child["label"] for child in group["children"]]) for group in registry()], list(expected.items()))
        ids = [entry["id"] for entry in entries()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_migration_legacy_and_protected_exemption(self):
        self.assertIsNone(access.selection())
        self.select()
        self.assertEqual(access.selection(), set())
        self.patch(access, "is_super_admin", return_value=True)
        self.assertIsNone(access.selection())
        self.assertTrue(access.target_allowed("doctype", "Customer"))

    def test_invoice_only_customer_only_multiple_and_user_isolation(self):
        self.select("Sales Invoices")
        self.select("Customers", user="sidebar-b@example.test")
        self.assertTrue(access.target_allowed("doctype", "Sales Invoice"))
        self.assertFalse(access.target_allowed("doctype", "Customer"))
        self.assertFalse(access.target_allowed("doctype", "Sales Invoice", "sidebar-b@example.test"))
        self.assertTrue(access.target_allowed("doctype", "Customer", "sidebar-b@example.test"))
        self.select("Sales Invoices", "Customers")
        self.assertTrue(access.target_allowed("doctype", "Customer"))

    def test_return_and_van_classification(self):
        self.select("Sales Invoices", "Purchase Receipts")
        for dt in ("Sales Invoice", "Purchase Receipt"):
            access.require_document(frappe._dict(doctype=dt, is_return=0))
            with self.assertRaises(frappe.PermissionError):
                access.require_document(frappe._dict(doctype=dt, is_return=1))
        with self.assertRaises(frappe.PermissionError):
            access.require_document(frappe._dict(doctype="Sales Invoice", custom_is_van_sale=1))
        self.select("Sales Returns")
        access.require_document(frappe._dict(doctype="Sales Invoice", is_return=1))
        with self.assertRaises(frappe.PermissionError):
            access.require_document(frappe._dict(doctype="Sales Invoice", is_return=0))

    def test_administrator_saved_selection_is_enforced_with_own_editor_recovery(self):
        frappe.session.user = "Administrator"
        self.select("Sales Invoices")
        with patch.object(access, "is_super_admin", return_value=True):
            self.assertFalse(access.target_allowed("doctype", "Customer"))
            frappe.local.form_dict = frappe._dict(doctype="Customer")
            with self.assertRaises(frappe.PermissionError):
                access.guard_request()
            frappe.request.path = "/app/user/Administrator"
            access.guard_request()
            frappe.request.path = "/api/method/frappe.desk.form.load.getdoc"
            frappe.local.form_dict = frappe._dict(doctype="User", name="Administrator")
            access.guard_request()
            frappe.local.form_dict.name = "someone@example.test"
            with self.assertRaises(frappe.PermissionError):
                access.guard_request()
            frappe.request.path = "/api/method/frappe.desk.form.save.savedocs"
            frappe.local.form_dict = frappe._dict(doc='{"doctype":"User","name":"Administrator"}')
            access.guard_request()
            self.configurations["Administrator"] = None
            self.assertIsNone(access.selection())

    def test_stock_entry_purpose_and_van_isolation(self):
        self.select("Stock Adjustments")
        access.require_document(frappe._dict(doctype="Stock Entry", purpose="Material Receipt"))
        for doc in (frappe._dict(doctype="Stock Entry", purpose="Manufacture"),
                    frappe._dict(doctype="Stock Entry", purpose="Material Transfer", custom_is_van_stock_entry=1)):
            with self.assertRaises(frappe.PermissionError):
                access.require_document(doc)
        self.select("Stock Entries")
        access.require_document(frappe._dict(doctype="Stock Entry", purpose="Manufacture"))

    def test_list_conditions_are_only_applied_to_explicit_http_target(self):
        self.select("Sales Invoices")
        self.assertEqual(access.query_conditions(doctype="Sales Invoice"), "")
        frappe.flags.retail_sidebar_list_doctype = "Sales Invoice"
        conditions = access.query_conditions(doctype="Sales Invoice")
        self.assertIn("`is_return`, 0) = 0", conditions)
        self.assertIn("`custom_is_van_sale`, 0) = 0", conditions)
        self.assertEqual(access.query_conditions(doctype="Customer"), "")
        self.select("Sales Returns")
        self.assertIn("`is_return`, 0) = 1", access.query_conditions(doctype="Sales Invoice"))

    def test_linked_checks_and_internal_posting_are_not_denied(self):
        self.select()
        for dt in ("Customer", "Item", "GL Entry", "Stock Ledger Entry", "Stock Entry"):
            doc = Mock(doctype=dt)
            doc.get.return_value = "internal-record"
            self.assertIsNone(access.has_permission(doc))
            access.validate_document(doc)
            self.assertEqual(access.query_conditions(doctype=dt), "")

    def test_unauthorized_urls_and_api_read_write_methods(self):
        self.select("Sales Invoices")
        for method in ("GET", "POST", "PUT", "DELETE"):
            frappe.request.method = method
            frappe.request.path = "/api/resource/Customer"
            with self.assertRaises(frappe.PermissionError):
                access.guard_request()
        frappe.request.path = "/api/v2/document/Customer"
        with self.assertRaises(frappe.PermissionError):
            access.guard_request()
        frappe.request.path = "/api/method/frappe.client.get_list"
        frappe.local.form_dict = frappe._dict(doctype="Sales Invoice")
        access.guard_request()
        self.assertEqual(frappe.flags.retail_sidebar_list_doctype, "Sales Invoice")

    def test_config_write_requires_protected_administrator(self):
        doc = Mock()
        doc.get_doc_before_save.return_value = frappe._dict({access.FIELD: ""})
        doc.get.return_value = json.dumps({"version": 1, "allowed": []})
        with self.assertRaises(frappe.PermissionError):
            access.validate_user(doc)
        self.admin.assert_called_once()

    def test_normalize_parent_and_reject_unknown_identifier(self):
        self.admin.side_effect = None
        doc = Mock()
        doc.get_doc_before_save.return_value = None
        doc.get.return_value = json.dumps({"version": 1, "allowed": ["workspace:sales_invoices"]})
        access.validate_user(doc)
        self.assertEqual(json.loads(doc.set.call_args.args[1])["allowed"], ["workspace:sales", "workspace:sales_invoices"])
        doc.get.return_value = json.dumps({"version": 1, "allowed": ["label:Sales Invoices"]})
        with self.assertRaises(frappe.PermissionError):
            access.validate_user(doc)

    def test_partial_sales_filters_workspace_links_despite_van_customer_access(self):
        self.select("Sales Invoices", "Sales Orders", "Van Sales Customers Link")
        data = {
            "shortcuts": {"items": [
                {"type": "DocType", "link_to": "Customer", "label": "Customers"},
                {"type": "DocType", "link_to": "Quotation", "label": "Quotation"},
                {"type": "DocType", "link_to": "Sales Invoice", "label": "Sales Invoice"},
                {"type": "DocType", "link_to": "Sales Invoice", "label": "Sales Return"},
            ]},
            "cards": {"items": [{"label": "Customers", "links": [
                {"link_type": "DocType", "link_to": "Customer"}]}]},
            "quick_lists": {"items": [{"document_type": "Customer"}]},
        }
        self.assertTrue(access.enabled("workspace:sales"))
        filtered = access.filter_workspace(data, "Sales")
        self.assertEqual([row["label"] for row in filtered["shortcuts"]["items"]], ["Sales Invoice"])
        self.assertEqual(filtered["cards"]["items"], [])
        self.assertEqual(filtered["quick_lists"]["items"], [])
        frappe.flags.retail_sidebar_list_doctype = "Customer"
        self.assertIn("`custom_is_van_customer`, 0) = 1", access.query_conditions(doctype="Customer"))
        with self.assertRaises(frappe.PermissionError):
            access.require_document(frappe._dict(doctype="Customer", custom_is_van_customer=0))
        access.require_document(frappe._dict(doctype="Customer", custom_is_van_customer=1))

    def test_pos_service_selection_never_grants_native_actions(self):
        self.select("POS Invoices")
        frappe.request.path = "/api/method/retail.api.pos_sync.create_pos_invoice"
        access.guard_request()
        self.native.assert_any_call("POS Invoice", "submit")
        self.native.return_value = False
        with self.assertRaises(frappe.PermissionError):
            access.guard_request()
        self.select("Customers")
        self.native.return_value = True
        with self.assertRaises(frappe.PermissionError):
            access.guard_request()

    def test_saved_old_record_cannot_change_to_denied_classification(self):
        self.select("Sales Invoices")
        frappe.flags.retail_sidebar_documents = {("Sales Invoice", "INV-1")}
        doc = Mock(doctype="Sales Invoice")
        doc.get.side_effect = lambda field: {"name": "INV-1", "is_return": 0}.get(field)
        doc.get_doc_before_save.return_value = frappe._dict(doctype="Sales Invoice", is_return=1)
        with self.assertRaises(frappe.PermissionError):
            access.validate_document(doc)

    def test_selected_family_page_does_not_unlock_item_list(self):
        self.select("Item Family List")
        self.assertTrue(access.target_allowed("page", "retail-item-family-l"))
        self.assertFalse(access.target_allowed("doctype", "Item"))
        frappe.request.path = "/api/method/retail.retail_app.page.retail_item_family_l.retail_item_family_l.get_rows"
        access.guard_request()
        self.native.return_value = False
        with self.assertRaises(frappe.PermissionError):
            access.guard_request()

    def test_link_lookup_is_narrow_and_does_not_enable_full_customer_api(self):
        self.select("Sales Invoices")
        frappe.request.path = "/api/method/frappe.client.get_value"
        frappe.local.form_dict = frappe._dict(doctype="Customer", fieldname="customer_name", filters='{"name":"C-1"}')
        access.guard_request()
        frappe.local.form_dict.fieldname = "*"
        with self.assertRaises(frappe.PermissionError):
            access.guard_request()
        frappe.local.form_dict.fieldname = "customer_name"
        frappe.local.form_dict.filters = "{}"
        with self.assertRaises(frappe.PermissionError):
            access.guard_request()
        self.assertFalse(access.target_allowed("doctype", "Customer"))

    def test_saved_filter_metadata_cannot_hide_an_unrelated_document_write(self):
        self.select("Customers")
        frappe.request.path = "/api/method/frappe.client.save"
        frappe.local.form_dict = frappe._dict(doctype="List Filter", doc='{"doctype":"Sales Invoice"}')
        with self.assertRaises(frappe.PermissionError):
            access.guard_request()

    def test_code_initialization_follows_selected_list_and_native_permission(self):
        self.select("Business Profile")
        frappe.request.path = "/api/method/retail.document_codes.ensure_codes"
        frappe.local.form_dict = frappe._dict(doctype="Company")
        access.guard_request()
        self.native.return_value = False
        with self.assertRaises(frappe.PermissionError):
            access.guard_request()
        self.native.return_value = True
        frappe.local.form_dict.doctype = "Customer"
        with self.assertRaises(frappe.PermissionError):
            access.guard_request()

    def test_selected_report_definition_and_unlisted_report_configuration(self):
        self.select("Accounts Reports")
        frappe.request.path = "/api/method/frappe.desk.form.load.getdoc"
        frappe.local.form_dict = frappe._dict(doctype="Report", name="General Ledger")
        access.guard_request()
        self.select("Customers")
        with self.assertRaises(frappe.PermissionError):
            access.guard_request()
        self.select("Accounts Reports")
        frappe.request.path = "/api/method/frappe.client.get_list"
        access.guard_request()  # Report configuration is outside the checklist.
        frappe.request.path = "/api/method/frappe.client.save"
        access.guard_request()

    def test_invoice_search_filters_each_invoice_doctype(self):
        self.select("Sales Returns")
        frappe.request.path = "/api/method/retail.invoice_search.search_invoices"
        access.guard_request()
        self.assertEqual(access.query_conditions(doctype="POS Invoice"), "1=0")
        self.assertIn("`is_return`, 0) = 1", access.query_conditions(doctype="Sales Invoice"))

    def test_native_async_export_retains_row_restrictions_without_affecting_posting_jobs(self):
        self.select("Sales Returns")
        access.before_job(method="retail.pos_settlements.recover", kwargs={})
        self.assertEqual(access.query_conditions(doctype="Sales Invoice"), "")
        access.before_job(method="frappe.desk.reportview.run_report_view_export_job", kwargs={"form_params": {"doctype": "Sales Invoice"}})
        self.assertIn("`is_return`, 0) = 1", access.query_conditions(doctype="Sales Invoice"))

    def test_private_attachment_cannot_bypass_denied_parent_document(self):
        self.select("Sales Invoices")
        frappe.request.path = "/private/files/customer.pdf"
        self.patch(frappe, "get_all", return_value=[frappe._dict(attached_to_doctype="Customer", attached_to_name="C-1", owner=frappe.session.user)])
        with self.assertRaises(frappe.PermissionError):
            access.guard_request()

    def test_unlisted_targets_routes_and_rpcs_retain_native_access(self):
        self.select()
        for kind, target in (("doctype", "UOM"), ("doctype", "Address"), ("doctype", "Dashboard Settings"),
                             ("report", "Unlisted Report"), ("page", "future-page")):
            self.assertTrue(access.target_allowed(kind, target))
        for path, params in (
            ("/api/method/frappe.client.get_list", {"doctype": "UOM"}),
            ("/api/method/frappe.desk.form.load.getdoc", {"doctype": "Address", "name": "ADDR-1"}),
            ("/api/method/frappe.desk.query_report.run", {"report_name": "Unlisted Report"}),
            ("/api/method/frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config", {"name": "Any Source"}),
            ("/api/method/retail.some_future_api.helper", {}),
            ("/app/uom", {}), ("/app/future-page", {}),
        ):
            with self.subTest(path=path):
                frappe.request.path = path
                frappe.local.form_dict = frappe._dict(params)
                access.guard_request()
        self.assertEqual(access.query_conditions(doctype="UOM"), "")
        access.require_document(frappe._dict(doctype="Address"))

    def test_unchecked_checklist_targets_still_deny(self):
        self.select("Business Profile", "Items List")
        for path, params in (
            ("/api/method/frappe.client.get_list", {"doctype": "Customer"}),
            ("/api/method/frappe.desk.query_report.run", {"report_name": "General Ledger"}),
            ("/app/customer", {}), ("/app/manufacturing", {}),
            ("/api/method/retail.retail_app.page.retail_item_family_l.retail_item_family_l.get_rows", {}),
        ):
            with self.subTest(path=path):
                frappe.request.path = path
                frappe.local.form_dict = frappe._dict(params)
                with self.assertRaises(frappe.PermissionError):
                    access.guard_request()
