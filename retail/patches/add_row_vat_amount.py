"""Expose row VAT in existing personal transaction table layouts."""

import frappe

from retail.domains.transactions.vat import VAT_RATE_ITEM_DOCTYPES, ensure_transaction_vat_rate_fields
from retail.grid_view_settings import _get_user_settings, _save_user_settings


def execute():
	ensure_transaction_vat_rate_fields()
	for row in frappe.db.sql("SELECT user, doctype FROM `__UserSettings`", as_dict=True):
		settings = _get_user_settings(row.user, row.doctype)
		changed = False
		for key in ("GridView", "RetailScrollableGrid"):
			for table, columns in (settings.get(key) or {}).items():
				child = table if key == "GridView" else frappe.get_meta(row.doctype).get_field(table)
				child = child.options if hasattr(child, "options") else child
				if child not in VAT_RATE_ITEM_DOCTYPES or not columns:
					continue
				if any(column.get("fieldname") == "custom_vat_amount" for column in columns):
					continue
				index = next((i + 1 for i, column in enumerate(columns) if column.get("fieldname") == "amount"), len(columns))
				columns.insert(index, {"fieldname": "custom_vat_amount", "columns": 2})
				changed = True
		if changed:
			_save_user_settings(row.user, row.doctype, settings)
			frappe.cache.hdel("_user_settings", f"{row.doctype}::{row.user}")
