"""Company-owned VAT defaults must not depend on template name or abbreviation."""
import unittest
from unittest.mock import Mock, patch
import frappe
from retail.domains.item import vat_pricing as vat


class TestCompanyItemVatInitialization(unittest.TestCase):
    def run_initializer(self, company, templates):
        db = Mock()
        def get_doc(dt, name):
            return company if dt == 'Company' else frappe._dict(taxes=[frappe._dict(tax_rate=r) for r in templates[name]])
        with patch.object(frappe, 'db', db), patch.object(frappe, 'get_meta', return_value=Mock(has_field=Mock(return_value=True))), patch.object(frappe, 'get_doc', side_effect=get_doc), patch.object(frappe, 'get_all', return_value=list(templates)) as query:
            vat.initialize_company_item_vat_defaults(company=company.name)
        return db, query

    def test_each_company_uses_its_own_enabled_five_percent_template(self):
        for company_name, template_name in [('Shop One', 'Local VAT - ABC'), ('Shop Two', 'Tax Five - XYZ')]:
            company = frappe._dict(name=company_name)
            db, query = self.run_initializer(company, {'Zero': [0], template_name: [5], 'Other rate': [10]})
            self.assertEqual(query.call_args.kwargs['filters'], {'company': company_name, 'disabled': 0})
            values = db.set_value.call_args.args[2]
            self.assertEqual(values['custom_default_purchase_vat_template'], template_name)
            self.assertEqual(values['custom_default_sales_vat_template'], template_name)
            self.assertEqual(values['custom_item_vat_defaults_initialized'], 1)
            self.assertEqual(db.set_value.call_args.args[0], 'Company')

    def test_deliberately_cleared_defaults_are_never_refilled(self):
        company = frappe._dict(name='Shop', custom_item_vat_defaults_initialized=1)
        db, query = self.run_initializer(company, {'VAT': [5]})
        db.set_value.assert_not_called()
        query.assert_not_called()

    def test_setup_can_retry_when_company_template_is_created_later(self):
        company = frappe._dict(name='Shop')
        db, _ = self.run_initializer(company, {})
        db.set_value.assert_not_called()
        db, _ = self.run_initializer(company, {'Delayed local template': [5]})
        self.assertEqual(db.set_value.call_args.args[2]['custom_default_purchase_vat_template'], 'Delayed local template')

    def test_existing_explicit_selection_is_preserved_during_initialization(self):
        company = frappe._dict(name='Shop', custom_default_purchase_vat_template='Chosen zero VAT')
        db, _ = self.run_initializer(company, {'Local five': [5]})
        self.assertNotIn('custom_default_purchase_vat_template', db.set_value.call_args.args[2])
        self.assertEqual(db.set_value.call_args.args[2]['custom_default_sales_vat_template'], 'Local five')
