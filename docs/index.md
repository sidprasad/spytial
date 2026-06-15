# sPyTial

**Spatial diagrams of Python objects.** sPyTial turns structured Python data into box-and-arrow diagrams whose layout is driven by declarative spatial constraints. It is aimed at cases where the structure matters more than the UI: debugging recursive objects, teaching data structures, inspecting serialized state, or building small visual tools around Python models.

## What you can do with it

- Render any Python object — `dict`, `list`, dataclass, custom class, graph — as a box-and-arrow diagram.
- Control layout declaratively with constraints (`orientation`, `align`, `cyclic`, `group`) and directives (`atomColor`, `attribute`, `hideAtom`, `tag`, `inferredEdge`, …).
- Step through sequences of states to visualize how a data structure evolves.

!!! tip "Try it now, no install"
    The [**Playground**](playground.md) loads this exact binary tree in an
    in-browser editor — open it to tweak the code and watch the diagram update live.

## Hello, sPyTial

A complete, copy-paste-runnable example: define a binary tree, describe how it
should be laid out, and draw an instance. The four decorators *are* the "sPyTial
layout" — each is one rule that turns the default box-and-arrow graph into a tree.

<!-- canonical example — keep in sync with docs/getting-started.md and the playground preset -->
```python
import spytial

@spytial.orientation(selector="left",  directions=["below", "left"])   # place the `left` child below-left
@spytial.orientation(selector="right", directions=["below", "right"])  # place the `right` child below-right
@spytial.attribute(field="value")                                      # show `value` as a label inside the node
@spytial.hideAtom(selector="NoneType")                                 # hide the empty (None) leaves
class Node:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right

# A small binary tree, built by hand.
root = Node(4,
            Node(2, Node(1), Node(3)),
            Node(6, Node(5), Node(7)))

spytial.diagram(root)
```

**→ [Walk through this example one annotation at a time (Getting Started)](getting-started.md)**
&nbsp;·&nbsp; **[Run it in your browser (Playground)](playground.md)**

## The sPyTial ecosystem

sPyTial is part of a small family of projects. Most users only need the first.

- **`spytial-py`** (this package) — the Python host. Install with `pip install spytial-diagramming`. Exposes `diagram()`, `evaluate()`, decorators and types for annotating layouts, and a relationalizer plug-in system.
- **[`spytial-core`](https://github.com/sidprasad/spytial-core)** — the browser-side rendering engine (TypeScript). Loaded automatically from a CDN; you do not install it yourself. The same engine is used by every sPyTial language host (Python, Rust, Pyret, Lean). See [How It Works](how-it-works.md) for the pipeline.
- **[`spytial-clrs`](https://github.com/sidprasad/spytial-clrs)** — a Jupyter notebook collection that implements the data structures from the **CLRS algorithms textbook** (Cormen, Leiserson, Rivest, Stein) using sPyTial: heaps, stacks, queues, linked lists, hash tables, BST / red-black / B / van Emde Boas / interval trees, Huffman codes, disjoint-set forests, graphs with MST and SCC views. It is the best place to see the package on realistic structures. Ships with a Docker image and a JupyterLite deployment for zero-install browsing.

## Where to go next

- [Playground](playground.md) — edit and run sPyTial in your browser, no install.
- [Getting Started](getting-started.md) — install, then a line-by-line walkthrough of the example above.
- [Diagramming](usage/diagramming.md) — the main rendering workflow.
- [Operations](operations.md) — constraints and directives.
- [How It Works](how-it-works.md) — the Python → browser pipeline and `spytial-core`.
- [CLRS Notebook Examples](examples/spytial-clrs.md) — worked examples on classic data structures.
