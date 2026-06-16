# sPyTial

<p class="sp-tagline"><strong>Spatial diagrams of Python objects.</strong> Turn any dict, dataclass, tree, or graph into a box-and-arrow diagram — and shape the layout with a few declarative decorators.</p>

[Get started](getting-started.md){ .md-button .md-button--primary }
[Try it in your browser](playground/index.html){ .md-button }

<div class="sp-hero" markdown="1">

<div class="sp-code" markdown="1">

```python
import spytial

@spytial.orientation(selector="left",  directions=["below", "left"])
@spytial.orientation(selector="right", directions=["below", "right"])
@spytial.attribute(field="value")
@spytial.hideAtom(selector="NoneType")
class Node:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right

root = Node(4, Node(2, Node(1), Node(3)),
               Node(6, Node(5), Node(7)))

spytial.diagram(root)
```

</div>

<div class="sp-viz">
  <iframe src="assets/hero-tree.html" title="A binary tree rendered by sPyTial" loading="lazy"></iframe>
  <div class="sp-cap">↑ The real, live output of the code above — drag to explore, scroll to zoom</div>
</div>

</div>

## Get started in three steps

1. **Install** — `pip install spytial-diagramming` (Python 3.8–3.12, nothing else to set up).
2. **Decorate** — add layout rules to your class with decorators like `@orientation` and `@attribute`.
3. **Draw** — call `spytial.diagram(obj)`. It opens in your browser, or renders inline in a notebook.

That's the whole loop. [Walk through the example above, line by line →](getting-started.md)

## Operations at a glance

Layout is controlled by two kinds of operation. Attach them as class decorators
(`@spytial.orientation(...)`), to individual objects, or via `typing.Annotated`.
Full details and arguments are in [Operations](operations.md).

<div class="sp-ops" markdown="1">

<div markdown="1">

**Constraints** — shape the geometry

| Operation | What it does |
| --- | --- |
| `orientation` | Place a field's target in a direction (`below`, `left`, …) |
| `align` | Line selected nodes up on a shared axis |
| `cyclic` | Arrange selected nodes in a ring |
| `group` | Enclose selected nodes in a labelled region |

</div>

<div markdown="1">

**Directives** — change how things are drawn

| Operation | What it does |
| --- | --- |
| `attribute` | Show a field as a label inside the node |
| `atomColor` · `edgeColor` | Color nodes / edges |
| `hideAtom` · `hideField` | Hide nodes / fields |
| `tag` | Add a computed label to matching nodes |
| `inferredEdge` | Draw a derived edge between nodes |
| `size` · `icon` | Resize / icon-ify nodes |

</div>

</div>

## What it's good for

- **Debugging** recursive or linked structures — see the shape, not a `repr`.
- **Teaching** data structures — trees, heaps, graphs, hash tables.
- **Inspecting** serialized state, ORM objects, protobufs, nested config.
- **Stepping through** how a structure evolves, with [sequences](usage/sequences.md).

## The sPyTial ecosystem

Most users only need the first.

- **`spytial-diagramming`** (this package) — the Python host: `diagram()`, `evaluate()`, the decorators, and a relationalizer plug-in system.
- **[`spytial-core`](https://github.com/sidprasad/spytial-core)** — the browser-side rendering engine (TypeScript), loaded from a CDN. The same engine powers every sPyTial host (Python, Rust, Pyret, Lean). See [How It Works](how-it-works.md).
- **[`spytial-clrs`](https://github.com/sidprasad/spytial-clrs)** — Jupyter notebooks implementing CLRS-textbook data structures with sPyTial: heaps, trees, hash tables, disjoint sets, graphs, and more. The best place to see it on realistic structures.

## Where to go next

- [Playground](playground/index.html) — edit and run sPyTial in your browser, no install.
- [Getting Started](getting-started.md) — install, then a line-by-line walkthrough.
- [Operations](operations.md) — every layout constraint and drawing directive.
- [How It Works](how-it-works.md) — the Python → browser pipeline.
- [CLRS Notebook Examples](examples/spytial-clrs.md) — worked examples on classic data structures.
