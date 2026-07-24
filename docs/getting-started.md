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

!!! tip "Try it without installing"
    The [**Playground**](playground/index.html) runs this exact example in the
    browser. Return here to run it locally.

## A first diagram: a binary tree

Copy this block into a `.py` file or a notebook cell and run it. The block
defines a binary tree, states how the tree is laid out, and draws one instance.
Each decorator is described below.

<!-- canonical example: keep in sync with docs/index.md and the playground -->
```python
from spytial import orientation, attribute, hideAtom, flag, diagram

@orientation(selector='{ x : TreeNode, y : TreeNode | x.left = y }', directions=['below', 'left'])
@orientation(selector='{ x : TreeNode, y : TreeNode | x.right = y }', directions=['below', 'right'])
@attribute(field='value')
@hideAtom(selector='NoneType')
@flag(name="hideDisconnected")
class TreeNode:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right

root = TreeNode(
    value=10,
    left=TreeNode(value=5, left=TreeNode(3), right=TreeNode(7)),
    right=TreeNode(value=15, left=TreeNode(12), right=TreeNode(18)),
)

diagram(root)
```

A script opens the diagram in a new browser tab. A notebook renders it inline.
The output shows `10` at the root, `5` below-left, `15` below-right, and their
children below them.

### What each decorator does

The decorators *are* the Spytial layout. Each decorator is one rule. The table
reads from top to bottom:

| Decorator | What it does |
| --- | --- |
| `@orientation(selector='{ x : TreeNode, y : TreeNode \| x.left = y }', directions=['below','left'])` | Place each node's left child **below and to the left**. The selector matches the pairs `(x, y)` where `y` is the left child of `x`. These are the left-child edges. |
| `@orientation(selector='{ x : TreeNode, y : TreeNode \| x.right = y }', directions=['below','right'])` | The mirror image, for the right child. |
| `@attribute(field='value')` | Render `node.value` as text **inside** the node, instead of as a separate box with an arrow. |
| `@hideAtom(selector='NoneType')` | Hide the empty `None` leaves. |
| `@flag(name="hideDisconnected")` | Drop any atom that has no edges, to keep the picture tidy. |

The `selector` strings are Spytial's **relational query language**. The
`{ x : T, y : T | … }` form matches *pairs* of atoms, here the parent-and-child
edges. See [Selectors](selectors.md) for a Python-oriented guide to the syntax.

!!! note "Build it up incrementally"
    A good workflow is to call `diagram(obj)` first with **no** decorators, to
    see the raw structure. Then add one rule at a time. The
    [Playground](playground/index.html) is the fastest place to do this: edit,
    run, and repeat.

## Where the diagram shows up

`Spytial` works in three places without any configuration:

| Where it runs | Default output |
| --- | --- |
| Jupyter or IPython notebook | Inline HTML |
| Script or REPL | Opens a new browser tab |
| Anywhere, on demand | Writes an HTML file |

One output method can be forced explicitly:

```python
import spytial

spytial.diagram(t, method="browser")   # open a new tab
spytial.diagram(t, method="file")      # save spytial_visualization.html
spytial.diagram(t, method="inline")    # force inline (notebook) output
```

The browser does the actual rendering, through
[`spytial-core`](https://github.com/sidprasad/spytial-core). This bundle loads
from a CDN on the first render. Nothing extra is installed, and the bundle is
cached after the first load.

## Inspect before diagramming

To confirm exactly how an object is serialized into atoms and relations, use the
[evaluator](usage/evaluator.md). This is useful when debugging a custom class or
annotation:

```python
import spytial

spytial.evaluate(t)
```


## Next steps

- Try the [Playground](playground/index.html) to edit and run Spytial in the
  browser.
- Read [Diagramming](usage/diagramming.md) for the main rendering workflow.
- Read [Operations](operations.md) for every layout constraint and drawing
  directive.
- Read the [Evaluator](usage/evaluator.md) guide to inspect serialized data.
- Browse [CLRS Notebook Examples](examples/spytial-clrs.md) for worked examples
  on classic data structures (heaps, trees, graphs, hash tables, and
  disjoint-set forests).

- **PyPI:** [pypi.org/project/spytial-diagramming](https://pypi.org/project/spytial-diagramming/)
- **Source:** [github.com/sidprasad/spytial](https://github.com/sidprasad/spytial)
