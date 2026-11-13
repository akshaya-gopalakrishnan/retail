"""Automatic Item naming must survive ERPNext's company setup defaults."""

import unittest
from unittest.mock import Mock, patch

from erpnext.utilities.naming import set_by_naming_series

from retail import hooks
from retail.domains.item import naming


class TestItemNamingSetup(unittest.TestCase):
	def test_wizard_manual_code_settings_are_restored_without_resetting_series(self):
		properties = {}
		settings = {"item_naming_by": "Item Code"}
		defaults = {"item_naming_by": "Item Code"}
		db = Mock()
		db.exists.side_effect = lambda dt, name: name in properties
		db.set_single_value.side_effect = lambda dt, key, value: settings.update({key: value})
		db.set_default.side_effect = lambda key, value: defaults.update({key: value})
		db.set_value.side_effect = lambda dt, name, key, value, **kwargs: properties.update({name: value})

		def setter(dt, field, prop, value, kind, **kwargs):
			properties[f"{dt}-{field or 'main'}-{prop}"] = str(value)

		with (
			patch.object(naming.frappe, "db", db),
			patch.object(naming.frappe, "clear_cache"),
			patch("frappe.custom.doctype.property_setter.property_setter.make_property_setter", setter),
			patch.object(naming, "make_property_setter", setter),
		):
			# This is the native helper called when the wizard saves Item Code mode.
			set_by_naming_series("Item", "item_code", False, make_mandatory=0)
			self.assertEqual(properties["Item-item_code-reqd"], "1")
			db.reset_mock()
			naming.after_setup_wizard({"company_name": "New Company"})
			first = dict(properties)
			naming.after_setup_wizard({"company_name": "New Company"})
			self.assertEqual(properties, first)
			db.sql.assert_not_called()

		self.assertEqual(settings["item_naming_by"], "Naming Series")
		self.assertEqual(defaults["item_naming_by"], "Naming Series")
		self.assertEqual(properties["Item-item_code-reqd"], "0")
		self.assertEqual(properties["Item-item_code-read_only"], "1")
		self.assertEqual(properties["Item-item_name-reqd"], "1")
		self.assertEqual(properties["Item-naming_series-options"], "I-.#")
		self.assertEqual(properties["Item-naming_series-hidden"], "1")

	def test_setup_success_registers_the_repair(self):
		self.assertEqual(hooks.setup_wizard_success, "retail.domains.item.naming.after_setup_wizard")
