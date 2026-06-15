# Getting Started

[![PyPI version](https://img.shields.io/pypi/v/spytial-diagramming.svg)](https://pypi.org/project/spytial-diagramming/)
[![Python versions](https://img.shields.io/pypi/pyversions/spytial-diagramming.svg)](https://pypi.org/project/spytial-diagramming/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/sidprasad/spytial/blob/main/LICENSE)
[![CI](https://github.com/sidprasad/spytial/actions/workflows/ci.yml/badge.svg)](https://github.com/sidprasad/spytial/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-blue.svg)](https://sidprasad.github.io/spytial/)

## Install

```bash
pip install spytial-diagramming
```

That's it — no browser extension, no separate renderer, no config. Supported on
Python 3.8 – 3.12.

!!! tip "Don't want to install yet?"
    The [**Playground**](playground.md) runs this exact example in your browser.
    Come back here when you want to run it locally.

## Your first diagram — a complete example

This is the binary search tree from the [`spytial-clrs`](https://github.com/sidprasad/spytial-clrs)
notebook collection. Copy the whole block into a `.py` file (or a notebook cell)
and run it — it builds a BST and draws it as a box-and-arrow diagram.

<!-- canonical example — keep in sync with docs/index.md and the BST playground preset -->
```python
from spytial import attribute, orientation, hideAtom, hideField, diagram

# --- The layout: how a tree node should be drawn ---
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

# A single shared NIL sentinel that every empty child points to.
BST_NIL = BSTNode(key=None)
BST_NIL.left = BST_NIL.right = BST_NIL.parent = BST_NIL

@hideAtom(selector='{ x : BSTNode | (x.key in NoneType) } + BSTree + int + NoneType')  # hide the NIL/plumbing
@hideField(field='parent')                                       # don't draw parent back-pointers
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

# --- An example instance ---
t = BSTree()
for k in [15, 6, 18, 17, 20, 3, 7, 13, 9, 2, 4]:
    t.insert(k)

# --- Draw it ---
diagram(t)
```

Running a script opens the diagram in a new browser tab; running it in a notebook
renders it inline. You'll see `15` at the root, with smaller keys branching
below-left and larger keys below-right.

### What each line is doing

sPyTial draws **any** Python object out of the box — even `diagram(t)` with no
decorators gives you a labelled box-and-arrow graph. The decorators are how you
turn that default graph into the tree *shape* you have in mind:

| Decorator | Effect |
| --- | --- |
| `@attribute(field="key")` | Render `node.key` as text **inside** the node instead of as a separate box. |
| `@orientation(selector="left & …", directions=["below", "left"])` | Place each node's real left child **below and to the left**. |
| `@orientation(selector="right & …", directions=["below", "right"])` | Mirror it for the right child. |
| `@hideField(field="parent")` | Don't draw the `parent` back-pointers. |
| `@hideAtom(selector="…")` | Hide the shared `NIL` sentinel and bare `int`/`None` atoms so only keyed nodes show. |

The `selector` strings are sPyTial's relational query language — here they isolate
the *real* child edges from the shared `NIL` sentinel so leaves stay tidy. You
rarely need anything that elaborate: for a plain tree, `selector="left"` already
works. See [Operations](operations.md) for the full selector syntax.

!!! note "Start small, then annotate"
    A good workflow is: call `diagram(obj)` first to see the raw structure, then add
    one decorator at a time. The [Playground](playground.md) is the fastest place to
    do this — edit, run, repeat.

## Where the diagram shows up

`sPyTial` works in three places without any configuration:

| Where you run it | Default output |
| --- | --- |
| Jupyter / IPython notebook | Inline HTML |
| Script / REPL | Opens a new browser tab |
| Anywhere, on demand | Writes an HTML file |

You can always force one explicitly:

```python
import spytial

spytial.diagram(t, method="browser")   # open a new tab
spytial.diagram(t, method="file")      # save spytial_visualization.html
spytial.diagram(t, method="inline")    # force inline (notebook) output
```

The actual rendering is done in the browser by
[`spytial-core`](how-it-works.md), loaded from a CDN the first time you render.
There is nothing extra to install; the bundle is cached after first load. See
[How It Works](how-it-works.md) for the pipeline and offline/pinning guidance.

## Inspect before you diagram

If you want to confirm exactly how an object is being serialized into atoms and
relations — useful when debugging a custom class or annotation — use the
[evaluator](usage/evaluator.md):

```python
import spytial

spytial.evaluate(t)
```

## Optional extras

Most users do not need these. Install them only if you hit one of the listed cases.

```bash
pip install "spytial-diagramming[widget]"     # anywidget-based Jupyter widget mode
pip install "spytial-diagramming[headless]"   # Selenium-driven headless rendering for benchmarking
pip install "spytial-diagramming[dev]"        # pytest, flake8, black (contributors)
pip install "spytial-diagramming[docs]"       # mkdocs + plugins (contributors)
```

- `[headless]` also requires a Chrome / Chromedriver installation on `PATH`. See
  [Diagramming → Headless benchmarking](usage/diagramming.md#headless-benchmarking).

## Next steps

- Try the [Playground](playground.md) — edit and run examples in your browser.
- Read [Diagramming](usage/diagramming.md) for the main rendering workflow.
- Read [Operations](operations.md) for every layout constraint and drawing directive.
- Read the [Evaluator](usage/evaluator.md) guide for inspecting serialized data.
- Read [How It Works](how-it-works.md) to understand the Python → browser pipeline.
- Browse [CLRS Notebook Examples](examples/spytial-clrs.md) for worked examples on
  classic data structures (heaps, trees, graphs, hash tables, disjoint-set forests).

- **PyPI:** [pypi.org/project/spytial-diagramming](https://pypi.org/project/spytial-diagramming/)
- **Source:** [github.com/sidprasad/spytial](https://github.com/sidprasad/spytial)
