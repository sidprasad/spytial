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
feedback. The 3.0 style-system major left this entry's API unchanged, and so did
the 4.0 packaging major: 4.0 split the React components, the SQL evaluator, and
the a11y explorer out of the default entries, but `./evaluator` was already a
separate self-contained build and kept all seven symbols the bridge imports. Its
one internal change is CJS interop for `simple-graph-query`, which fixed named
imports under plain Node.

4.1.0 keeps that API too, but bumps the bundled `simple-graph-query` to 3.0, which
changes what an *unresolved name* means — so re-vendoring it changes query
semantics even though no symbol moved. In sgq 2.x an identifier that resolved to
nothing was silently reinterpreted as a string, which made `red` a string only
because nothing in the instance happened to be named `red`. In 3.0 it evaluates to
the empty relation and raises a warning; strings must be written as `"..."`
literals. The failure is quiet — an empty set satisfies a comparison vacuously, so
an unquoted right-hand side just makes the directive stop applying while the
diagram still renders. Every query in this repo was migrated to quoted literals
before this bundle landed (the selector `spytial.suggest` generates for enum
members quotes the member, see [`../rules.py`](../rules.py)). The warnings also
reach the browser: spytial-core 4.1.0 renders them as a dismissable
`⚠ n selector warnings` bar naming the offending decorator, and exposes them on
`layout.warnings` and a `layout-warnings` event.

## Regenerate (when bumping the pinned spytial-core)

```sh
VERSION=4.1.0   # the spytial-core release to vendor
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

Pinned version: **spytial-core 4.1.0**.
