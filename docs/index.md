# sPyTial

<p class="sp-tagline"><strong>Spatial diagrams of Python objects.</strong> Turn any dict, dataclass, tree, or graph into a box-and-arrow diagram — and shape the layout with a few declarative decorators.</p>

[Get started](getting-started.md){ .md-button .md-button--primary }
[Try it in your browser](playground/index.html){ .md-button }

<div class="sp-hero" markdown="1">

<div class="sp-code" markdown="1">

```python
from spytial import attribute, orientation, hideAtom, hideField, diagram

@attribute(field="key")                      # show `key` inside each node
@orientation(selector='left & (BSTNode -> (BSTNode - NoneType.~key))',
             directions=['below', 'left'])    # real left child: below-left
@orientation(selector='right & (BSTNode -> (BSTNode - NoneType.~key))',
             directions=['below', 'right'])   # real right child: below-right
class BSTNode:
    def __init__(self, key=None, left=None, right=None, parent=None):
        self.key = key
        self.left = left
        self.right = right
        self.parent = parent

BST_NIL = BSTNode(key=None)                   # one shared NIL sentinel
BST_NIL.left = BST_NIL.right = BST_NIL.parent = BST_NIL

@hideAtom(selector='{ x : BSTNode | (x.key in NoneType) } + BSTree + int + NoneType')
@hideField(field='parent')                    # don't draw parent back-pointers
class BSTree:
    def __init__(self):
        self.root = BST_NIL

    def insert(self, k):                       # CLRS TREE-INSERT
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

</div>

<div class="sp-viz">
  <iframe src="assets/hero-tree.html" title="A binary tree rendered by sPyTial" loading="lazy"></iframe>
  <div class="sp-cap">↑ The real, live output of the code above (a binary search tree) — drag to explore, scroll to zoom</div>
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

- [Playground](playground/index.html) — edit and run sPyTial in your browser.
- [Getting Started](getting-started.md) — install and a walkthrough.
- [Operations](operations.md) — every constraint and directive.
- [How It Works](how-it-works.md) — the Python → browser pipeline.
- [`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) — more examples: CLRS data structures rendered with sPyTial.
