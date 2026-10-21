#!/usr/bin/env bash
# Rebuild public assets without changing developer mode or application source.
set -euo pipefail
bench_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$bench_directory"
bench build --production --force
./env/bin/python - <<'PY'
from pathlib import Path
from retail.build_asset_manifest import clear_runtime_asset_cache, validate_desk_bundles
validate_desk_bundles(Path('sites/assets'))
clear_runtime_asset_cache(Path.cwd())
print('Production bundles validated; runtime asset-map cache invalidated.')
PY
