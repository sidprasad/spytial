# Browser assets

These are the already-minified browser renderer, React components, and component
CSS copied verbatim from the pinned `spytial-core` npm release. `package.json` is
the upstream package metadata, including its version and license declaration;
dependency license notices remain intact in the bundles. Source maps are omitted.

`../VENDORED.json` records the release and SHA-256 of every copied artifact.
`spytial/core_assets.py` selects embedded, locally served, or pinned-CDN delivery.
Do not edit these generated files or download a CDN-generated `.min.js` variant.

From the repository root:

```sh
./update-spytial-core.sh                     # latest published npm release
./update-spytial-core.sh --version 6.6.0     # exact release; also repairs this version
./update-spytial-core.sh --tarball /path/to/spytial-core-6.6.0.tgz  # offline
./update-spytial-core.sh --check             # no download or changes
python scripts/vendor_lock.py --wheel dist/spytial_diagramming-*.whl
```

The updater reads all required files from one tarball and validates the package,
manifest, schema, and generated language tables before changing the checkout.
Every invocation refreshes the complete inventory, even if the version is already
pinned. Failed downloads, missing artifacts, or unsupported language changes leave
the current installation untouched. npm and Python are needed for online updates;
an existing tarball needs only Python. Runtime rendering never invokes npm.

After updating, review the diff and run `python -m pytest`. When the core version
changes, review and regenerate `test/api_baseline.json` with
`python scripts/generate_api_baseline.py`. The updater leaves that baseline for
review so it cannot silently accept a public API change.
