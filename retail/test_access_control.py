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
        cls.users = {}
        cls.module_profile = frappe.get_doc({"doctype": "Module Profile", "module_profile_name": "Access Test " + frappe.generate_hash(length=8)}).insert().name
        cls.gravatar = patch("frappe.core.doctype.user.user.update_gravatar")
        cls.gravatar.start()
        for label, roles in {
            "super": ["Super Admin", "System Manager"],
            "customer": ["Customer Administrator"],
            "legacy_manager": ["System Manager"],
            "staff": ["Sales User"],
        }.items():
            user = frappe.get_doc({
                "doctype": "User", "email": f"access-{label}-{frappe.generate_hash(length=8)}@example.com",
                "first_name": f"Access Test {label}", "send_welcome_email": 0,
                "user_type": "System User", "roles": [{"role": role} for role in roles],
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

    def test_customer_cannot_assign_roles_profiles_or_modules_even_ignoring_permissions(self):
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
        for dt, name in (("Role Profile", "Administrator"), ("Role", "Employee"), ("System Settings", "System Settings")):
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
            ("/backups/private-database.sql.gz", {}),
            ("/api/method/frappe.utils.backups.get_backup_encryption_key", {}),
            ("/api/method/frappe.desk.doctype.system_console.system_console.execute_code", {}),
            ("/api/method/run_doc_method", {"docs": '{"doctype": "System Console"}'}),
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
