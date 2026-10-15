"""Preserve old scopes and add hour conditions to existing linked rules."""
import frappe
from retail.promotions.schedule import sync_scheme_hours


def execute():
	for doctype in ('Promo Price', 'Buy X Get Y Promotion'):
		for name in frappe.get_all(doctype, pluck='name'):
			doc = frappe.get_doc(doctype, name)
			if doctype == 'Promo Price' and not doc.get('promotion_scope'):
				scope = 'CATEGORY' if doc.products and doc.products[0].item_group else 'ITEM'
				frappe.db.set_value(doctype, name, 'promotion_scope', scope, update_modified=False)
			for row in doc.get('linked_schemes') or []:
				if frappe.db.exists('Promotional Scheme', row.promotional_scheme):
					sync_scheme_hours(doc, frappe.get_doc('Promotional Scheme', row.promotional_scheme))
