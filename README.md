# sPyTial: Lightweight Diagrams for Structured Python Data

[![PyPI version](https://img.shields.io/pypi/v/spytial-diagramming.svg)](https://pypi.org/project/spytial-diagramming/)
[![Python versions](https://img.shields.io/pypi/pyversions/spytial-diagramming.svg)](https://pypi.org/project/spytial-diagramming/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/sidprasad/spytial/actions/workflows/ci.yml/badge.svg)](https://github.com/sidprasad/spytial/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-blue.svg)](https://sidprasad.github.io/spytial/)

```bash
pip install spytial-diagramming
```

**Docs:** https://sidprasad.github.io/spytial/ — start with [Getting Started](https://sidprasad.github.io/spytial/getting-started/) for install, badges, and your first diagram.

---

Sometimes you just want to see your data.

You're working with a tree, a graph, a recursive object — maybe an AST, a neural network, or a symbolic term. You don't need an interactive dashboard or a production-grade visualization system. You just need a diagram that lays it out clearly so you can understand what's going on.

That's what `sPyTial` is for. It is designed for developers, educators, and researchers who work with structured data and need to make that structure visible — to themselves or to others — with minimal effort.

## Why spatial layout

Spatial arrangement helps people understand structure: when elements are grouped, aligned, and oriented meaningfully, patterns and errors become easier to see. `sPyTial` gives you that layout **by default** — the diagram reflects how the parts are connected, not how they happen to be stored.

You get:
- a **box-and-arrow diagram** that shows the shape of your data
- a layout driven by declarative constraints (`orientation`, `align`, `cyclic`, `group`)
- a tool that flags when a constraint can't be satisfied

## Quick start

```python
import spytial

data = {
    "name": "root",
    "children": [
        {"value": 1},
        {"value": 2},
        {"value": 3},
    ],
}

# Opens in a browser tab, or inline in a Jupyter notebook.
spytial.diagram(data)

# Or save to a file:
spytial.diagram(data, method="file")
```

For stepping through sequences of states, custom relationalizers, and annotation-driven layouts, see the [docs](https://sidprasad.github.io/spytial/).

## Related projects

- **[`spytial-clrs`](https://github.com/sidprasad/spytial-clrs)** — a Jupyter notebook collection that implements the data structures from the CLRS algorithms textbook (Cormen, Leiserson, Rivest, Stein) using sPyTial: heaps, linked lists, hash tables, BST / red-black / B / van Emde Boas trees, disjoint-set forests, graphs with MST and SCC views, and more. The best place to see sPyTial on realistic structures.
- **[`spytial-core`](https://github.com/sidprasad/spytial-core)** — the browser-side rendering engine sPyTial uses under the hood. Shared across all sPyTial language hosts (Python, Rust, Pyret, Lean).

## License

MIT — see [LICENSE](LICENSE).
