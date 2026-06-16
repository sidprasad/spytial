# Spytial

<p class="sp-tagline"><strong>Spatial diagrams of Python objects.</strong> Turn any dict, dataclass, tree, or graph into a box-and-arrow diagram — and shape the layout with a few declarative decorators.</p>

[Get started](getting-started.md){ .md-button .md-button--primary }
[Try it in your browser](playground/index.html){ .md-button }

<div class="sp-hero" markdown="1">

<div class="sp-code" markdown="1">

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

</div>

<div class="sp-viz">
  <iframe src="assets/hero-tree.html" title="A binary tree rendered by Spytial" loading="lazy"></iframe>
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

## More

- [Playground](playground/index.html) — edit and run Spytial in your browser.
- [Getting Started](getting-started.md) — install and a walkthrough.
- [Operations](operations.md) — every constraint and directive.
- [How It Works](how-it-works.md) — the Python → browser pipeline.
- [`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) — more examples: CLRS data structures rendered with Spytial.
