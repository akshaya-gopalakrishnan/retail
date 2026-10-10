import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import frappe
from retail.build_asset_manifest import repair
from retail.pos_transaction_display import correct_consolidated_title, refresh_accepted_invoice_links


class TestRecoveredPOSDisplay(unittest.TestCase):
    def test_recovery_updates_links_without_rewriting_receipt(self):
        db = Mock()
        db.exists.return_value = True
        db.get_value.return_value = 'PSI-1'
        transaction = frappe._dict(pos_invoice='POS-1', external_pos_reference='SALE-1')
        with patch.object(frappe, 'db', db), patch.object(frappe, 'get_all', return_value=['PSL-1']) as get_all:
            refresh_accepted_invoice_links(transaction)
        self.assertEqual(get_all.call_args.kwargs['filters']['status'], ['in', ['Success', 'Duplicate']])
        values = db.set_value.call_args.args[2]
        self.assertEqual(values, dict(linked_invoice_type='POS Invoice', linked_invoice='POS-1',
            custom_accounting_invoice='PSI-1', erpnext_docname='POS-1'))

    def test_unposted_acceptance_does_not_claim_invoice_links(self):
        with patch.object(frappe, 'db', Mock()) as db:
            refresh_accepted_invoice_links(frappe._dict(pos_invoice=None))
        db.set_value.assert_not_called()

    def test_literal_series_title_is_repaired(self):
        doc = frappe._dict(is_consolidated=1, title='PSI-.#', naming_series='PSI-.#', customer_name='Customer')
        correct_consolidated_title(doc)
        self.assertEqual(doc.title, 'Customer')

    def test_custom_and_standalone_titles_are_preserved(self):
        for consolidated, title in ((1, 'Custom title'), (0, 'PSI-.#')):
            doc = frappe._dict(is_consolidated=consolidated, title=title, naming_series='PSI-.#')
            correct_consolidated_title(doc)
            self.assertEqual(doc.title, title)

    def test_manifest_preserves_core_and_adds_correct_rtl_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            assets = Path(folder)
            (assets / 'assets.json').write_text(json.dumps({'desk.bundle.js': '/assets/core.js'}))
            for subpath in ('retail/dist/css/retail_desk.bundle.A.css',
                            'retail/dist/js/retail_desk.bundle.B.js',
                            'retail/dist/css-rtl/retail_desk.bundle.C.css'):
                path = assets / subpath
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('asset')
            repair(assets)
            repair(assets)
            normal = json.loads((assets / 'assets.json').read_text())
            rtl = json.loads((assets / 'assets-rtl.json').read_text())
            self.assertEqual(normal['desk.bundle.js'], '/assets/core.js')
            self.assertEqual(normal['retail_desk.bundle.css'], '/assets/retail/dist/css/retail_desk.bundle.A.css')
            self.assertEqual(rtl['rtl_retail_desk.bundle.css'], '/assets/retail/dist/css-rtl/retail_desk.bundle.C.css')
            self.assertNotIn('retail_desk.bundle.css', rtl)


class TestDockerMountedAssets(unittest.TestCase):
    def test_mounted_volume_gets_image_hashes_and_preserves_existing_assets(self):
        from retail.build_asset_manifest import install, snapshot
        with tempfile.TemporaryDirectory() as folder:
            bench = Path(folder)
            assets = bench / 'sites/assets'
            assets.mkdir(parents=True)
            for app in ('retail', 'hrms'):
                public = bench / 'apps' / app / app / 'public'
                public.mkdir(parents=True)
                (assets / app).symlink_to(public, target_is_directory=True)
            for subpath in ('css/retail_desk.bundle.NEW.css', 'js/retail_desk.bundle.NEW.js'):
                path = assets / 'retail/dist' / subpath
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('new image content')
            repair(assets)
            snapshot(bench)
            (assets / 'assets.json').write_text(json.dumps({'old.bundle.js': '/assets/old.js'}))
            (assets / 'assets-rtl.json').write_text('{}')
            (assets / 'retail').unlink()
            stale = assets / 'retail/dist/css/retail_desk.bundle.ZZZ.css'
            stale.parent.mkdir(parents=True)
            stale.write_text('old content')
            self.assertTrue(install(bench))
            self.assertTrue(install(bench))
            data = json.loads((assets / 'assets.json').read_text())
            self.assertEqual(data['retail_desk.bundle.css'], '/assets/retail/dist/css/retail_desk.bundle.NEW.css')
            self.assertEqual(data['old.bundle.js'], '/assets/old.js')
            self.assertTrue(stale.exists())
            self.assertTrue((assets / 'retail/dist/js/retail_desk.bundle.NEW.js').is_file())

    def test_ordinary_bench_is_unchanged(self):
        from retail.build_asset_manifest import install
        with tempfile.TemporaryDirectory() as folder:
            self.assertFalse(install(Path(folder)))
            self.assertFalse((Path(folder) / 'sites').exists())

    def test_old_rtl_manifest_cannot_shadow_current_css_or_js(self):
        from retail.build_asset_manifest import install, snapshot
        with tempfile.TemporaryDirectory() as folder:
            bench = Path(folder)
            assets = bench / 'sites/assets'
            assets.mkdir(parents=True)
            for app in ('retail', 'hrms'):
                public = bench / 'apps' / app / app / 'public'
                public.mkdir(parents=True)
                (assets / app).symlink_to(public, target_is_directory=True)
            for subpath in ('css/retail_desk.bundle.NEW.css', 'js/retail_desk.bundle.NEW.js',
                            'css-rtl/retail_desk.bundle.RTL.css'):
                path = assets / 'retail/dist' / subpath
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('asset')
            (assets / 'assets-rtl.json').write_text(json.dumps({
                'retail_desk.bundle.css': '/assets/missing-old.css',
                'retail_desk.bundle.js': '/assets/missing-old.js',
            }))
            repair(assets)
            snapshot(bench)
            # The persisted volume can have the same bad keys independently.
            (assets / 'assets-rtl.json').write_text(json.dumps({
                'retail_desk.bundle.css': '/assets/missing-old.css',
                'retail_desk.bundle.js': '/assets/missing-old.js',
            }))
            install(bench)
            merged = json.loads((assets / 'assets.json').read_text())
            merged.update(json.loads((assets / 'assets-rtl.json').read_text()))
            for key in ('retail_desk.bundle.css', 'retail_desk.bundle.js', 'rtl_retail_desk.bundle.css'):
                self.assertTrue((assets / merged[key].removeprefix('/assets/')).is_file())
            self.assertEqual(merged['retail_desk.bundle.css'], '/assets/retail/dist/css/retail_desk.bundle.NEW.css')

    def test_failed_link_migration_does_not_rewrite_response_or_status(self):
        from retail.patches.repair_failed_pos_log_links import execute
        db = Mock()
        with patch.object(frappe, 'db', db), patch.object(frappe, 'get_all', return_value=['PSL-failed']) as get_all, \
                patch('retail.patches.repair_recovered_pos_display.execute'):
            execute()
        self.assertEqual(get_all.call_args.kwargs['filters']['status'], 'Failed')
        values = db.set_value.call_args.args[2]
        self.assertEqual(set(values), {'linked_invoice_type', 'linked_invoice', 'custom_accounting_invoice', 'erpnext_docname'})
        self.assertTrue(all(value is None for value in values.values()))
