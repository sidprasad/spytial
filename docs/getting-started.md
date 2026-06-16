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

!!! tip "Don't want to install yet?"
    The [**Playground**](playground/index.html) runs this exact example in your
    browser. Come back here when you want to run it locally.

## Your first diagram — a binary tree

Copy this whole block into a `.py` file or a notebook cell and run it. It defines a
binary tree, says how it should be laid out, and draws an instance. We walk through
what each decorator does just below.

<!-- canonical example — keep in sync with docs/index.md and the playground -->
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

Running a script opens the diagram in a new browser tab; running it in a notebook
renders it inline. You'll see `10` at the root, `5` below-left and `15`
below-right, and their children beneath them.

### What each decorator does

The decorators *are* the sPyTial layout — each is one rule. Reading top to bottom:

| Decorator | What it does |
| --- | --- |
| `@orientation(selector='{ x : TreeNode, y : TreeNode \| x.left = y }', directions=['below','left'])` | Place each node's left child **below and to the left**. The selector matches the pairs `(x, y)` where `y` is `x`'s left child — i.e. the left-child edges. |
| `@orientation(selector='{ x, y : TreeNode \| x.right = y }', directions=['below','right'])` | The mirror image, for the right child. |
| `@attribute(field='value')` | Render `node.value` as text **inside** the node, instead of as a separate box with an arrow. |
| `@hideAtom(selector='NoneType')` | Hide the empty `None` leaves. |
| `@flag(name="hideDisconnected")` | Drop any atom left with no edges, keeping the picture tidy. |

The `selector` strings are sPyTial's **relational query language**. The
`{ x : T, y : T | … }` form matches *pairs* of atoms (here, parent-and-child edges);
see [Selectors](selectors.md) for a Python-oriented guide to the syntax.

!!! note "Build it up incrementally"
    A good workflow is to call `diagram(obj)` first with **no** decorators to see
    the raw structure, then add one rule at a time. The
    [Playground](playground/index.html) is the fastest place to do this — edit,
    run, repeat.

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

- Try the [Playground](playground/index.html) — edit and run sPyTial in your browser.
- Read [Diagramming](usage/diagramming.md) for the main rendering workflow.
- Read [Operations](operations.md) for every layout constraint and drawing directive.
- Read the [Evaluator](usage/evaluator.md) guide for inspecting serialized data.
- Read [How It Works](how-it-works.md) to understand the Python → browser pipeline.
- Browse [CLRS Notebook Examples](examples/spytial-clrs.md) for worked examples on
  classic data structures (heaps, trees, graphs, hash tables, disjoint-set forests).

- **PyPI:** [pypi.org/project/spytial-diagramming](https://pypi.org/project/spytial-diagramming/)
- **Source:** [github.com/sidprasad/spytial](https://github.com/sidprasad/spytial)
