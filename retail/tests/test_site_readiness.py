"""Database-free regression coverage for partial-install recovery boundaries."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from retail import accounting_defaults as defaults
from retail import site_readiness as ready


class TestSiteReadiness(unittest.TestCase):
    def account(self, **values):
        data = dict(name="cheques", account_name="Post Dated Cheques Received",
                    company="ALY", root_type="Asset", account_type="Receivable",
                    account_currency="AED", is_group=0, disabled=0)
        data.update(values)
        return SimpleNamespace(**data)

    def test_uae_cheque_receivable_supported_without_retyping_account(self):
        company = SimpleNamespace(name="ALY", default_currency="AED")
        spec = defaults.PAYMENT_ACCOUNT_SPECS["Cheque"]
        self.assertTrue(ready._usable(self.account(), company, spec))
        with patch.object(frappe, "db", Mock()) as db:
            db.get_value.return_value = frappe._dict(vars(self.account()))
            self.assertTrue(defaults._valid_account("cheques", company, spec))
            db.set_value.assert_not_called()
        self.assertFalse(ready._usable(self.account(), company, defaults.PAYMENT_ACCOUNT_SPECS["Card"]))

    def test_account_resolution_never_crosses_company_or_uses_disabled_group(self):
        company = SimpleNamespace(name="ALY", default_currency="AED")
        spec = defaults.PAYMENT_ACCOUNT_SPECS["Cheque"]
        for overrides in ({"company": "OTHER"}, {"disabled": 1}, {"is_group": 1}, {"account_currency": "USD"}):
            self.assertIsNone(ready._candidate([self.account(**overrides)], company, spec, spec[3]))
        self.assertIsNone(ready._candidate([self.account(), self.account(name="duplicate")], company, spec, spec[3]))

    def test_native_uae_cheque_selected_instead_of_conflicting_creation(self):
        company = SimpleNamespace(name="ALY", default_currency="AED")
        with patch.object(frappe, "get_all", return_value=[frappe._dict(name="cheques", account_name="Post Dated Cheques Received")]) as query, patch.object(defaults, "_create_account") as create:
            self.assertEqual(defaults._resolve_account(company, defaults.PAYMENT_ACCOUNT_SPECS["Cheque"]), "cheques")
            self.assertEqual(query.call_args.kwargs["filters"]["account_type"], ["in", ["Bank", "Receivable"]])
            create.assert_not_called()

    def test_schema_install_is_additive_and_repeatable(self):
        definitions = ready.definitions()
        self.assertEqual(sum(map(len, definitions.values())), 21)
        with patch.object(frappe, "get_meta", return_value=Mock(has_field=Mock(return_value=True))), patch("frappe.custom.doctype.custom_field.custom_field.create_custom_fields") as create:
            ready.install_schema()
            create.assert_not_called()
        with patch.object(frappe, "get_meta", return_value=Mock(has_field=Mock(return_value=False))), patch("frappe.custom.doctype.custom_field.custom_field.create_custom_fields") as create:
            ready.install_schema()
            self.assertFalse(create.call_args.kwargs["update"])
            self.assertEqual(sum(map(len, create.call_args.args[0].values())), 21)

    def test_gate_detects_missing_database_even_with_metadata(self):
        with patch.object(frappe, "get_meta", return_value=Mock(get_field=Mock(return_value=SimpleNamespace(fieldtype="Data")))) , patch.object(frappe, "db", Mock()) as db:
            db.get_table_columns.return_value = []
            self.assertEqual(len(ready.validate_schema()), 21)

    def test_stale_or_blocked_plan_never_changes_schema(self):
        for report in ({"review_token": "new", "blockers": []}, {"review_token": "old", "blockers": ["ambiguous"]}):
            with patch.object(frappe, "only_for"), patch.object(ready, "plan", return_value=report), patch.object(ready, "install_schema") as install:
                with self.assertRaises(RuntimeError):
                    ready.apply("ALY", "old")
                install.assert_not_called()

    def test_global_vat_defaults_not_guessed_for_multiple_companies(self):
        with patch.object(frappe, "get_all", return_value=["ALY", "OTHER"]), patch("frappe.custom.doctype.property_setter.property_setter.make_property_setter") as setter:
            ready.initialize_item_defaults()
            setter.assert_not_called()

    def test_recovery_plan_fills_blanks_but_preserves_company_choices(self):
        company = frappe._dict(name="ALY", default_currency="AED", cost_center="Main - ALY", round_off_cost_center="Main - ALY")
        accounts = []
        for field, spec in defaults.DEFAULTS.items():
            label = ready.ALIASES.get(field, spec[3])[0]
            account = self.account(name=field, account_name=label, root_type=spec[1], account_type=spec[2])
            accounts.append(account)
            company[field] = field
        company.default_income_account = None
        company.as_dict = lambda: {k: v for k, v in company.items() if k != "as_dict"}
        template = SimpleNamespace(taxes=[SimpleNamespace(tax_rate=5)])
        field = SimpleNamespace(reqd=0, default="my-existing-vat")
        def get_all(dt, **kwargs):
            if dt == "Account":
                return accounts
            if dt == "Item Tax Template":
                return ["my-existing-vat"]
            return []
        def get_doc(dt, name):
            return company if dt == "Company" else template
        with patch.object(frappe, "get_all", side_effect=get_all), patch.object(frappe, "get_doc", side_effect=get_doc), patch.object(frappe, "get_meta", return_value=Mock(get_field=Mock(return_value=field))), patch.object(frappe, "db", Mock()) as db, patch.object(ready, "validate_schema", return_value=[]), patch.object(frappe, "local", SimpleNamespace(site="retail-test.localhost")):
            db.exists.side_effect = lambda dt, name: dt == "Item Tax Template"
            report = ready.plan("ALY")
        company_changes = [c for c in report["changes"] if c["doctype"] == "Company"]
        self.assertEqual(company_changes, [{"doctype": "Company", "name": "ALY", "field": "default_income_account", "value": "default_income_account"}])
        self.assertFalse([c for c in report["changes"] if c["doctype"] == "Item setting"])
        self.assertFalse(report["blockers"])

    def test_new_site_and_upgrade_have_additive_schema_gate(self):
        from retail import hooks
        self.assertIn("retail.site_readiness.install_schema", hooks.after_sync)
        self.assertIn("retail.site_readiness.install_schema", hooks.after_migrate)
        self.assertIn("retail.domains.item.naming.install_item_code_defaults", hooks.after_sync)
