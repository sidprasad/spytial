# Vendored spytial-core evaluator

`spytial-core-evaluator.js` is the **self-contained** `./evaluator` build of
[`spytial-core`](https://github.com/sidprasad/spytial-core), copied verbatim from
the published npm tarball. It bundles its runtime deps (`graphlib`,
`simple-graph-query`, `lodash`) inline, so it requires only the Node `util`
builtin — no sibling `node_modules`.

It lets `spytial.suggest`'s tier-2 selector validation ([`../_eval.py`](../_eval.py))
run headlessly with just a `node` binary on the machine — no `npm install`, no
`SPYTIAL_CORE_NODE_PATH`. The self-contained build was introduced in
spytial-core 2.10.1 (tsup `noExternal`).

## Regenerate (when bumping the pinned spytial-core)

```sh
VERSION=2.10.1   # the spytial-core release to vendor
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

Pinned version: **spytial-core 2.10.1**.

> **Prototype note (branch `suggest-static-gate-repair`).** This vendored bundle is
> currently a **local dev build** of spytial-core (branch `suggest-surface-analyze-synth`,
> ahead of any release), not the published 2.10.1 tarball. The only delta is that the
> `./evaluator` entry now also re-exports `analyzeForgeExpression`, `synthesizeSelector`,
> and `synthesizeBinaryRelation` (the static analyzer + FOIL-style synthesizers), which
> the tier-2 bridge uses for the static gate / repair feedback. Before shipping: land that
> re-export in spytial-core, cut a release, and re-vendor from npm via the recipe above so
> this file matches a published version again.
