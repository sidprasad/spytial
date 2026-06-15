# sPyTial

**Spatial diagrams of Python objects.** sPyTial turns structured Python data into box-and-arrow diagrams whose layout is driven by declarative spatial constraints. It is aimed at cases where the structure matters more than the UI: debugging recursive objects, teaching data structures, inspecting serialized state, or building small visual tools around Python models.

## What you can do with it

- Render any Python object — `dict`, `list`, dataclass, custom class, graph — as a box-and-arrow diagram.
- Control layout declaratively with constraints (`orientation`, `align`, `cyclic`, `group`) and directives (`atomColor`, `attribute`, `hideAtom`, `tag`, `inferredEdge`, …).
- Step through sequences of states to visualize how a data structure evolves.

!!! tip "Try it now, no install"
    The [**Playground**](playground.md) loads this exact binary search tree in an
    in-browser editor — open it to tweak the code and watch the diagram update live.

## Hello, sPyTial

A complete, copy-paste-runnable example — the binary search tree from the
[`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) notebooks. The
decorators *are* the "sPyTial layout": they turn the default box-and-arrow graph
into the tree shape you have in mind.

<!-- canonical example — keep in sync with docs/getting-started.md and the BST playground preset -->
```python
from spytial import attribute, orientation, hideAtom, hideField, diagram

@attribute(field="key")                                          # show `key` inside the node
@orientation(selector='left & (BSTNode -> (BSTNode - NoneType.~key))',
             directions=['below', 'left'])                       # real left child: below-left
@orientation(selector='right & (BSTNode -> (BSTNode - NoneType.~key))',
             directions=['below', 'right'])                      # real right child: below-right
class BSTNode:
    def __init__(self, key=None, left=None, right=None, parent=None):
        self.key = key
        self.left = left
        self.right = right
        self.parent = parent

BST_NIL = BSTNode(key=None)                                      # shared NIL sentinel
BST_NIL.left = BST_NIL.right = BST_NIL.parent = BST_NIL

@hideAtom(selector='{ x : BSTNode | (x.key in NoneType) } + BSTree + int + NoneType')
@hideField(field='parent')
class BSTree:
    def __init__(self):
        self.root = BST_NIL

    def insert(self, k):                                         # CLRS TREE-INSERT
        z = BSTNode(key=k, left=BST_NIL, right=BST_NIL, parent=None)
        y, x = BST_NIL, self.root
        while x is not BST_NIL:
            y = x
            x = x.left if z.key < x.key else x.right
        z.parent = y
        if y is BST_NIL:    self.root = z
        elif z.key < y.key: y.left = z
        else:               y.right = z
        return z

t = BSTree()
for k in [15, 6, 18, 17, 20, 3, 7, 13, 9, 2, 4]:
    t.insert(k)

diagram(t)
```

**→ [Install and walk through this example, line by line (Getting Started)](getting-started.md)**
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
