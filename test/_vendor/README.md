# Vendored spytial-core conformance harness

`spytial-check.js` is the `spytial-check` bin from
[`spytial-core`](https://github.com/sidprasad/spytial-core), copied verbatim out
of the published npm tarball. It reads case documents on stdin and writes a JSON
verdict on stdout, which is what [`../conformance.py`](../conformance.py) drives.

It is built self-contained, so it requires only the Node `child_process`, `fs`,
`path`, and `util` builtins — no sibling `node_modules`, no `npm install`. The
only requirement for running the conformance suite is a `node` binary.

## Why it is here and not in `spytial/`

It is a test dependency, and at ~3 MB it is four times the runtime evaluator
bundle. `MANIFEST.in` excludes `test/`, so keeping it here is what stops every
`pip install spytial_diagramming` from paying for a harness it will not run.

## Which release this is

`../../spytial/_vendor/VENDORED.json` records the version and a SHA-256 for this
file, and `test_spec_tables.py` checks both against the pin in
`spytial/core_assets.py`. The version is not restated here, because a pin written
in prose is a pin that goes stale silently. The bin also reports it directly:

```sh
node test/_vendor/spytial-check.js --version
```

## Regenerate

`./update-spytial-core.sh` re-vendors this file along with everything else, and
re-runs `scripts/vendor_lock.py`. It has to move with the same pin as the rest: a
harness from one release checking specs written against another is the drift the
vendoring exists to prevent, arriving through the thing meant to catch it.
