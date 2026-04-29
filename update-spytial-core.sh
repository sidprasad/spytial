#!/usr/bin/env bash
# Bump the bundled spytial-core version to the latest npm release.
#
# Reads the latest version from the npm registry, compares it against the
# pinned version in spytial/core_assets.py, and rewrites the version in
# both core_assets.py and the test docstring that references it.
#
# Usage:  ./update-spytial-core.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_ASSETS="$REPO_ROOT/spytial/core_assets.py"
TEST_DOCSTRING="$REPO_ROOT/test/test_data_instance_format.py"

for f in "$CORE_ASSETS" "$TEST_DOCSTRING"; do
    [[ -f "$f" ]] || { echo "missing: $f" >&2; exit 1; }
done

CURRENT="$(python3 -c "import re; print(re.search(r'SPYTIAL_CORE_VERSION = \"([^\"]+)\"', open('$CORE_ASSETS').read()).group(1))")"
LATEST="$(curl -fsSL https://registry.npmjs.org/spytial-core/latest \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')"

echo "current: $CURRENT"
echo "latest:  $LATEST"

if [[ "$CURRENT" == "$LATEST" ]]; then
    echo "Already up to date."
    exit 0
fi

python3 - "$CORE_ASSETS" "$TEST_DOCSTRING" "$CURRENT" "$LATEST" <<'PY'
import pathlib, sys
core, test, cur, new = sys.argv[1:5]
core_p = pathlib.Path(core)
core_p.write_text(core_p.read_text().replace(
    f'SPYTIAL_CORE_VERSION = "{cur}"',
    f'SPYTIAL_CORE_VERSION = "{new}"',
))
test_p = pathlib.Path(test)
test_p.write_text(test_p.read_text().replace(
    f"spytial-core v{cur} IJsonDataInstance",
    f"spytial-core v{new} IJsonDataInstance",
))
PY

echo "Bumped spytial-core $CURRENT -> $LATEST"
echo "Run 'pytest' to verify."
