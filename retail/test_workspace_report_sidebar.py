import unittest
from unittest.mock import patch

import frappe
from retail import workspace_permissions, module_access


class TestWorkspaceReportSidebar(unittest.TestCase):
	def setUp(self):
		self.patch(__import__("retail.sidebar_permissions", fromlist=["selection"]), "selection", return_value=None)
		self.patch(module_access, "allowed", return_value=True)
		self.patch(frappe.local, "flags", new=frappe._dict(in_test=True), create=True)
		self.patch(workspace_permissions, "_get_blocked_modules", return_value=set())
		self.allowed_reports = self.patch(workspace_permissions, "get_allowed_reports", return_value={})
		self.has_permission = self.patch(frappe, "has_permission", return_value=True)
		self.reports = {}
		self.get_cached_doc = self.patch(
			frappe, "get_cached_doc", side_effect=lambda _doctype, name: self.reports[name]
		)

	def patch(self, target, attribute, **kwargs):
		patcher = patch.object(target, attribute, **kwargs)
		self.addCleanup(patcher.stop)
		return patcher.start()

	def allow_report(self, name, **fields):
		self.reports[name] = frappe._dict(
			name=name, disabled=0, module="Accounts", ref_doctype="Sales Invoice"
		)
		self.reports[name].update(fields)
		self.allowed_reports.return_value[name] = {}

	def test_tax_only_access_keeps_accounts_ancestor_and_query_route(self):
		self.allow_report("Tax Report")

		pages = workspace_permissions.get_permitted_report_sidebar_items()

		self.assertEqual([page.title for page in pages], ["Accounts Reports", "Tax Reports", "Tax Report"])
		self.assertEqual(pages[0].parent_page, "Reports")
		self.assertEqual(pages[1].parent_page, "Accounts Reports")
		self.assertEqual(pages[2].parent_page, "Tax Reports")
		self.assertEqual(pages[2].route, ["query-report", "Tax Report"])
		self.assertNotEqual(pages[2].name, pages[2].title)

	def test_disabled_blocked_and_unreadable_reports_are_omitted(self):
		self.allow_report("Daily Sales Summary", disabled=1)
		self.allow_report("Gross Profit", module="Blocked Module")
		self.allow_report("Stock Balance", ref_doctype="Unreadable DocType")
		self.allow_report("Tax Report")
		workspace_permissions._get_blocked_modules.return_value = {"Blocked Module"}
		self.has_permission.side_effect = lambda doctype, _permission: doctype != "Unreadable DocType"

		pages = workspace_permissions.get_permitted_report_sidebar_items()

		self.assertEqual([page.title for page in pages if page.is_report_link], ["Tax Report"])
		self.assertEqual(self.get_cached_doc.call_count, 4)

	def test_reports_workspace_keeps_categories_and_permitted_report_links(self):
		self.allow_report("Accounts Receivable")
		standard_pages = [
			frappe._dict(name="Reports", title="Reports", public=1),
			frappe._dict(name="Accounts", title="Accounts", public=1),
			frappe._dict(name="Accounts Receivable", title="Accounts Receivable", parent_page="Accounts", public=1),
		]
		self.patch(workspace_permissions, "get_standard_workspace_sidebar_items", return_value={"pages": standard_pages})
		self.patch(workspace_permissions, "_get_role_allowed_sidebar_workspaces", return_value={"Reports"})
		self.patch(workspace_permissions, "_workspace_has_permitted_content", return_value=False)
		self.patch(workspace_permissions, "_workspace_has_route_permission", return_value=False)

		pages = workspace_permissions.get_workspace_sidebar_items()["pages"]

		self.assertEqual([page.get("title") for page in pages], ["Reports", "Accounts Reports", "Accounts Receivable"])
		self.assertTrue(pages[0]["is_workspace_link"])
		self.assertTrue(pages[1]["is_report_group"])
		self.assertEqual(pages[2]["route"], ["query-report", "Accounts Receivable"])

	def test_reports_sidebar_role_gate_is_preserved(self):
		self.patch(workspace_permissions, "get_standard_workspace_sidebar_items", return_value={
			"pages": [frappe._dict(name="Reports", title="Reports", public=1)]
		})
		self.patch(workspace_permissions, "_get_role_allowed_sidebar_workspaces", return_value={"Sales"})
		self.patch(workspace_permissions, "_workspace_has_permitted_content", return_value=True)
		self.patch(workspace_permissions, "_workspace_has_route_permission", return_value=False)

		self.assertEqual(workspace_permissions.get_workspace_sidebar_items()["pages"], [])
		self.allowed_reports.assert_not_called()

	def test_home_boot_keeps_report_access_separate_from_workspace_navigation(self):
		self.allow_report("Accounts Receivable")
		pages = [frappe._dict(name="Reports", title="Reports", public=1, is_workspace_link=1)]
		self.patch(workspace_permissions, "get_workspace_sidebar_items", return_value={"pages": pages})
		self.patch(workspace_permissions, "_get_role_allowed_sidebar_workspaces", return_value={"Reports"})
		bootinfo = frappe._dict()

		workspace_permissions.extend_bootinfo(bootinfo)

		self.assertEqual(bootinfo.allowed_workspaces, pages)
		self.assertEqual(bootinfo.retail_allowed_workspace_reports, ["Accounts Receivable"])
		self.assertEqual(bootinfo.retail_workspace_sidebar_groups["Accounts Receivable"], "Accounts")

	def test_promotions_loyalty_links_are_nested_and_permission_checked(self):
		self.patch(workspace_permissions, "get_standard_workspace_sidebar_items", return_value={
			"pages": [frappe._dict(name="Promotions", title="Promotions", public=1)]
		})
		self.patch(workspace_permissions, "_get_role_allowed_sidebar_workspaces", return_value={"Promotions"})
		self.patch(workspace_permissions, "_workspace_has_permitted_content", return_value=True)
		self.patch(workspace_permissions, "_workspace_has_route_permission", return_value=True)
		pages = workspace_permissions.get_workspace_sidebar_items()["pages"]
		loyalty = [page for page in pages if page.get("label", "").startswith("Loyalty")]
		self.assertEqual(len(loyalty), 5)
		self.assertEqual(loyalty[0].parent_page, "Promotions")
		for page in loyalty[1:]:
			self.assertEqual(page.parent_page, loyalty[0].name)
		self.assertEqual(loyalty[2].route, ["List", "Loyalty Program", "Report"])
		self.assertEqual(loyalty[4].route, ["List", "Loyalty Point Entry", "Report"])
		self.has_permission.side_effect = lambda doctype, permission: permission != "report"
		pages = workspace_permissions.get_workspace_sidebar_items()["pages"]
		self.assertEqual([page.label for page in pages if page.get("label", "").startswith("Loyalty")],
			["Loyalty Program", "Loyalty Program List", "Loyalty Point Entry"])
