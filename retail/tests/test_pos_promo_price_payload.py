import json
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retail.api import pos_sync


class TestPOSPromoPricePayload(unittest.TestCase):
	def setUp(self):
		additional = patch.object(pos_sync, "_additional_pos_promotions", return_value={})
		additional.start()
		self.addCleanup(additional.stop)

	def document(self, **row_values):
		row = dict(name="ROW", idx=1, item="ITEM", item_group="", barcode="BARCODE",
			qty=1, uom="Nos", price_list="Standard Selling", current_price=9.52,
			current_price_including_tax=10, purchase_price=4.76, purchase_price_including_tax=5,
			vat_rate=5, promo_price=0, promo_price_including_tax=0,
			discount_percent=10, discount_amount=1, discount_input="Amount", max_qty=5)
		row.update(row_values)
		return frappe.get_doc(dict(doctype="Promo Price", name="OFFER", description="OFFER",
			disabled=1, active_from="2026-10-14", active_to="2026-10-31", company="COMPANY",
			warehouse="WAREHOUSE", min_qty=1, max_qty=10, min_sales_value=100, priority="2",
			notes="Notes", products=[row], linked_schemes=[{"promotional_scheme":"INTERNAL"}]))

	def payload(self, doc):
		counter = frappe._dict(branch="BRANCH", name="COUNTER", counter_code="C001")
		with patch.object(pos_sync, "_pos_promotion_payload", return_value=({}, counter, "CURSOR")) as gate, patch.object(pos_sync, "_get_promotion_docs", return_value=[doc]) as lookup:
			result = pos_sync.get_pos_promo_prices(branch="BRANCH", counter_code="C001", modified_after="CURSOR")
		gate.assert_called_once_with("BRANCH", "C001", "CURSOR")
		lookup.assert_called_once_with("Promo Price", counter, "CURSOR")
		return result["promotions"][0]

	def test_every_form_field_and_parent_detail_is_exported(self):
		doc = self.document()
		result = self.payload(doc)
		row = result["products"][0]
		schema = json.loads((Path(__file__).parents[1] / "retail_app/doctype/promo_price_item/promo_price_item.json").read_text())
		self.assertTrue({field["fieldname"] for field in schema["fields"]}.issubset(row))
		for field in ("disabled", "active_from", "active_to", "company", "warehouse", "min_qty", "max_qty", "min_sales_value", "priority", "notes"):
			self.assertEqual(result[field], doc.get(field))
		self.assertNotIn("linked_schemes", result)
		self.assertEqual((row["discount_amount"],row["discount_input"]),(1,"Amount"))
		self.assertEqual((row["purchase_price"],row["purchase_price_including_tax"]),(4.76,5))
		self.assertEqual((row["calculated_promo_price"],row["calculated_promo_price_including_tax"]),(8.57,9))
		self.assertEqual((row["promo_price"],row["promo_price_including_tax"]),(0,0))
		self.assertEqual(doc.products[0].promo_price,0)
	def test_item_tracking_preserves_packing_barcode_and_scopes_serials(self):
		rows = [dict(item="ITEM", barcode="PACK"), dict(item="ITEM", barcode=""),
			dict(item="", barcode=""), dict(item="PLAIN", barcode="")]
		items = [frappe._dict(item_code="ITEM", barcode="BASE", has_serial_no=1, disabled=0),
			frappe._dict(item_code="PLAIN", barcode="PLAIN-BC", has_serial_no=0, disabled=0)]
		with patch.object(frappe, "get_all", side_effect=[items,
			[frappe._dict(item_code="ITEM", name="SERIAL-1")]]) as query:
			pos_sync.with_item_identity([{"products": rows}], "WAREHOUSE")
		self.assertEqual([row["barcode"] for row in rows], ["PACK", "BASE", "", "PLAIN-BC"])
		self.assertEqual([row["serial_numbers"] for row in rows], [["SERIAL-1"], ["SERIAL-1"], [], []])
		self.assertEqual([row["has_serial_no"] for row in rows], [1, 1, 0, 0])
		self.assertEqual(query.call_args.kwargs["filters"],
			{"item_code": ["in", ["ITEM"]], "warehouse": "WAREHOUSE", "status": "Active"})
		with patch.object(frappe, "get_all", side_effect=[items, []]):
			pos_sync.with_item_identity([{"products": rows}], "WAREHOUSE")
		self.assertEqual(rows[0]["serial_numbers"], [])

	def test_legacy_percentage_offer_gets_amount_without_mutation(self):
		doc = self.document(discount_amount=None, discount_input=None)
		row = self.payload(doc)["products"][0]
		self.assertEqual((row["discount_amount"],row["discount_input"]),(1,"Percent"))
		self.assertIsNone(doc.products[0].discount_amount)
		self.assertIsNone(doc.products[0].discount_input)

	def test_fixed_price_offer_retains_existing_rate_fields(self):
		row = self.payload(self.document(discount_percent=0, discount_amount=0, discount_input="", promo_price=8, promo_price_including_tax=8.4))["products"][0]
		self.assertEqual((row["promo_price"],row["promo_price_including_tax"]),(8,8.4))
		self.assertEqual((row["calculated_promo_price"],row["calculated_promo_price_including_tax"]),(8,8.4))

	def test_free_group_zero_vat_and_quantity_previews(self):
		for changes, expected in (
			({"discount_percent":100,"discount_amount":10},(0,0)),
			({"item":"","item_group":"GROUP","current_price":0,"current_price_including_tax":0,"discount_input":"Percent"},(0,0)),
			({"vat_rate":0,"current_price":10,"current_price_including_tax":10},(9,9)),
			({"qty":2,"current_price":19.04,"current_price_including_tax":20,"discount_input":"Percent"},(17.14,18)),
		):
			with self.subTest(changes=changes):
				row=self.payload(self.document(**changes))["products"][0]
				self.assertEqual((row["calculated_promo_price"],row["calculated_promo_price_including_tax"]),expected)

	def test_new_numeric_fields_never_return_null(self):
		row=self.payload(self.document(purchase_price=None,purchase_price_including_tax=None,discount_amount=None,discount_input=None,discount_percent=0,promo_price=None,promo_price_including_tax=None))["products"][0]
		for field in ("purchase_price","purchase_price_including_tax","discount_amount","calculated_promo_price","calculated_promo_price_including_tax"):
			self.assertEqual(row[field],0)
			self.assertIsInstance(row[field],(int,float))

	def test_scope_disabled_records_and_incremental_filters_are_preserved(self):
		counter=frappe._dict(company="COMPANY",warehouse="WAREHOUSE")
		docs={"global":frappe._dict(company="",warehouse="",disabled=1),
			"matched":frappe._dict(company="COMPANY",warehouse="WAREHOUSE"),
			"other_company":frappe._dict(company="OTHER",warehouse="WAREHOUSE"),
			"other_warehouse":frappe._dict(company="COMPANY",warehouse="OTHER")}
		with patch.object(pos_sync.frappe,"get_all",return_value=list(docs)) as names, patch.object(pos_sync.frappe,"get_doc",side_effect=lambda dt,name:docs[name]):
			self.assertEqual(pos_sync._get_promotion_docs("Promo Price",counter),[docs["global"],docs["matched"]])
			self.assertEqual(names.call_args.kwargs["filters"],[])
			pos_sync._get_promotion_docs("Promo Price",counter,"2026-10-14 00:00:00")
			self.assertEqual(names.call_args.kwargs["filters"],[["modified",">","2026-10-14 00:00:00"]])
