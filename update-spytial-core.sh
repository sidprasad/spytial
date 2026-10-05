#!/usr/bin/env bash
# Vendor latest, an exact --version, or an offline --tarball; --check verifies.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON:-python3}" "$REPO_ROOT/scripts/vendor_core.py" "$@"
