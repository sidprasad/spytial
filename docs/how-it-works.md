# How It Works

`sPyTial` is a thin Python layer over a shared browser-side rendering engine. Understanding the split helps when you want to pin a version, work offline, or build your own host.

## The pipeline

```
Python object
  → relationalizer (turns the object into atoms + relations)
  → JSON data instance (the IJsonDataInstance format)
  → HTML page (loads spytial-core from a CDN)
  → spytial-core in the browser
      → evaluates constraints + directives
      → lays out a box-and-arrow diagram
```

The Python package handles steps 1–3: it walks your object, hands it to the matching relationalizer (see [Custom Relationalizers](relationalizers.md)), and emits a JSON payload plus a YAML spec of layout constraints. The HTML page it produces loads [`spytial-core`](https://github.com/sidprasad/spytial-core) from a CDN, which then does the actual rendering.

## What `spytial-core` is

[`spytial-core`](https://github.com/sidprasad/spytial-core) is the host-agnostic browser engine (TypeScript) that all sPyTial language bindings share:

- [`spytial-py`](https://github.com/sidprasad/spytial) — Python (this package)
- [`caraspace`](https://github.com/sidprasad/caraspace) — Rust
- [`spyret`](https://github.com/sidprasad/spyret-lang) — Pyret
- [`spytial-lean`](https://github.com/sidprasad/spytial-lean) — Lean

Each host serializes its own values into the same JSON data instance format, so the layout engine, constraint solver, and renderer are shared across languages.

## Version pinning

This release pins a specific `spytial-core` version. The pinned version is defined once in [`spytial/core_assets.py`](https://github.com/sidprasad/spytial/blob/main/spytial/core_assets.py), and the CDN URL it builds looks like:

```
https://cdn.jsdelivr.net/npm/spytial-core@<version>/dist/browser/spytial-core-complete.global.js
```

To read the version at runtime:

```python
from spytial.core_assets import get_spytial_core_version
print(get_spytial_core_version())
```

When `spytial-core` is upgraded, that constant is bumped and a new sPyTial release is cut.

## What this means for you

- **No extra install.** You only `pip install spytial-diagramming`. The browser bundle is fetched from the CDN the first time a diagram is rendered, then cached by the browser.
- **First render needs network access.** Once the bundle is cached, rendering works offline. For air-gapped or reproducibility-sensitive workflows, fetch the pinned CDN URL once and serve it locally.
- **The JSON format is `spytial-core`'s `IJsonDataInstance`.** If you want to drive the engine from a non-Python host, or write tests that bypass Python entirely, the data format is documented in [`spytial-core`](https://github.com/sidprasad/spytial-core)'s docs.
