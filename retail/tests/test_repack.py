"""Database-free cost regressions; never save hosted business records."""
import unittest
from unittest.mock import patch

import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from retail.repack import RetailStockEntry, GROUP, _group_items, _signature


def row(**values):
    result = frappe._dict(values)
    result.precision = lambda field: 2
    return result


def entry():
    doc = object.__new__(RetailStockEntry)
    doc.__dict__.update(dict(
        doctype="Stock Entry", purpose="Repack", custom_multiple_boms=1,
        from_warehouse="Raw", to_warehouse="Finished", custom_repack_boms=[
            row(idx=1, bom_no="BOM-A", finished_item="Pack A", qty=10, packing_cost=2.5),
            row(idx=2, bom_no="BOM-B", finished_item="Pack B", qty=20, packing_cost=5),
        ], items=[
            row(item_code="Bulk", qty=2, transfer_qty=2, conversion_factor=1,
                s_warehouse="Raw", basic_rate=10, basic_amount=20, **{GROUP:1}),
            row(item_code="Pack A", qty=10, transfer_qty=10, conversion_factor=1,
                t_warehouse="Finished", bom_no="BOM-A", **{GROUP:1}),
            row(item_code="Bulk", qty=3, transfer_qty=3, conversion_factor=1,
                s_warehouse="Raw", basic_rate=10, basic_amount=30, **{GROUP:2}),
            row(item_code="Pack B", qty=20, transfer_qty=20, conversion_factor=1,
                t_warehouse="Finished", bom_no="BOM-B", **{GROUP:2}),
        ], additional_costs=[
            row(base_amount=2.5, **{GROUP:1}), row(base_amount=5, **{GROUP:2}),
        ]))
    return doc


