"""Apply the requested Buy/Get field placement to existing customized layouts."""
import json
import frappe


def execute():
	for name in frappe.get_all('Property Setter', filters={
		'doc_type': 'Buy X Get Y Promotion', 'property': 'field_order'}, pluck='name'):
		setter = frappe.get_doc('Property Setter', name)
		order = json.loads(setter.value)
		order = [field for field in order if field not in ('qty_section', 'priority')]
		if 'promotion_scope' not in order:
			position = order.index('notes') + 1 if 'notes' in order else len(order)
			order.insert(position, 'promotion_scope')
		order.insert(order.index('promotion_scope') + 1, 'priority')
		setter.value = json.dumps(order)
		setter.save(ignore_permissions=True)
	frappe.clear_cache(doctype='Buy X Get Y Promotion')
