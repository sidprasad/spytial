# Vendored spytial-core evaluator

`spytial-core-evaluator.js` is the **self-contained** `./evaluator` build of
[`spytial-core`](https://github.com/sidprasad/spytial-core), copied verbatim from
the published npm tarball. It bundles its runtime deps (`graphlib`,
`simple-graph-query`, `lodash`) inline, so it requires only the Node `util`
builtin — no sibling `node_modules`.

It lets `spytial.suggest`'s tier-2 selector validation ([`../_eval.py`](../_eval.py))
run headlessly with just a `node` binary on the machine — no `npm install`, no
`SPYTIAL_CORE_NODE_PATH`. The self-contained build was introduced in
spytial-core 2.10.1 (tsup `noExternal`); 2.11.0 additionally re-exports the static
analyzer (`analyzeForgeExpression`) and the by-example synthesizers on the
`./evaluator` entry, which the tier-2 bridge uses for the static gate and repair
feedback. The 3.0 style-system major left this entry's API unchanged.

## Regenerate (when bumping the pinned spytial-core)

```sh
VERSION=3.2.1   # the spytial-core release to vendor
TMP=$(mktemp -d)
( cd "$TMP" && npm pack "spytial-core@$VERSION" && tar xzf "spytial-core-$VERSION.tgz" )
cp "$TMP/package/dist/evaluator.js" spytial/suggest/_vendor/spytial-core-evaluator.js
rm -rf "$TMP"
```

Then confirm it stayed self-contained (only `util` should print):

```sh
grep -oE "require\(['\"][^'\"]+['\"]\)" spytial/suggest/_vendor/spytial-core-evaluator.js \
  | grep -vE "require\(['\"](\.|node:)" | sort -u
```

Pinned version: **spytial-core 3.2.1**.
