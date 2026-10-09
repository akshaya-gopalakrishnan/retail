import unittest
from unittest.mock import patch

from retail.workspace_permissions import SidebarWorkspace


class TestSidebarDiscovery(unittest.TestCase):
    def test_module_scoped_discovery_is_isolated_from_mutations_and_operations(self):
        first = object.__new__(SidebarWorkspace)
        second = object.__new__(SidebarWorkspace)
        first.sidebar_discovery = second.sidebar_discovery = {}
        with patch('retail.workspace_permissions.get_custom_reports_and_doctypes',
                   side_effect=lambda module: [{'label': module, 'links': [{'link_to': 'Allowed'}]}]) as discover:
            links = first._discover_custom_links('Stock')
            links[0]['links'][0]['link_to'] = 'Changed'
            self.assertEqual(second._discover_custom_links('Stock')[0]['links'][0]['link_to'], 'Allowed')
            self.assertEqual(discover.call_count, 1)
            second._discover_custom_links('Buying')
            self.assertEqual(discover.call_count, 2)
            second.sidebar_discovery = {}
            second._discover_custom_links('Stock')
            self.assertEqual(discover.call_count, 3)

    def test_cached_discovery_rechecks_item_permissions_for_each_workspace(self):
        import frappe
        from types import SimpleNamespace

        shared = {}
        with patch('retail.workspace_permissions.get_custom_reports_and_doctypes', return_value=[
            {'label': 'Custom Documents', 'links': [
                {'link_to': 'Visible', 'link_type': 'doctype'},
                {'link_to': 'Restricted', 'link_type': 'doctype'},
            ]}
        ]) as discover, patch.object(frappe.local, 'db', new=SimpleNamespace(get_default=lambda key: None), create=True) as db, patch.object(frappe, '_', side_effect=lambda text: text):
            for permitted in ['Visible', 'Restricted', None]:
                workspace = object.__new__(SidebarWorkspace)
                workspace.sidebar_discovery = shared
                workspace.doc = SimpleNamespace(hide_custom=False, module='Stock', get_link_groups=lambda: [])
                workspace.is_item_allowed = lambda name, kind: name == permitted
                workspace._prepare_item = lambda item: item
                cards = workspace.get_links()
                self.assertEqual([item.link_to for card in cards for item in card['links']],
                                 [permitted] if permitted else [])
            self.assertEqual(discover.call_count, 1)

    def test_sidebar_presence_does_not_load_form_metadata(self):
        import frappe
        first = object.__new__(SidebarWorkspace)
        second = object.__new__(SidebarWorkspace)
        first.sidebar_discovery = second.sidebar_discovery = {}
        item = frappe._dict(link_type='DocType',link_to='Allowed',label='Allowed')
        with patch.object(frappe,'get_meta',side_effect=AssertionError('Metadata loaded')), patch.object(frappe,'get_all',return_value=['Allowed']) as names:
            for workspace in (first,second):
                prepared = workspace._prepare_item(item)
                self.assertEqual(prepared.link_type,'DocType')
                self.assertEqual(prepared.label,'Allowed')
            self.assertEqual(names.call_count,1)
            with self.assertRaises(frappe.DoesNotExistError):
                first._prepare_item(frappe._dict(link_type='DocType',link_to='Missing'))
