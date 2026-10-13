#!/usr/bin/env bash
set -euo pipefail
umask 0002
cd /home/frappe/frappe-bench

# The base entrypoint removes sites/assets on every start. Preserve this shared
# directory and restore the image's exact mappings for ALL commands/containers.
./env/bin/python -m retail.build_asset_manifest --install-runtime
exec "$@"
