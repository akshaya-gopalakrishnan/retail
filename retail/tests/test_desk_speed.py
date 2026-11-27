"""Cache identities and commit/rollback invalidation, without business fixtures."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

import frappe
from retail import desk_speed as speed


class TestDeskSpeed(unittest.TestCase):
    def setUp(self):
        p = patch.object(speed, "nowdate", return_value="2026-11-27")
        p.start(); self.addCleanup(p.stop)
        self.values = {}
        self.cache = Mock()
        self.cache.get_value.side_effect = lambda key: self.values.get(key)
        self.cache.set_value.side_effect = lambda key, value, **kw: self.values.__setitem__(key, value)
        for target, value in (("cache", self.cache), ("flags", frappe._dict()),
                              ("form_dict", frappe._dict()), ("session", frappe._dict(user="A"))):
            p = patch.object(frappe, target, value); p.start(); self.addCleanup(p.stop)
        p = patch.object(frappe.defaults, "get_user_default", return_value="Company A")
        self.company = p.start(); self.addCleanup(p.stop)
        self.compute = Mock(return_value={"value": 7})
        self.get = speed.cached("cards", 60)(self.compute)

    def test_cache_is_scoped_by_user_company_and_arguments(self):
        self.assertEqual(self.get(company="One"), {"value": 7})
        self.assertEqual(self.get(company="One"), {"value": 7})
        self.assertEqual(self.compute.call_count, 1)
        frappe.session.user = "B"; self.get(company="One")
        self.company.return_value = "Company B"; self.get(company="One")
        self.get(company="Two")
        self.assertEqual(self.compute.call_count, 4)

    def test_empty_results_cache_and_failures_do_not(self):
        self.compute.return_value = []
        self.assertEqual(self.get(), []); self.assertEqual(self.get(), [])
        self.assertEqual(self.compute.call_count, 1)
        self.compute.side_effect = RuntimeError("failed")
        for _ in range(2):
            with self.assertRaises(RuntimeError): self.get(fresh=True)
        self.assertEqual(self.compute.call_count, 3)

    def test_invalidation_waits_for_commit_and_coalesces(self):
        commit, rollback = [], []
        db = SimpleNamespace(after_commit=SimpleNamespace(add=commit.append),
                             after_rollback=SimpleNamespace(add=rollback.append))
        self.get()
        with patch.object(frappe, "db", db):
            speed.invalidate_values(); speed.invalidate_values(); speed.invalidate_permissions()
        self.assertEqual(len(commit), 1)
        self.get(); self.assertEqual(self.compute.call_count, 1)
        commit[0]()
        self.get(); self.assertEqual(self.compute.call_count, 2)
        self.assertNotIn("retail_desk_speed_invalidations", frappe.flags)

    def test_rollback_keeps_current_epoch(self):
        rollback = []
        db = SimpleNamespace(after_commit=SimpleNamespace(add=lambda f: None),
                             after_rollback=SimpleNamespace(add=rollback.append))
        self.get()
        with patch.object(frappe, "db", db): speed.invalidate_values()
        rollback[0](); self.get()
        self.assertEqual(self.compute.call_count, 1)
        self.assertNotIn("retail_desk_speed_invalidations", frappe.flags)
