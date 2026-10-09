from unittest import TestCase
from unittest.mock import patch

import frappe
from retail import business_home_preload as preload


class TestBusinessHomePreload(TestCase):
	def test_dynamic_references_deduplicate_and_fail_independently(self):
		data = {
			'number_cards': {'items': [{'number_card_name': n} for n in ['New Card', 'New Card', 'Broken']]},
			'charts': {'items': [{'chart_name': 'New Chart'}]},
		}
		def load(doctype, name):
			return None if name == 'Broken' else {'docs': [{'doctype': doctype, 'name': name}], 'docinfo': {}}
		with patch.object(preload, 'standard_get_desktop_page', return_value=data), patch.object(preload, '_load_definition', side_effect=load) as loader:
			result = preload.get_desktop_page('{"name":"Business Home"}')
		self.assertEqual(loader.call_count, 3)
		self.assertEqual(len(result['retail_widget_definitions']), 2)

	def test_other_workspace_is_unchanged(self):
		data = {'number_cards': {'items': []}}
		with patch.object(preload, 'standard_get_desktop_page', return_value=data), patch.object(preload, '_load_definition') as loader:
			self.assertIs(preload.get_desktop_page('{"name":"POS"}'), data)
		loader.assert_not_called()

	def test_loader_restores_response_messages_and_flags_on_permission_failure(self):
		response, messages, flags = frappe.local.response, frappe.local.message_log, frappe.local.flags
		def denied(*args):
			frappe.local.response['docinfo'] = {'secret': 'must not escape'}
			frappe.local.message_log.append('unrelated widget permission error')
			frappe.flags.error_message = 'permission error'
			raise frappe.PermissionError
		with patch.object(preload, 'getdoc', side_effect=denied):
			self.assertIsNone(preload._load_definition('Number Card', 'Denied'))
		self.assertIs(frappe.local.response, response)
		self.assertIs(frappe.local.message_log, messages)
		self.assertIs(frappe.local.flags, flags)

	def test_standard_getdoc_payload_is_preserved(self):
		doc = {'doctype': 'Number Card', 'name': 'New Card', '__onload': {'x': 1}}
		info = {'doctype': 'Number Card', 'name': 'New Card', 'permissions': {'read': 1}}
		def loaded(*args):
			frappe.local.response.update(docs=[doc], docinfo=info)
		with patch.object(preload, 'getdoc', side_effect=loaded):
			result = preload._load_definition('Number Card', 'New Card')
		self.assertEqual(result, {'docs': [doc], 'docinfo': info})

	def test_configs_only_for_loaded_custom_charts_and_failure_falls_back(self):
		data = {'charts': {'items': [{'chart_name': n} for n in ['One', 'Two', 'Denied', 'Broken']]}}
		def load(doctype, name):
			if name == 'Denied':
				return None
			return {'docs': [{'doctype': doctype, 'name': name, 'chart_type': 'Custom',
				'source': 'Broken' if name == 'Broken' else 'Shared'}], 'docinfo': {}}
		def config(name):
			if name == 'Broken':
				raise OSError('missing config')
			return 'source config'
		with patch.object(preload, 'standard_get_desktop_page', return_value=data), patch.object(preload, '_load_definition', side_effect=load), patch.object(preload, 'get_config', side_effect=config) as configs:
			result = preload.get_desktop_page('{"name":"Business Home"}')
		self.assertEqual(result['retail_chart_source_configs'], {'Shared': 'source config'})
		self.assertEqual(configs.call_count, 2)
