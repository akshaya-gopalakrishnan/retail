"""Run on retail-test.localhost; all fixtures are rolled back by the runner."""

import unittest
from unittest.mock import patch

import frappe

from retail import access_control as access


class TestAccessControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not getattr(frappe.local, "db", None):
            raise unittest.SkipTest("Requires an initialized Frappe test site")
        frappe.set_user("Administrator")
        frappe.flags.in_test = True
        access.install()
        from retail.delegated_access import install
        install()
        cls.users = {}
        cls.module_profile = frappe.get_doc({"doctype": "Module Profile", "module_profile_name": "Access Test " + frappe.generate_hash(length=8)}).insert().name
        cls.gravatar = patch("frappe.core.doctype.user.user.update_gravatar")
        cls.gravatar.start()
        for label, roles in {
            "super": ["Super Admin", "System Manager"],
            "customer": ["Customer Administrator", "Sales User", "Stock User"],
            "legacy_manager": ["System Manager"],
            "staff": ["Sales User"],
        }.items():
            user = frappe.get_doc({
                "doctype": "User", "email": f"access-{label}-{frappe.generate_hash(length=8)}@example.com",
                "first_name": f"Access Test {label}", "send_welcome_email": 0,
                "user_type": "System User", "roles": [{"role": role} for role in roles],
                "retail_access_manager": cls.users.get("customer") if label == "staff" else None,
                "block_modules": [{"module": "Manufacturing"}] if label in ("customer", "staff") else [],
                "retail_sidebar_permissions": '{"version":1,"allowed":["workspace:sales","workspace:sales_invoices","workspace:settings","workspace:user_list"]}' if label in ("customer", "staff") else None,
            }).insert(ignore_permissions=True)
            cls.users[label] = user.name

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        cls.gravatar.stop()
        frappe.db.rollback()
        frappe.clear_cache()

    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.savepoint("access_test")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="access_test")
        frappe.clear_cache()

    def test_defaults_are_native_and_editable_without_reseeding(self):
        self.assertTrue(frappe.db.exists("Role Profile", "Administrator"))
        profile = frappe.get_doc("Role Profile", "Administrator")
        self.assertNotIn("System Manager", [row.role for row in profile.roles])
        profile.roles = []
        profile.append("roles", {"role": "Employee"})
        profile.save()
        access.install()
        self.assertEqual([r.role for r in frappe.get_doc("Role Profile", "Administrator").roles], ["Employee"])

    def test_customer_cannot_assign_access_outside_ceiling_even_ignoring_permissions(self):
        for field, value in (("role_profile_name", "Super Admin"), ("module_profile", self.module_profile), ("roles", [{"role": "Super Admin"}]), ("block_modules", [{"module": "POS"}])):
            with self.subTest(field=field):
                frappe.set_user(self.users["customer"])
                doc = frappe.get_doc("User", self.users["staff"])
                doc.set(field, value)
                with self.assertRaises(frappe.PermissionError):
                    doc.save(ignore_permissions=True)

    def test_customer_can_edit_business_user_details(self):
        frappe.set_user(self.users["customer"])
        doc = frappe.get_doc("User", self.users["staff"])
        doc.first_name = "Updated by customer"
        doc.save()
        self.assertEqual(frappe.db.get_value("User", doc.name, "first_name"), "Updated by customer")

    def test_super_users_are_hidden_from_customer_lists_and_document_access(self):
        frappe.set_user(self.users["customer"])
        names = frappe.get_list("User", pluck="name", limit_page_length=0)
        self.assertNotIn(self.users["super"], names)
        self.assertNotIn("Administrator", names)
        self.assertIn(self.users["staff"], names)
        self.assertFalse(frappe.has_permission("User", "read", self.users["super"]))
        doc = frappe.get_doc("User", self.users["super"])
        doc.enabled = 0
        with self.assertRaises(frappe.PermissionError):
            doc.save(ignore_permissions=True)

    def test_legacy_system_manager_cannot_change_security(self):
        frappe.set_user(self.users["legacy_manager"])
        for dt, name in (("Role Profile", "Administrator"), ("Role", "Employee")):
            with self.subTest(doctype=dt):
                doc = frappe.get_doc(dt, name)
                self.assertFalse(access.has_permission(doc))
                with self.assertRaises(frappe.PermissionError):
                    doc.save(ignore_permissions=True)

    def test_super_admin_can_edit_builtin_administrator_and_profiles(self):
        frappe.set_user(self.users["super"])
        doc = frappe.get_doc("User", "Administrator")
        self.assertTrue(frappe.has_permission("User", "write", doc))
        doc.save()
        profile = frappe.get_doc("Role Profile", "Administrator")
        profile.save()
        for dt in ("Sales Invoice", "System Settings", "Role Profile", "User", "Server Script"):
            self.assertTrue(frappe.has_permission(dt, "write"), dt)

    def test_http_guards_cover_native_permission_apis_and_resource_routes(self):
        frappe.set_user(self.users["legacy_manager"])
        cases = [
            ("/api/method/frappe.core.page.permission_manager.permission_manager.update", {}),
            ("/api/method/frappe.client.set_value", {"doctype": "Module Profile"}),
            ("/api/resource/Role%20Profile/Administrator", {}),
            ("/api/v2/document/User/" + self.users["super"], {}),
            ("/api/method/frappe.core.doctype.user.user.generate_keys", {"user": self.users["super"]}),
            ("/api/method/frappe.desk.desk_page.getpage", {"name": "permission-manager"}),
        ]
        for path, args in cases:
            with self.subTest(path=path), patch.object(frappe.local, "request", frappe._dict(path=path), create=True), patch.object(frappe.local, "form_dict", frappe._dict(args), create=True):
                with self.assertRaises(frappe.PermissionError):
                    access.guard_request()

    def test_operational_tools_use_native_permissions(self):
        frappe.set_user(self.users["legacy_manager"])
        for dt in ("Data Import", "Data Export", "Workflow", "Workflow State",
                   "Workflow Action Master", "Repost Accounting Ledger",
                   "Repost Accounting Ledger Settings", "Repost Allowed Types",
                   "System Settings", "Customize Form", "Workspace"):
            with self.subTest(doctype=dt):
                doc = frappe.get_doc({"doctype": dt})
                self.assertIsNone(access.has_permission(doc, ptype="write"))
                self.assertEqual(access.query_conditions(doctype=dt), "")
                access.validate_document(doc)
        for path, args in (
            ("/api/method/frappe.core.doctype.data_import.data_import.form_start_import", {}),
            ("/api/method/frappe.core.doctype.data_export.data_export.export_data", {}),
            ("/api/method/frappe.desk.desk_page.getpage", {"name": "customize-form"}),
            ("/api/method/run_doc_method", {"docs": '{"doctype": "Data Import"}'}),
        ):
            with self.subTest(path=path), patch.object(frappe.local, "request", frappe._dict(path=path), create=True), patch.object(frappe.local, "form_dict", frappe._dict(args), create=True):
                access.guard_request()
        frappe.set_user(self.users["staff"])
        self.assertFalse(frappe.has_permission("Data Import", "create"))

    def test_role_profile_changes_propagate_using_native_behavior(self):
        profile = frappe.get_doc({"doctype": "Role Profile", "role_profile": "Access Test " + frappe.generate_hash(length=8), "roles": [{"role": "Stock User"}]}).insert()
        user = frappe.get_doc("User", self.users["staff"])
        user.role_profile_name = profile.name
        user.save()
        frappe.set_user(self.users["super"])
        profile.append("roles", {"role": "Sales User"})
        profile.save()
        self.assertIn("Sales User", frappe.get_roles(user.name))

    def test_password_recovery_does_not_target_protected_account(self):
        frappe.set_user("Guest")
        with patch("frappe.core.doctype.user.user.reset_password") as native:
            access.reset_password(self.users["super"])
            native.assert_called_once_with("Administrator")

    def test_customer_retains_business_access(self):
        frappe.set_user(self.users["customer"])
        for dt in ("Sales Invoice", "Purchase Invoice", "Stock Entry", "Employee", "Company"):
            self.assertTrue(frappe.has_permission(dt, "write"), dt)

    def test_customer_can_create_unassigned_user(self):
        frappe.set_user(self.users["customer"])
        user = frappe.get_doc({"doctype": "User", "email": f"unassigned-{frappe.generate_hash(length=8)}@example.com", "first_name": "Unassigned", "send_welcome_email": 0}).insert()
        self.assertEqual(user.roles, [])

    def test_protected_user_cannot_be_shared_or_renamed_by_customer(self):
        frappe.set_user(self.users["customer"])
        doc = frappe.get_doc("User", self.users["super"])
        with self.assertRaises(frappe.PermissionError):
            access.validate_document(doc, "before_rename", doc.name, "changed@example.com", False)
        share = frappe.get_doc({"doctype": "DocShare", "share_doctype": "User", "share_name": self.users["super"], "user": self.users["customer"], "read": 1})
        with self.assertRaises(frappe.PermissionError):
            share.insert(ignore_permissions=True)

    def test_customer_assigns_own_roles_and_sidebar_to_new_staff(self):
        from retail.delegated_access import get_all_roles
        from retail.sidebar_permissions import get_editor
        frappe.set_user(self.users["customer"])
        available = get_all_roles()
        self.assertIn("Sales User", available)
        self.assertNotIn("Super Admin", available)
        self.assertNotIn("System Manager", available)
        visible = {row["id"] for group in get_editor() for row in [group, *group["children"]]}
        self.assertIn("workspace:sales_invoices", visible)
        self.assertNotIn("workspace:van_sales", visible)
        user = frappe.get_doc({"doctype": "User", "email": f"delegated-{frappe.generate_hash(length=8)}@example.com",
            "first_name": "Delegated", "send_welcome_email": 0, "user_type": "System User",
            "roles": [{"role": "Sales User"}],
            "retail_sidebar_permissions": '{"version":1,"allowed":["workspace:sales","workspace:sales_invoices"]}'}).insert()
        self.assertEqual(user.retail_access_manager, self.users["customer"])
        self.assertIn("Manufacturing", [row.module for row in user.block_modules])
        self.assertEqual([row.role for row in user.roles], ["Sales User"])
        user.roles = []
        user.append("roles", {"role": "Stock User"})
        user.save()
        self.assertIn("Stock User", frappe.get_roles(user.name))

    def test_customer_cannot_expand_self_or_delegate_hidden_sidebar(self):
        frappe.set_user(self.users["customer"])
        own = frappe.get_doc("User", frappe.session.user)
        own.append("roles", {"role": "Accounts User"})
        with self.assertRaises(frappe.PermissionError):
            own.save(ignore_permissions=True)
        staff = frappe.get_doc("User", self.users["staff"])
        staff.retail_sidebar_permissions = '{"version":1,"allowed":["workspace:van_sales"]}'
        with self.assertRaises(frappe.PermissionError):
            staff.save(ignore_permissions=True)
        staff.reload()
        staff.retail_sidebar_permissions = None
        staff.save()
        from retail.sidebar_permissions import selection
        self.assertNotIn("workspace:van_sales", selection(staff.name))

    def test_customer_cannot_manage_unrelated_users(self):
        frappe.set_user(self.users["customer"])
        unrelated = self.users["legacy_manager"]
        self.assertNotIn(unrelated, frappe.get_list("User", pluck="name", limit_page_length=0))
        self.assertFalse(frappe.has_permission("User", "write", unrelated))
        doc = frappe.get_doc("User", unrelated)
        doc.first_name = "Unauthorized"
        with self.assertRaises(frappe.PermissionError):
            doc.save(ignore_permissions=True)

    def test_customer_cannot_forge_staff_ownership(self):
        frappe.set_user(self.users["customer"])
        for field, value in (("retail_access_manager", frappe.session.user), ("owner", frappe.session.user)):
            doc = frappe.get_doc("User", self.users["legacy_manager"])
            doc.set(field, value)
            with self.assertRaises(frappe.PermissionError):
                doc.save(ignore_permissions=True)

    def test_super_admin_reduction_cascades_to_staff(self):
        from retail.sidebar_permissions import selection
        parent = frappe.get_doc("User", self.users["customer"])
        parent.set("roles", [{"role": "Customer Administrator"}, {"role": "Stock User"}])
        parent.retail_sidebar_permissions = '{"version":1,"allowed":["workspace:settings","workspace:user_list"]}'
        parent.save()
        staff = frappe.get_doc("User", self.users["staff"])
        self.assertNotIn("Sales User", [row.role for row in staff.roles])
        self.assertNotIn("workspace:sales_invoices", selection(staff.name))

    def test_customer_own_profile_remains_editable(self):
        frappe.set_user(self.users["customer"])
        own = frappe.get_doc("User", frappe.session.user)
        own.first_name = "Personal profile update"
        own.save()
        self.assertEqual(frappe.db.get_value("User", own.name, "first_name"), "Personal profile update")

    def test_linking_existing_staff_applies_manager_ceiling(self):
        user = frappe.get_doc("User", self.users["legacy_manager"])
        user.retail_access_manager = self.users["customer"]
        user.save()
        self.assertNotIn("System Manager", frappe.get_roles(user.name))
        self.assertIn("Manufacturing", [row.module for row in user.block_modules])
        from retail.sidebar_permissions import selection
        self.assertNotIn("workspace:van_sales", selection(user.name))

    def test_customer_pos_profile_picker_request_and_validation(self):
        from frappe.desk.search import search_link
        from retail.pos_privileges import validate_profile_link
        customer = frappe.get_doc('User', self.users['customer'])
        customer.append('roles', {'role': 'POS Manager'})
        customer.retail_sidebar_permissions = None
        customer.save()
        profile = frappe.get_doc({'doctype': 'POS Operator Privilege',
            'profile_name': 'Picker Test ' + frappe.generate_hash(length=8)}).insert()
        frappe.set_user(customer.name)
        args = {'doctype': 'POS Operator Privilege', 'txt': profile.name,
                'query': 'retail.pos_privileges.available_profiles'}
        with patch.object(frappe.local, 'request', frappe._dict(path='/api/method/frappe.desk.search.search_link'), create=True), patch.object(frappe.local, 'form_dict', frappe._dict(args), create=True):
            access.guard_request()
            self.assertIn(profile.name, [row['value'] for row in search_link(**args)])
        args = {'doctype': 'POS Operator Privilege', 'docname': profile.name, 'fields': '[]'}
        with patch.object(frappe.local, 'request', frappe._dict(path='/api/method/frappe.client.validate_link'), create=True), patch.object(frappe.local, 'form_dict', frappe._dict(args), create=True):
            access.guard_request()
            self.assertEqual(validate_profile_link(**args), {'name': profile.name})
            with self.assertRaises(frappe.PermissionError):
                validate_profile_link(args['doctype'], profile.name, '["change_price"]')
        for command in ('frappe.client.get', 'frappe.client.set_value', 'frappe.desk.search.search_link'):
            with patch.object(frappe.local, 'request', frappe._dict(path='/api/method/' + command), create=True), patch.object(frappe.local, 'form_dict', frappe._dict(doctype='POS Operator Privilege'), create=True):
                with self.assertRaises(frappe.PermissionError):
                    access.guard_request()
        self.assertFalse(frappe.has_permission('POS Operator Privilege', 'create'))
        self.assertFalse(frappe.has_permission('POS Operator Privilege', 'write'))

    def test_customer_employee_automatic_permissions_are_scoped(self):
        customer = frappe.get_doc('User', self.users['customer'])
        company = frappe.db.get_value('Company', {}, 'name')
        frappe.get_doc({'doctype': 'Employee', 'first_name': 'Manager',
            'gender': 'Male', 'date_of_birth': '1990-01-01',
            'date_of_joining': '2026-01-01', 'company': company,
            'user_id': customer.name, 'create_user_permission': 0}).insert()
        customer.reload()
        customer.append_roles('HR Manager')
        customer.retail_sidebar_permissions = None
        customer.save()
        company = frappe.db.get_value('Company', {}, 'name')
        self.assertTrue(company)
        frappe.set_user(customer.name)
        employee = frappe.get_doc({
            'doctype': 'Employee', 'first_name': 'Scoped Staff',
            'gender': 'Male', 'date_of_birth': '1990-01-01',
            'date_of_joining': '2026-01-01', 'company': company,
            'status': 'Active', 'user_id': self.users['staff'],
            'create_user_permission': 1,
        })
        employee.insert()
        for allow, value in [('Employee', employee.name), ('Company', company)]:
            self.assertTrue(frappe.db.exists('User Permission', {
                'user': self.users['staff'], 'allow': allow, 'for_value': value}))
        direct = frappe.get_doc({'doctype': 'User Permission', 'user': self.users['staff'],
                                 'allow': 'Company', 'for_value': company})
        with self.assertRaises(frappe.PermissionError):
            direct.insert(ignore_permissions=True)
        employee.create_user_permission = 0
        employee.save()
        self.assertFalse(frappe.db.exists('User Permission', {
            'user': self.users['staff'], 'allow': 'Employee', 'for_value': employee.name}))
        employee.user_id = self.users['legacy_manager']
        employee.create_user_permission = 1
        with self.assertRaises(frappe.PermissionError):
            employee.save()