class TestRepackCosts(unittest.TestCase):
    def setUp(self):
        for stub in (
            patch("retail.repack._", side_effect=lambda text: text),
            patch.object(frappe, "get_system_settings", return_value="Banker's Rounding"),
            patch.object(frappe.local, "flags", frappe._dict(in_test=False), create=True),
        ):
            stub.start()
            self.addCleanup(stub.stop)

    def calculate(self, doc, reset=False):
        # Source valuation is provided by the native ledger. Everything after
        # that, including StockEntry's amount/valuation/totals methods, is real.
        def outgoing(self, *args):
            for r in self.items:
                if r.s_warehouse:
                    r.basic_amount = r.basic_rate * r.transfer_qty
            return sum(r.basic_amount for r in self.items if r.s_warehouse)
        with patch.object(StockEntry, "set_rate_for_outgoing_items", outgoing), patch(
            "erpnext.stock.doctype.stock_entry.stock_entry.init_landed_taxes_and_totals"
        ):
            doc.calculate_rate_and_amount(reset_outgoing_rate=reset)

    def test_packing_cost_stays_with_its_bom_and_source_rate_is_unchanged(self):
        doc = entry()
        self.calculate(doc)
        a, b = doc.items[1], doc.items[3]
        self.assertEqual((a.basic_amount, a.additional_cost, a.valuation_rate), (20, 2.5, 2.25))
        self.assertEqual((b.basic_amount, b.additional_cost, b.valuation_rate), (30, 5, 1.75))
        self.assertEqual([r.basic_rate for r in (doc.items[0], doc.items[2])], [10, 10])
        self.assertEqual(doc.total_incoming_value, 57.5)
        self.assertEqual(doc.total_outgoing_value, 50)
        self.assertEqual(doc.value_difference, doc.total_additional_costs)

    def test_reposting_recalculates_only_the_affected_material_group(self):
        doc = entry()
        self.calculate(doc)
        doc.items[0].basic_rate = 15
        self.calculate(doc)
        self.assertEqual(doc.items[1].valuation_rate, 3.25)
        self.assertEqual(doc.items[3].valuation_rate, 1.75)
        self.assertEqual(doc.total_incoming_value, 67.5)

    def test_common_additional_cost_retains_native_value_proportion(self):
        doc = entry()
        doc.additional_costs.append(row(base_amount=10))
        self.calculate(doc)
        self.assertEqual(doc.items[1].additional_cost, 6.5)
        self.assertEqual(doc.items[3].additional_cost, 11)
        self.assertEqual(doc.total_incoming_value, 67.5)

    def test_zero_cost_materials_still_receive_packing_cost(self):
        doc = entry()
        for r in doc.items:
            if r.s_warehouse:
                r.basic_rate = 0
        self.calculate(doc)
        self.assertEqual(doc.items[1].valuation_rate, .25)
        self.assertEqual(doc.items[3].valuation_rate, .25)
        self.assertEqual(doc.total_incoming_value, 7.5)

    def test_stock_uom_and_split_batch_outputs(self):
        doc = entry()
        doc.items[1].qty = .4
        doc.items[1].conversion_factor = 10
        doc.items[1].transfer_qty = 4
        doc.items.append(row(item_code="Pack A", qty=.6, transfer_qty=6, conversion_factor=10,
                             t_warehouse="Finished", bom_no="BOM-A", **{GROUP:1}))
        self.calculate(doc)
        self.assertEqual(doc.items[1].valuation_rate, 2.25)
        self.assertEqual(doc.items[-1].valuation_rate, 2.25)
        self.assertEqual(doc.total_incoming_value, 57.5)

    def test_same_output_from_two_boms_retains_distinct_group_costs(self):
        doc = entry()
        doc.custom_repack_boms[1].finished_item = "Pack A"
        doc.items[3].item_code = "Pack A"
        self.calculate(doc)
        self.assertEqual(doc.items[1].valuation_rate, 2.25)
        self.assertEqual(doc.items[3].valuation_rate, 1.75)

    def test_fractional_batch_splits_preserve_material_and_charge_totals(self):
        doc = entry()
        doc.custom_repack_boms[0].qty = 3
        doc.items[1].update(qty=1, transfer_qty=1)
        for _ in range(2):
            doc.items.append(row(item_code="Pack A", qty=1, transfer_qty=1, conversion_factor=1,
                                 t_warehouse="Finished", bom_no="BOM-A", **{GROUP:1}))
        self.calculate(doc)
        group = [r for r in doc.items if r.t_warehouse and r.get(GROUP) == 1]
        self.assertAlmostEqual(sum(r.basic_amount for r in group),20)
        self.assertAlmostEqual(sum(r.additional_cost for r in group),2.5)
        self.assertEqual(doc.total_incoming_value,57.5)

    def test_invalid_membership_quantities_and_sequential_outputs_are_rejected(self):
        for mutate in (
            lambda d: d.items[0].update({GROUP:0}),
            lambda d: d.items[1].update(qty=9),
            lambda d: d.items[1].update(item_code="Wrong output"),
            lambda d: d.items[0].update(item_code="Pack B"),
            lambda d: d.items[0].update(t_warehouse="Finished"),
            lambda d: d.items[0].update(qty=-1),
            lambda d: d.items[0].update(conversion_factor=0),
        ):
            doc = entry()
            mutate(doc)
            with self.subTest(items=doc.items), patch.object(frappe, "throw", side_effect=frappe.ValidationError):
                with self.assertRaises(frappe.ValidationError):
                    _group_items(doc)

    def test_signature_tracks_bom_quantity_warehouse_and_explosion_but_not_charge(self):
        for field, value in (("bom_no", "Other"), ("qty", 11),
                             ("source_warehouse", "Other"), ("target_warehouse", "Other"),
                             ("use_multi_level_bom", 1)):
            doc = entry()
            original = _signature(doc)
            doc.custom_repack_boms[0][field] = value
            self.assertNotEqual(original, _signature(doc), field)
        doc = entry()
        original = _signature(doc)
        doc.custom_repack_boms[0].packing_cost = 40
        self.assertEqual(original, _signature(doc))

    def test_normal_entries_delegate_to_core(self):
        doc = entry()
        doc.custom_multiple_boms = 0
        with patch.object(StockEntry, "set_basic_rate") as rates, patch.object(
            StockEntry, "distribute_additional_costs"
        ) as costs, patch.object(StockEntry, "get_items", return_value="core") as load:
            doc.set_basic_rate(False, False)
            doc.distribute_additional_costs()
            self.assertEqual(doc.get_items(), "core")
            rates.assert_called_once_with(False, False)
            costs.assert_called_once_with()
            load.assert_called_once_with()
