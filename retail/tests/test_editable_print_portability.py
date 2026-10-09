"""Database-free checks for fresh-site setup and template portability."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from retail import editable_print_formats as formats


class TestEditablePrintPortability(unittest.TestCase):
    def test_mixed_labels_translate_and_upgrade_is_idempotent(self):
        source = '<style>.x { color: red; }</style><div>DELIVERY NOTE</div><div>Delivery Note# {{ doc.name }}</div>'
        result = formats.editable_html(source)
        self.assertIn('{{ _("Delivery Note") }}# {{ doc.name }}', result)
        self.assertIn('<style>.x { color: red; }</style>', result)
        self.assertEqual(formats.editable_html(result), result)

    def test_item_values_and_amount_words_use_print_language(self):
        source = '{{ item.item_name or item.item_code }} {{ item.description }} {{ item.uom or item.stock_uom }} {{ doc.in_words or "" }}'
        result = formats.editable_html(source)
        self.assertIn('_(item.item_name)', result)
        self.assertIn('_(item.description)', result)
        self.assertIn('_(item.uom or item.stock_uom)', result)
        self.assertIn('frappe.utils.money_in_words', result)
        self.assertIn('doc.is_rounded_total_disabled()', result)
        self.assertNotIn('doc.in_words', result)
        self.assertEqual(formats.editable_html(result), result)

    def test_legacy_letterhead_becomes_print_context(self):
        source = '{% set fixed_letterhead = frappe.db.get_value("Letter Head", "Arab Scale Letter Head - Standard", "content") %}'
        result = formats.editable_html(source)
        self.assertNotIn("Arab Scale", result)
        self.assertIn("letter_head if not no_letterhead", result)
        self.assertIn("footer and not no_letterhead", result)

    def test_original_company_bank_details_are_not_copied(self):
        source = '{% if doc.custom_customer_notes %}{{ doc.custom_customer_notes }}{% else %}Account Name: Arab Scale Trading LLC; IBAN: old-account{% endif %}'
        result = formats.editable_html(source)
        self.assertIn("{{ doc.custom_customer_notes }}", result)
        self.assertNotIn("Arab Scale", result)
        self.assertNotIn("old-account", result)

    def test_fresh_site_creates_editable_copy_and_default(self):
        target = SimpleNamespace(insert=Mock())
        with patch.object(formats, "frappe") as frappe, patch.object(formats, "make_property_setter") as setter, patch.dict(formats.SOURCES, {"Sales Invoice": "Sales Invoice - Copy"}, clear=True):
            frappe.db.exists.side_effect = lambda dt, name: name == "Sales Invoice - Copy"
            frappe.get_doc.return_value.html = "<div>Invoice</div>"
            frappe.copy_doc.return_value = target
            frappe.get_meta.return_value.default_print_format = None
            formats.ensure_editable_print_formats()
            self.assertEqual(target.name, "Sales Invoice - A4")
            self.assertEqual(target.standard, "No")
            self.assertEqual(target.custom_format, 1)
            target.insert.assert_called_once_with(ignore_permissions=True)
            setter.assert_called_once()

    def test_existing_ui_copy_and_chosen_default_are_preserved(self):
        with patch.object(formats, "frappe") as frappe, patch.object(formats, "make_property_setter") as setter, patch.dict(formats.SOURCES, {"Sales Invoice": "Sales Invoice - Copy"}, clear=True):
            frappe.db.exists.return_value = True
            frappe.get_doc.return_value.html = "<div>My Company</div>"
            frappe.get_meta.return_value.default_print_format = "My Company Invoice"
            formats.ensure_editable_print_formats()
            frappe.copy_doc.assert_not_called()
            self.assertIn("My Company", frappe.get_doc.return_value.html)
            setter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
