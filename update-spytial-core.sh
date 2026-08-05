#!/usr/bin/env bash
# Bump the bundled spytial-core version to the latest npm release.
#
# Reads the latest version from the npm registry, compares it against the
# pinned version in spytial/core_assets.py, and rewrites the version in
# core_assets.py, the test docstring that references it, the vendored
# evaluator bundle, the vendored conformance harness bin, and the vendor
# README's pin.
#
# It also re-vendors the language manifest and regenerates the annotation
# tables from it. Core's parser ignores anything it does not recognize, so a
# release that adds a field or moves a form to the other section would
# otherwise leave the Python side accepting exactly what it accepted before --
# emitting a spec core silently drops part of, with no error anywhere. The
# regeneration turns that into a diff in review, and into a test failure if it
# is skipped.
#
# Usage:  ./update-spytial-core.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_ASSETS="$REPO_ROOT/spytial/core_assets.py"
TEST_DOCSTRING="$REPO_ROOT/test/test_data_instance_format.py"
VENDOR_EVALUATOR="$REPO_ROOT/spytial/suggest/_vendor/spytial-core-evaluator.js"
VENDOR_README="$REPO_ROOT/spytial/suggest/_vendor/README.md"
VENDOR_MANIFEST="$REPO_ROOT/spytial/_vendor/spytial-language.json"
VENDOR_SCHEMA="$REPO_ROOT/spytial/_vendor/spytial-spec.schema.json"
VENDOR_CHECK="$REPO_ROOT/test/_vendor/spytial-check.js"
GENERATOR="$REPO_ROOT/scripts/generate_spec_tables.py"
VENDOR_LOCK="$REPO_ROOT/scripts/vendor_lock.py"

for f in "$CORE_ASSETS" "$TEST_DOCSTRING" "$VENDOR_EVALUATOR" "$VENDOR_README" \
         "$VENDOR_MANIFEST" "$VENDOR_SCHEMA" "$VENDOR_CHECK" "$GENERATOR" "$VENDOR_LOCK"; do
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

python3 - "$CORE_ASSETS" "$TEST_DOCSTRING" "$VENDOR_README" "$CURRENT" "$LATEST" <<'PY'
import pathlib, sys
core, test, readme, cur, new = sys.argv[1:6]
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
readme_p = pathlib.Path(readme)
readme_p.write_text(readme_p.read_text().replace(
    f"Pinned version: **spytial-core {cur}**",
    f"Pinned version: **spytial-core {new}**",
).replace(
    f"VERSION={cur}",
    f"VERSION={new}",
))
PY

# Re-vendor the self-contained evaluator from the freshly published tarball so
# the tier-2 pin can't drift from the browser pin again.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
( cd "$TMP" && npm pack "spytial-core@$LATEST" --silent && tar xzf "spytial-core-$LATEST.tgz" )
cp "$TMP/package/dist/evaluator.js" "$VENDOR_EVALUATOR"

# The conformance harness bin, which answers what a decorator's spec *entails*
# (test/conformance.py). It has to move with this same pin: a harness from one
# release checking specs written against another is the drift the rest of this
# script exists to prevent, arriving through the thing meant to catch it.
cp "$TMP/package/dist/cli/spytial-check.js" "$VENDOR_CHECK"

# Re-vendor the language manifest and regenerate the annotation tables from it.
# The generator refuses to emit output it cannot account for, so a release that
# adds a construct stops here by name rather than dropping it silently.
cp "$TMP/package/docs/spytial-language.json" "$VENDOR_MANIFEST"
# The spec schema covers the other direction: the manifest says what spytial may
# accept, the schema says whether what it emits is well-formed.
cp "$TMP/package/docs/spytial-spec.schema.json" "$VENDOR_SCHEMA"
python3 "$GENERATOR"

# Record which release every vendored file came from. The evaluator bundle is
# minified with no version string in it, so this lockfile is the only thing that
# can tell a stale copy from a current one.
python3 "$VENDOR_LOCK"

# Confirm each bundle stayed self-contained. Both are copied out of the tarball
# with no node_modules beside them, so a bare require of anything that is not a
# node builtin means the file cannot load where we put it. The allowed builtins
# are listed per file rather than blanket-allowed, so a build that starts
# reaching for a new one is still worth a look.
check_self_contained() {
    local label="$1" file="$2" allowed="$3" external
    external="$(grep -oE "require\(['\"][^'\"]+['\"]\)" "$file" \
        | grep -vE "require\(['\"](\.|node:)" \
        | sed -E "s/require\(['\"]([^'\"]+)['\"]\)/\1/" \
        | sort -u | grep -vxE "$allowed" || true)"
    if [[ -n "$external" ]]; then
        echo "WARNING: vendored $label has unexpected external requires:" >&2
        echo "$external" >&2
    fi
}

check_self_contained evaluator "$VENDOR_EVALUATOR" 'util'
check_self_contained spytial-check "$VENDOR_CHECK" 'child_process|fs|path|util'

echo "Bumped spytial-core $CURRENT -> $LATEST (assets pin, vendored evaluator + spytial-check, language manifest + tables)"
echo
echo "Next:"
echo "  1. Review spytial/_spec_tables.py -- that diff IS the language change."
echo "     If LANGUAGE_VERSION did not move, the language did not change."
echo "  2. Run 'pytest'. Failures name whatever hand-written surface is now behind."
echo "  3. Run 'python3 scripts/generate_api_baseline.py' if the public API changed;"
echo "     test_api_baseline.py will say whether the change is additive or breaking,"
echo "     and therefore what version bump it warrants."
