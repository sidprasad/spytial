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
   (e.g. `['below', 'left']`). One of `above`, `below`, `left`, `right`, or the
   adjacency variants `directlyAbove`, `directlyBelow`, `directlyLeft`,
   `directlyRight`, which also require that nothing sits in between.

```python
@spytial.orientation(
    selector='{ x : TreeNode, y : TreeNode | x.left = y }',  # which edges
    directions=['below', 'left'],                            # where the child goes
)
```

### `align` — line atoms up on a shared axis

1. **`selector`** — the atoms to align.
2. **`direction`** — the axis to share: `'horizontal'` or `'vertical'`.

### `cyclic` — arrange atoms in a ring

1. **`selector`** — the atoms/edges forming the cycle.
2. **`direction`** — which way the ring runs: `'clockwise'` or
   `'counterclockwise'`.

> These value sets are closed, and spytial checks them where you write them. The
> easy mistake is borrowing another constraint's words — `align` takes the *axis*
> (`horizontal`/`vertical`) while `orientation` takes *placements*
> (`above`/`left`/…), and swapping them is not an error spytial-core reports: an
> unknown orientation direction just quietly drops the constraint, and a
> misspelled `cyclic` direction reads as `clockwise`. Same for `flag`, which acts
> on exactly `hideDisconnected` and `hideDisconnectedBuiltIns`.

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

### `hold` — invert any constraint

Every constraint takes an optional **`hold`**. It defaults to `'always'`; pass
`'never'` to require the opposite — the layout must *not* satisfy the
constraint. It's how you say "these must not be grouped" or "y is never below
x", rather than leaving the relationship unconstrained.

```python
@spytial.orientation(selector='children', directions=['below'], hold='never')
@spytial.group(selector='Team.members', name='Team', hold='never')
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
4. **`draw`** *(optional)* — where each end attaches. See below.

```python
@spytial.inferredEdge(
    selector='{ x : Vertex, y : Vertex | y in x.neighbors }',  # which pairs
    name='edge',                                               # edge label
)
```

#### `draw` — attach an end to a group's hull

By default an inferred edge runs atom-to-atom. **`draw`** is a string
`'<end> -> <end>'` where each end is either `'_'` (the atom itself) or the
**name of a `group` constraint** — in which case that end attaches to the hull
of the group *keyed by that end's atom*. This is what makes group-to-group and
node-to-group edges expressible.

```python
# A binary group selector: one group per Team, keyed by the Team atom.
@spytial.group(selector='{ t : Team, l : list | l in t.members }', name='regions')
@spytial.inferredEdge(
    name='reports to',
    selector='{ a : Team, b : Team | b = a.parent }',
    draw='regions -> regions',   # hull to hull, rather than node to node
)
```

`'_ -> regions'` runs from the atom to a group's hull; `'_ -> _'` means the same
as omitting `draw`. The edge's own selector still ranges over atoms either way —
and with `draw`, a unary edge selector is allowed, its atom feeding both ends.

> **The referenced group must be keyed** — that is, declared with a *binary*
> selector, whose first element becomes the key. `draw` resolves each end by
> looking up the group of that name keyed by that end's atom, so a group built
> from a unary selector (`selector='Team.members'`) has no key for any end to
> match, and the edge is dropped without drawing anything. A group *name* that
> matches no `group` constraint at all is a hard error at render time; an atom
> that keys no group of that name is reported in the browser console.

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
