import json
import tempfile
import unittest
from pathlib import Path
from retail.build_asset_manifest import validate_desk_bundles

class ReleaseAssets(unittest.TestCase):
    def test_missing_hrms_and_complete_release(self):
        with tempfile.TemporaryDirectory() as folder:
            assets = Path(folder)
            mapping = {}
            for app, bundle in [('retail', 'retail_desk'), ('hrms', 'hrms')]:
                for extension in ('css', 'js'):
                    key = f'{bundle}.bundle.{extension}'
                    relative = f'{app}/dist/{extension}/{bundle}.bundle.HASH.{extension}'
                    path = assets / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('asset')
                    mapping[key] = '/assets/' + relative
            (assets / 'assets.json').write_text(json.dumps(mapping))
            validate_desk_bundles(assets)
            (assets / mapping['hrms.bundle.js'].removeprefix('/assets/')).unlink()
            with self.assertRaisesRegex(RuntimeError, 'hrms.bundle.js'):
                validate_desk_bundles(assets)

if __name__ == '__main__':
    unittest.main()
