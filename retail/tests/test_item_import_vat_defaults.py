import unittest
from unittest.mock import Mock, patch
import frappe
from retail.domains.item import vat_pricing as vat

class DefaultsTest(unittest.TestCase):
 def apply(self, fields, values=None, new=True):
  doc=Mock(); doc.is_new.return_value=new; doc.flags={'updater_reference':{'doctype':'Data Import','docname':'import'}}
  doc.meta.has_field.return_value=True
  with patch.object(vat,'get_item_import_fields',return_value=set(fields)), patch.object(vat,'get_company_item_vat_defaults',return_value={'custom_tax':'VAT','custom_sales_rate_includes_vat':1}):
   vat.apply_new_item_vat_defaults(doc)
  return dict(call.args for call in doc.set.call_args_list)
 def test_omitted_columns(self):
  self.assertEqual(self.apply([]),{'custom_tax':'VAT','custom_sales_rate_includes_vat':1})
 def test_explicit_zero_and_template_preserved(self):
  self.assertEqual(self.apply(['custom_tax','custom_sales_rate_includes_vat']),{})
 def test_updates_untouched(self):
  self.assertEqual(self.apply([],new=False),{})
if __name__ == "__main__":
 unittest.main()
