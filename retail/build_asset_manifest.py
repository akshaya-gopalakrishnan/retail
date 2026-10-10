"""Preserve app bundle mappings in Docker images after a selective build."""
import json
import re
from pathlib import Path


def repair(assets):
    assets = Path(assets)
    for filename, folders, prefix in (
        ('assets.json', ('css', 'js'), ''),
        ('assets-rtl.json', ('css-rtl',), 'rtl_'),
    ):
        manifest = assets / filename
        data = json.loads(manifest.read_text()) if manifest.exists() else {}
        for app in ('retail', 'hrms'):
            for folder in folders:
                for path in sorted((assets / app / 'dist' / folder).glob('*')):
                    match = re.fullmatch(r'(.+\.bundle)\.[^.]+\.(css|js)', path.name)
                    if match:
                        key = prefix + match.group(1) + '.' + match.group(2)
                        data[key] = '/assets/' + path.relative_to(assets).as_posix()
        manifest.write_text(json.dumps(data, indent=2) + '\n')
    data = json.loads((assets / 'assets.json').read_text())
    for key in ('retail_desk.bundle.css', 'retail_desk.bundle.js'):
        if key not in data or not (assets / data[key].removeprefix('/assets/')).is_file():
            raise RuntimeError(f'Missing required bundle: {key}')


if __name__ == '__main__':
    repair(Path.cwd() / 'sites/assets')
