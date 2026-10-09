import unittest
from unittest.mock import MagicMock, patch

import frappe
from retail.domains.item import packing_sync, item_price_sync


class Item(frappe._dict):
	def set(self, key, value):
		self[key] = value

	def append(self, key, value):
		self.setdefault(key, []).append(frappe._dict(value))


class TestPackingUoms(unittest.TestCase):
	def setUp(self):
		self.db = MagicMock()
		self.db.exists.return_value = True
		self.db_patch = patch.object(frappe, "db", self.db)
		self.db_patch.start()
		self.addCleanup(self.db_patch.stop)
		self.throw_patch = patch.object(frappe, "throw", side_effect=ValueError)
		self.throw_patch.start()
		self.addCleanup(self.throw_patch.stop)

	def item(self):
		return Item(item_code="TEST", stock_uom="Nos", uoms=[frappe._dict(uom="Box", conversion_factor=21)],
			custom_retail_packing_detail=[frappe._dict(uom="Box", conversion_factor=n,
				barcode=str(n), selling_rate=n*10, purchase_rate=n*5) for n in [21, 50, 100]])

	def test_mapping_is_idempotent_and_prices_use_exact_uom(self):
		doc = self.item()
		for _ in range(2):
			packing_sync.sync_uoms_and_barcodes(doc)
			self.assertEqual([r.uom for r in doc.custom_retail_packing_detail], ["Box-21", "Box-50", "Box-100"])
			self.assertEqual([r.packing_uom for r in doc.custom_retail_packing_detail], ["Box"]*3)
			self.assertEqual({r.uom: r.conversion_factor for r in doc.uoms},
				{"Nos": 1, "Box": 21, "Box-21": 21, "Box-50": 50, "Box-100": 100})
			self.assertEqual([r.uom for r in doc.barcodes], ["Box-21", "Box-50", "Box-100"])
		with patch.object(item_price_sync, "sync_item_price") as sync:
			item_price_sync.sync_packing_item_prices(doc)
			self.assertEqual([c.kwargs['uom'] for c in sync.call_args_list],
				["Box-21", "Box-21", "Box-50", "Box-50", "Box-100", "Box-100"])

	def test_reuse_qualified_uom_and_factor_change(self):
		doc = self.item()
		doc.custom_retail_packing_detail[0].uom = "Box-21"
		packing_sync.sync_uoms_and_barcodes(doc)
		doc.custom_retail_packing_detail[0].conversion_factor = 22
		packing_sync.sync_uoms_and_barcodes(doc)
		self.assertEqual(doc.custom_retail_packing_detail[0].uom, "Box-22")
		self.assertIn("Box-21", [r.uom for r in doc.uoms])

	def test_conflicts_and_invalid_factors_fail_safely(self):
		for factor in [0, -1, None, float('nan'), 50]:
			doc = self.item()
			doc.custom_retail_packing_detail[0].conversion_factor = factor
			with self.subTest(factor=factor), self.assertRaises(ValueError):
				packing_sync.sync_uoms_and_barcodes(doc)
		doc = self.item()
		doc.uoms.append(frappe._dict(uom="Box-21", conversion_factor=50))
		with self.assertRaises(ValueError):
			packing_sync.sync_uoms_and_barcodes(doc)

	def test_missing_uom_is_created_once(self):
		doc = self.item()
		known = set()
		self.db.exists.side_effect = lambda dt, name: name in known
		with patch.object(frappe, "get_doc") as get_doc:
			get_doc.side_effect = lambda values: (known.add(values['uom_name']) or MagicMock())
			packing_sync.sync_uoms_and_barcodes(doc)
			packing_sync.sync_uoms_and_barcodes(doc)
			self.assertEqual(get_doc.call_count, 3)

	def test_standard_conversion_conflict_is_rejected(self):
		doc = self.item()
		packing_sync.sync_uoms_and_barcodes(doc)
		packing_sync.validate_packing_uoms(doc)
		next(row for row in doc.uoms if row.uom == "Box-21").conversion_factor = 99
		with self.assertRaises(ValueError):
			packing_sync.validate_packing_uoms(doc)
