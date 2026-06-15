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

## Your first diagram: a binary tree, step by step

We'll build up a binary tree diagram one annotation at a time, so you can see
exactly what each one does. Step 1 is a complete program; steps 2–4 show just the
decorator you add at each stage, and the full runnable version is at the end.

### 1. Start with plain Python

Define a binary tree node — nothing sPyTial-specific yet — and ask sPyTial to
draw an instance:

```python
import spytial

class Node:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right

root = Node(4,
            Node(2, Node(1), Node(3)),
            Node(6, Node(5), Node(7)))

spytial.diagram(root)
```

`spytial.diagram()` draws **any** object, so this already works. But with no
layout rules you get a *generic* box-and-arrow graph: each `value`, `left`, and
`right` is its own box joined by labelled arrows, placed wherever it happens to
fit. The next three steps shape that into a tree.

### 2. Lay the children out — `@orientation`

```python
@spytial.orientation(selector="left",  directions=["below", "left"])   # the `left` child goes below-left
@spytial.orientation(selector="right", directions=["below", "right"])  # the `right` child goes below-right
class Node:
    ...
```

`orientation` is a layout **constraint**. `selector="left"` picks the `left`
field; `directions=["below", "left"]` says "place whatever that field points to
*below* its owner and offset to the *left*." Add the mirror rule for `right` and
parents now sit above their children — the graph reads top-down like a tree.

### 3. Put the value inside the node — `@attribute`

```python
@spytial.attribute(field="value")   # draw `value` as text inside the node
```

By default `value` is a separate box with an arrow pointing at it. `attribute`
folds the field *into* its owner as a text label, so each node simply shows its
number. (`attribute` is a **directive** — it changes how things are drawn, not
where.)

### 4. Hide the empty leaves — `@hideAtom`

```python
@spytial.hideAtom(selector="NoneType")   # don't draw the None children
```

A leaf's `left`/`right` are `None`, and without this every `None` shows up as an
empty box. `hideAtom` removes atoms matching a selector — here, everything of
type `NoneType` — so the leaves stay clean.

### The complete example

Putting all four rules together. Copy this into a `.py` file or a notebook cell
and run it:

<!-- canonical example — keep in sync with docs/index.md and the playground preset -->
```python
import spytial

# Each decorator below is one rule for how the tree is drawn.
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

Running a script opens the diagram in a new browser tab; running it in a notebook
renders it inline. You'll see `4` at the root, `2` and `6` below it, and their
children fanning out beneath them.

!!! note "Selectors can do much more"
    Here `selector` just names a field (`"left"`) or a type (`"NoneType"`). For
    bigger structures it's a small relational query language — see
    [Operations](operations.md) for the full syntax, and the
    [`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) notebooks for how
    a real CLRS binary search tree uses it.

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

spytial.diagram(root, method="browser")   # open a new tab
spytial.diagram(root, method="file")      # save spytial_visualization.html
spytial.diagram(root, method="inline")    # force inline (notebook) output
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

spytial.evaluate(root)
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
