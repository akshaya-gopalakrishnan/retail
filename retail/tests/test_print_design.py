import unittest
from retail.print_design import compact_header

class TestPrintDesign(unittest.TestCase):
    def test_preserves_dynamic_title_number_and_content(self):
        html = '<table class="document-heading-table"><tr><td><h1 class="document-title">{{ title }}</h1><div class="document-number">{{ doc.name }}</div></td></tr></table><div>Saved content</div>'
        result, css = compact_header(html, '.custom { color: red; }')
        self.assertIn('{{ title }}', result)
        self.assertIn('{{ doc.name }}', result)
        self.assertIn('<div>Saved content</div>', result)
        self.assertIn('retail-title-rule', result)
        self.assertIn('.custom { color: red; }', css)
        self.assertEqual(compact_header(result, css), (result, css))
