import unittest
from retail.print_item_tax import item_tax_for_print

class TestPrintItemTax(unittest.TestCase):
    def test_saved_breakup_foreign_currency_and_duplicate_items(self):
        items = [dict(item_code='A', net_amount=100), dict(item_code='A', net_amount=200)]
        doc = dict(items=items, conversion_rate=2, taxes=[dict(charge_type='On Net Total', rate=5, item_wise_tax_detail='{"A": [5, 30]}')])
        self.assertEqual(item_tax_for_print(doc, items[0]), dict(rate=5, amount=5))
        self.assertEqual(item_tax_for_print(doc, items[1]), dict(rate=5, amount=10))

    def test_exempt_row_and_valuation_exclusion(self):
        items = [dict(item_code='A', net_amount=100, item_tax_rate='{"VAT": 0}'), dict(item_code='A', net_amount=100)]
        doc = dict(items=items, taxes=[dict(account_head='VAT', charge_type='On Net Total', rate=5, item_wise_tax_detail={'A': [5, 5]}),dict(category='Valuation',item_wise_tax_detail={'A':[20,40]})])
        self.assertEqual(item_tax_for_print(doc,items[0]),dict(rate=0,amount=0))
        self.assertEqual(item_tax_for_print(doc,items[1]),dict(rate=5,amount=5))

    def test_no_breakup_does_not_invent_tax(self):
        item=dict(item_code='A', net_amount=100)
        self.assertEqual(item_tax_for_print(dict(items=[item],taxes=[]),item),dict(rate=0,amount=0))
