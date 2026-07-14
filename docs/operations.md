# Operations

Operations are the rules that shape a diagram. Each is one **constraint** or
**directive** you attach to a class (or an object). They are declarative and
order-independent — every rule narrows the set of acceptable layouts, turning the
raw value graph into the picture you want.

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
3. **`addEdge`** *(optional)* — the connector between the group's key and the
   group: `'none'` (default), `'togroup'`, or `'fromgroup'`. To also style the
   connector, pass a `GroupEdge` instead of a bare string.
4. **`textStyle`** *(optional)* — styles the group's own label.

```python
from spytial import GroupEdge, LineStyle, TextStyle

@spytial.group(
    selector='Team.members',
    name='Team',
    addEdge=GroupEdge(points='togroup', lineStyle=LineStyle(pattern='dashed')),
    textStyle=TextStyle(color='navy'),
)
```

## Directives

### `attribute` — show a field as inline text

1. **`field`** — the field to fold into the node as a label (instead of a separate
   box and arrow).
2. **`textStyle`** *(optional)* — styles this attribute's line
   (`TextStyle(size=..., color=...)`).

```python
@spytial.attribute(field='value')
@spytial.attribute(field='weight', textStyle=spytial.TextStyle(size='small'))
```

### `atomStyle` / `edgeStyle` — styling

Styling is built from small **style blocks** (import them from `spytial`):

- `LineStyle(color, pattern, weight, highlight)` — a drawn edge line;
  `pattern` is `'solid'`, `'dashed'`, or `'dotted'`, `weight` is a number > 0.
- `TextStyle(size, color)` — any label; `size` is `'small'`/`'normal'`/`'large'`.
- `BorderStyle(color, width)` / `FillStyle(color)` — an atom's outline and interior.

Every field is optional — set only what you mean. Plain dicts with the same
keys work everywhere the blocks do.

- `atomStyle`: **`selector`** (which atoms; omit for all) + any of
  **`borderStyle`**, **`fillStyle`**, **`textStyle`**.
- `edgeStyle`: **`field`** (which relation) + any of **`lineStyle`**,
  **`textStyle`** (the edge's label), **`showLabel`**, **`hidden`**, plus
  optional `selector` / `filter`.

```python
from spytial import LineStyle, TextStyle, BorderStyle, FillStyle

@spytial.edgeStyle(field='next', lineStyle=LineStyle(color='crimson', pattern='dashed'))
@spytial.atomStyle(selector='Node', borderStyle=BorderStyle(color='steelblue'),
                   fillStyle=FillStyle(color='#eef6ff'))
```

> **Migrating from 2.x:** `atomColor` and `edgeColor` still work but are
> deprecated — they are rewritten to `atomStyle` / `edgeStyle` and raise a
> `DeprecationWarning`. The mapping: `edgeColor`'s `value` → `lineStyle.color`,
> `style` → `lineStyle.pattern`, `weight` → `lineStyle.weight`; `atomColor`'s
> `value` → `borderStyle.color` (the legacy directive colored the **border**,
> not the fill — reach for `fillStyle` only if you want a filled look).

> **Breaking in spytial-core 3.0:** two style rules that set the same property
> of the same edge/atom to *different* values now raise a `StyleCollisionError`
> at render time (2.x silently kept the first). Set each property in exactly one
> matching rule. spytial warns at spec-collection time for the statically
> detectable case (identical `field`/`selector`/`filter`).

### `hideAtom` / `hideField` — remove things from the picture

- `hideAtom`: **`selector`** (the atoms to hide).
- `hideField`: **`field`** (the relation to hide).

### `inferredEdge` — draw a derived edge

1. **`selector`** — the pairs to connect.
2. **`name`** — the label for the new edge.
3. **`lineStyle`** / **`textStyle`** *(optional)* — style the drawn edge and its
   label (same blocks as `edgeStyle`; the inline `color`/`style`/`weight`
   arguments are deprecated).

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
4. **`textStyle`** *(optional)* — styles this tag's line
   (`TextStyle(size=..., color=...)`).

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
    spytial.atomStyle(selector='self', borderStyle=spytial.BorderStyle(color='lightblue')),
)
class Node:
    ...
```

## See it in action

Try these on real data structures in the [Playground](playground/index.html), or
browse the [`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) notebooks
for idiomatic usage on heaps, trees, hash tables, disjoint sets, and graphs.
