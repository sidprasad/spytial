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

This site focuses on using sPyTial:

- installation and first steps
- diagramming and evaluation
- operations and custom relationalizers
- worked examples drawn from classic data structures

## Using `spytial-clrs` as the examples repo

The sibling [`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) repository is the best source of worked examples for this package. It contains CLRS-style notebooks for linked lists, heaps, trees, graphs, disjoint sets, and memoization tables.

- It gives you larger, more realistic examples than small `dict` and `list` snippets.
- It shows how sPyTial can be used to explain common data structures visually.
- It is a good place to browse if you want inspiration for your own diagrams.

Start with [Getting Started](getting-started.md), then move to [Diagramming](usage/diagramming.md) or [CLRS Examples](examples/spytial-clrs.md).
