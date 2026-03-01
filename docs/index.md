# sPyTial

sPyTial turns Python objects into box-and-arrow diagrams backed by Spytial's layout engine. It is aimed at cases where the structure matters more than the UI: debugging recursive objects, teaching data structures, inspecting serialized state, or building small visual tools around Python models.

## Install

```bash
pip install spytial-diagramming
```

## Quick start

```python
import spytial

tree = {
    "name": "root",
    "children": [
        {"name": "left"},
        {"name": "right"},
    ],
}

spytial.diagram(tree)
```

## What lives in this site

This documentation is split into two tracks:

- **Use sPyTial** covers installation, diagramming, evaluation, operations, the dataclass builder, and custom relationalizers.
- **Develop sPyTial** explains how the Python package is organized, how it bridges to `spytial-core`, and how the docs site is built and deployed.

## Using `spytial-clrs` as the examples repo

The sibling [`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) repository is the best source of worked examples for this package. It contains CLRS-style notebooks for linked lists, heaps, trees, graphs, disjoint sets, and memoization tables. In practice it serves three roles:

- a tutorial gallery for user-facing docs
- a source of screenshots and notebook snippets
- a regression corpus for checking that common data-structure patterns still render cleanly

Start with [Getting Started](getting-started.md) if you want to use the library, or [Develop sPyTial](development/index.md) if you want to work on the package itself.
