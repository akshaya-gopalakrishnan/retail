"""Repair skipped purchase defaults once, retaining existing columns and widths."""

import copy
import json

import frappe

from retail.grid_view_settings import _get_user_settings, _save_user_settings, get_fixture_path
from retail.patches.show_purchase_item_names import PURCHASE_DOCTYPES, add_item_name
from retail.patches.show_purchase_stock_identity import DOCTYPES, add_columns


def repair_settings(parent, settings, defaults):
	result = copy.deepcopy(settings)
	child = parent + " Item"
	legacy = result.get("GridView")
	legacy = legacy if isinstance(legacy, dict) else {}
	own = result.get("RetailScrollableGrid")
	own = own if isinstance(own, dict) else {}
	# An absent/empty Retail layout must not mask a valid native layout.
	fallback = own.get("items") or legacy.get(child) or defaults[parent][child]
	for namespace, key in (("GridView", child), ("RetailScrollableGrid", "items")):
		mapping = result.get(namespace)
		if not isinstance(mapping, dict):
			mapping = result[namespace] = {}
		columns = copy.deepcopy(mapping.get(key) or fallback)
		columns = add_item_name(columns)
		if parent in DOCTYPES:
			columns = add_columns(columns)
		mapping[key] = columns
	return result


def execute():
	defaults = json.loads(get_fixture_path().read_text())
	for user in frappe.get_all("User", pluck="name"):
		if user == "Guest":
			continue
		for parent in PURCHASE_DOCTYPES:
			current = _get_user_settings(user, parent)
			cache_key = f"{parent}::{user}"
			cached = frappe.cache.hget("_user_settings", cache_key)
			if cached is not None:
				current.update(json.loads(cached or "{}"))
			repaired = repair_settings(parent, current, defaults)
			if repaired != current:
				_save_user_settings(user, parent, repaired)

				def invalidate(key=cache_key):
					frappe.cache.hdel("_user_settings", key)

				frappe.db.after_commit.add(invalidate)
				frappe.db.after_rollback.add(invalidate)
