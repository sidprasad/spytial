# Operations

Operations are the rules that shape a diagram. Each is one **constraint** or
**directive** you attach to a class (or an object). They are declarative and
order-independent — every rule narrows the set of acceptable layouts, turning the
raw [value graph](how-it-works.md) into the picture you want.

- **Constraints** shape the geometry — *where* things go.
- **Directives** change the drawing — *how* things look.

Almost every operation is built from a **`selector`** — which atoms or edges it
applies to (see [Selectors](selectors.md)) — plus a few operation-specific
arguments. The sections below break each one into its parts.

## Constraints

### `orientation` — place a target in a direction

1. **`selector`** — the edges to orient.
2. **`directions`** — where the target sits relative to its source, as a list
   (e.g. `['below', 'left']`). Common values: `above`, `below`, `left`, `right`,
   and the adjacency variants `directlyLeft` / `directlyRight`.

```python
@spytial.orientation(
    selector='{ x : TreeNode, y : TreeNode | x.left = y }',  # which edges
    directions=['below', 'left'],                            # where the child goes
)
```

### `align` — line atoms up on a shared axis

1. **`selector`** — the atoms to align.
2. **`direction`** — the axis to share.

### `cyclic` — arrange atoms in a ring

1. **`selector`** — the atoms/edges forming the cycle.
2. **`direction`** — which way the ring runs.

### `group` — enclose atoms in a labelled region

1. **`selector`** — the relation (or atoms) whose members are grouped.
2. **`name`** — the label drawn on the bounding box.

## Directives

### `attribute` — show a field as inline text

1. **`field`** — the field to fold into the node as a label (instead of a separate
   box and arrow).

```python
@spytial.attribute(field='value')
```

### `atomColor` / `edgeColor` — color

- `atomColor`: **`selector`** (which atoms) + **`value`** (the color).
- `edgeColor`: **`field`** (which relation) + **`value`** (the color), plus optional
  `style`, `weight`, `filter`.

### `hideAtom` / `hideField` — remove things from the picture

- `hideAtom`: **`selector`** (the atoms to hide).
- `hideField`: **`field`** (the relation to hide).

### `inferredEdge` — draw a derived edge

1. **`selector`** — the pairs to connect.
2. **`name`** — the label for the new edge.

```python
@spytial.inferredEdge(
    selector='{ x : Vertex, y : Vertex | y in x.neighbors }',  # which pairs
    name='edge',                                               # edge label
)
```

### `tag` — attach a computed label

1. **`toTag`** — the type to tag.
2. **`name`** — the label name.
3. **`value`** — the field/expression to show.

### `size` / `icon` — adjust drawing

- `size`: **`selector`** + **`height`** + **`width`**.
- `icon`: **`selector`** + **`path`** (+ `showLabels`).

### `flag` — a rendering switch

1. **`name`** — e.g. `'hideDisconnected'` to drop atoms with no edges.

## Attaching operations

The same operations can be attached three ways.

**As class decorators** (most common):

```python
import spytial

@spytial.orientation(selector='children', directions=['below'])
@spytial.attribute(field='value')
class Node:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []
```

**On a single object**, without touching the class:

```python
node = Node('root')
spytial.annotate_orientation(node, selector='children', directions=['below'])
```

**Conditionally**, with `apply_if`:

```python
@spytial.apply_if(
    lambda cls: cls.__name__.endswith('Node'),
    spytial.atomColor(selector='self', value='lightblue'),
)
class Node:
    ...
```

## See it in action

Try these on real data structures in the [Playground](playground/index.html), or
browse the [`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) notebooks
for idiomatic usage on heaps, trees, hash tables, disjoint sets, and graphs.
