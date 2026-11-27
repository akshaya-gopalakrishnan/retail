from io import BytesIO
from pathlib import Path
import unittest
from pypdf import PdfReader, PdfWriter
from retail.document_print_layout import paginate_items, numbered_pdf, DELIVERY_CSS


class TestDocumentPrintLayout(unittest.TestCase):
    def test_pagination_preserves_saved_cells_and_is_idempotent(self):
        source = '<div>My letterhead</div><table class="item-table"><thead><tr><th>My column</th></tr></thead><tbody>{% for item in doc.items %}<tr><td>{{ item.item_name }}</td></tr>{% endfor %}</tbody></table><div>My terms</div>'
        html, css = paginate_items(source, '.custom {color:red}')
        self.assertIn('loop.index % 22 == 0 and not loop.last', html)
        self.assertIn('My letterhead', html)
        self.assertIn('My terms', html)
        self.assertEqual(html.count('<th>My column</th>'), 2)
        self.assertEqual(html.count('{{ item.item_name }}'), 1)
        self.assertEqual(paginate_items(html, css), (html, css))

    def test_numbered_pdf_uses_actual_page_count_and_leaves_single_page_untouched(self):
        for count in [1, 2, 3]:
            writer = PdfWriter()
            for _ in range(count):
                writer.add_blank_page(width=595, height=842)
            stream = BytesIO()
            writer.write(stream)
            original = stream.getvalue()
            result = numbered_pdf(original)
            if count == 1:
                self.assertEqual(result, original)
            else:
                pages = PdfReader(BytesIO(result)).pages
                for i, page in enumerate(pages, 1):
                    self.assertIn(f'Page {i} of {count}', page.extract_text())

    def test_shipped_templates_contain_single_item_loop_and_break_boundary(self):
        root = Path(__file__).parents[1] / 'templates' / 'editable_print_formats'
        for slug in ['sales_invoice', 'delivery_note']:
            source = (root / (slug + '.html')).read_text()
            self.assertEqual(source.count('{% for item in doc.items %}'), 1)
            self.assertEqual(source.count('loop.index % 22 == 0 and not loop.last'), 1)
        self.assertNotIn('width:', DELIVERY_CSS)

    def test_encrypted_multipage_pdf_keeps_password(self):
        writer = PdfWriter()
        for _ in range(2):
            writer.add_blank_page(width=595, height=842)
        writer.encrypt('test-password')
        stream = BytesIO()
        writer.write(stream)
        reader = PdfReader(BytesIO(numbered_pdf(stream.getvalue(), password='test-password')))
        self.assertTrue(reader.is_encrypted)
        self.assertTrue(reader.decrypt('test-password'))
        self.assertIn('Page 2 of 2', reader.pages[1].extract_text())

    def test_delivery_headers_start_with_serial_and_item_name_without_image_column(self):
        from retail.document_print_layout import document_header
        source = '<table><thead><tr><th class="col-number">#</th><th class="col-image"></th><th class="col-description">Item Description</th><th>Qty</th></tr></thead><tbody><tr><td class="col-image"><img src="example"></td><td class="col-description">{{ item.item_name }}</td></tr></tbody></table>'
        html, css = document_header(source, '', 'Delivery Note')
        self.assertNotIn('col-image', html)
        self.assertIn('<th class="col-number">{{ _("Sr No") }}</th><th class="col-description">{{ _("Item Name") }}</th>', html)
        self.assertIn('{{ item.item_name }}', html)
        self.assertIn('background: #fff !important', css)
        self.assertEqual(document_header(html, css, 'Delivery Note'), (html, css))

    def test_delivery_quantity_and_uom_are_inline_and_item_id_is_removed(self):
        from retail.document_print_layout import delivery_design
        source = '{% if item.item_code %}<div class="item-code">{{ item.item_code }}</div>{% endif %}<td class="col-qty"><div class="quantity-value">{{ item.qty }}</div> <div class="quantity-uom">{{ item.uom }}</div></td>'
        html, css = delivery_design(source, '')
        self.assertNotIn('item-code', html)
        self.assertNotIn('{{ item.item_code }}', html)
        self.assertIn('<span class="quantity-value">{{ item.qty }}</span>', html)
        self.assertIn('<span class="quantity-uom">{{ item.uom }}</span>', html)
        self.assertIn('white-space: nowrap', css)
        self.assertEqual(delivery_design(html, css), (html, css))

    def test_delivery_signatures_are_moved_into_pdf_footer_once(self):
        from retail.document_print_layout import delivery_footer
        source = '<div class="delivery-note-container"><table class="item-table">ITEMS</table><div class="signature-section"><table><tr><td>Date, Signature, Receiver, Phone, Stamp</td></tr></table></div></div>{% if footer and not no_letterhead %}<div>{{ footer }}</div>{% endif %}'
        html, css = delivery_footer(source, '')
        self.assertEqual(html.count('signature-section'), 1)
        self.assertLess(html.index('id="footer-html"'), html.index('signature-section'))
        self.assertIn('Date, Signature, Receiver, Phone, Stamp', html)
        self.assertEqual(html.count('{{ footer }}'), 1)
        self.assertEqual(delivery_footer(html, css), (html, css))
