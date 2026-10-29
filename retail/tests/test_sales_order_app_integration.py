"""Focused Sales Order API regression checks; all business writes are rolled back."""
import frappe
from frappe.utils import add_days, nowdate


def run_integration():
	from retail.api import pos_sync as api
	if frappe.local.site != 'retail-test.localhost':
		raise RuntimeError('Use retail-test.localhost')
	original_user = frappe.session.user
	frappe.set_user('Administrator')
	frappe.flags.in_test = True
	try:
		token = frappe.generate_hash(length=10)
		company = frappe.db.get_value('POS Branch Counter', {'is_active': 1}, 'company')
		currency = frappe.get_cached_value('Company', company, 'default_currency')
		customer = api.upsert_customer({'context': 'sales_order', 'external_customer_id': 'SO-TEST-'+token,
			'customer': {'customer_name': 'SO API '+token, 'customer_type': 'Individual',
				'customer_group': frappe.db.get_value('Customer Group', {'is_group': 0}, 'name'),
				'territory': frappe.db.get_value('Territory', {'is_group': 0}, 'name')},
			'addresses': [{'address_type': 'Billing', 'address_line1': 'Test street', 'city': 'Dubai', 'country': 'United Arab Emirates'}],
			'contacts': [{'first_name': 'API Test', 'phone_nos': [{'phone': '971500000001', 'is_primary_mobile_no': 1}],
				'email_ids': [{'email_id': 'so-api@example.invalid', 'is_primary': 1}]}]})
		assert len(customer['addresses']) == len(customer['contacts']) == 1
		item = frappe.get_doc({'doctype': 'Item', 'item_code': 'SO-API-'+token, 'item_name': 'SO API test',
			'item_group': frappe.db.get_value('Item Group', {'is_group': 0}, 'name'),
			'stock_uom': 'Nos', 'is_stock_item': 0, 'is_sales_item': 1}).insert()
		order = {'company': company, 'customer': customer['customer'], 'transaction_date': nowdate(),
			'delivery_date': add_days(nowdate(), 2), 'currency': currency,
			'selling_price_list': 'Standard Selling', 'customer_address': customer['addresses'][0],
			'contact_person': customer['contacts'][0],
			'items': [{'item_code': item.name, 'qty': 2, 'uom': 'Nos', 'rate': 100}]}
		before = frappe.db.count('Sales Order')
		preview = api.save_sales_order({'action': 'calculate', 'order': order})
		assert frappe.db.count('Sales Order') == before
		assert preview['order']['items'][0]['amount'] == 200, preview
		inclusive_order = dict(order, items=[{'item_code': item.name, 'qty': 2, 'uom': 'Nos',
			'custom_rate_including_vat': 105, 'custom_foc_qty': 1}])
		inclusive = api.save_sales_order({'action': 'calculate', 'order': inclusive_order})
		assert inclusive['order']['items'][0]['custom_rate_including_vat'] == 105, inclusive
		assert inclusive['order']['items'][0]['custom_foc_qty'] == 1, inclusive
		from retail.domains.item.vat_pricing import get_item_tax_rate
		for template_name in frappe.get_all('Item Tax Template', filters={'company': company}, pluck='name'):
			vat_rate = get_item_tax_rate(template_name)
			if vat_rate > 0:
				item.custom_tax = template_name
				item.save()
				taxed_order = dict(order, items=[{'item_code': item.name, 'qty': 2, 'uom': 'Nos',
					'custom_rate_including_vat': 100 * (1 + vat_rate / 100)}])
				taxed = api.save_sales_order({'action': 'calculate', 'order': taxed_order})
				assert abs(taxed['order']['items'][0]['rate'] - 100) < 0.01, taxed
				assert abs(taxed['order']['grand_total'] - 200 * (1 + vat_rate / 100)) < 0.01, taxed
				break
		else:
			raise AssertionError('No positive VAT template available for taxable pricing check')
		created = api.save_sales_order({'client_order_id': token, 'order': order})
		assert created['docstatus'] == 0
		retry = api.save_sales_order({'client_order_id': token, 'order': order})
		assert retry['duplicate'] and retry['name'] == created['name']
		try:
			api.save_sales_order({'name': created['name'], 'modified': '2000-01-01', 'order': order})
		except frappe.TimestampMismatchError:
			pass
		else:
			raise AssertionError('Stale draft accepted')
		updated = api.save_sales_order({'name': created['name'], 'modified': str(created['order']['modified']),
			'order': {'po_no': 'APP-TEST'}})
		assert updated['order']['po_no'] == 'APP-TEST'
		submitted = api.save_sales_order({'action': 'submit', 'name': created['name'],
			'modified': str(updated['order']['modified'])})
		assert submitted['docstatus'] == 1
		assert api.save_sales_order({'action': 'submit', 'client_order_id': token})['duplicate']
		read = api.get_sales_order_data({'queries': [{'doctype': 'Sales Order', 'name': created['name']},
			{'doctype': 'Item', 'filters': {'name': item.name}, 'include_details': True, 'fields': ['item_code']}]})
		assert read['results'][0]['documents'][0]['docstatus'] == 1
		assert read['results'][1]['documents'][0]['name'] == item.name
		# A real ERP salesperson needs no POS Integration User role.
		user = frappe.get_doc({'doctype': 'User', 'email': 'so-api-'+token+'@example.invalid',
			'first_name': 'Sales API', 'send_welcome_email': 0,
			'roles': [{'role': 'Sales User'}]}).insert()
		frappe.set_user(user.name)
		assert 'POS Integration User' not in frappe.get_roles()
		ordinary = api.save_sales_order({'action': 'submit', 'client_order_id': token+'-user', 'order': order})
		assert ordinary['docstatus'] == 1
		assert api.get_sales_order_data({'queries': [{'doctype': 'Sales Order', 'name': ordinary['name']}]})['results']
		frappe.set_user('Administrator')
		limited = frappe.get_doc({'doctype': 'User', 'email': 'so-denied-'+token+'@example.invalid',
			'first_name': 'No sales role', 'send_welcome_email': 0}).insert()
		frappe.set_user(limited.name)
		for call, payload in [(api.save_sales_order, {'client_order_id': token+'-denied', 'order': order}),
			(api.get_sales_order_data, {'queries': [{'doctype': 'Sales Order'}]})]:
			try:
				call(payload)
			except frappe.PermissionError:
				pass
			else:
				raise AssertionError('ERP role permission bypassed')
		frappe.set_user('Guest')
		for call, payload in [(api.save_sales_order, {}), (api.get_sales_order_data, {}),
			(api.upsert_customer, {'context': 'sales_order'})]:
			try:
				call(payload)
			except frappe.AuthenticationError:
				pass
			else:
				raise AssertionError('Guest accepted')
		print('PASS: customer/address/contact; preview without save; inclusive price/FOC; draft create/update; stale update; submit; retries; multi-master/detail; ordinary Sales User; ERP permission denial; guest rejection')
	finally:
		frappe.set_user(original_user)
		frappe.db.rollback()
