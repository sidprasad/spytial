# Released core assets

`spytial-check.js` is copied unchanged from `dist/cli/spytial-check.js` in the
published spytial-core npm package. It checks a datum and a spec and reports
spatial assertions through a JSON stdin/stdout protocol. Only Node is needed;
the bundle has no external npm dependencies.

Suggest's Python comparison strategy and the integration tests share this
checker through `spytial._conformance`. No comparison or example-selection
strategy is added to core.

Interactive sessions keep the released CLI's exported `main` function loaded in
one Node worker. The adapter supplies a case file and captures its JSON result;
Python supervises request timeouts. This avoids reloading the bundle for each
generated datum. The copied CLI remains unchanged.

`VENDORED.json` records the release and SHA-256 of each asset. The harness also
reports its version with `node spytial/_vendor/spytial-check.js --version`.
`./update-spytial-core.sh` updates the checker, evaluator, language manifest,
schema, and browser pin together and regenerates the lockfile.
