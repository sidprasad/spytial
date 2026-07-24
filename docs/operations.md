# Operations

Operations are the rules that shape a diagram. Each operation is one
**constraint** or **directive** that attaches to a class, or to an object. The
operations are declarative and order-independent. Each rule narrows the set of
acceptable layouts, which turns the raw value graph into the required picture.

- A **constraint** shapes the geometry. It sets *where* things go.
- A **directive** changes the drawing. It sets *how* things look.

Almost every operation is built from a **`selector`**, which selects the atoms
or edges that the operation applies to (see [Selectors](selectors.md)). Each
operation also takes a few specific arguments. The sections below describe each
operation part by part.

## Constraints

### `orientation`: place a target in a direction

1. **`selector`**: the edges to orient.
2. **`directions`**: where the target sits relative to its source, given as a
   list (for example `['below', 'left']`). Each direction is one of `above`,
   `below`, `left`, `right`, or an adjacency variant: `directlyAbove`,
   `directlyBelow`, `directlyLeft`, or `directlyRight`. An adjacency variant
   also requires that nothing sits between the two atoms.

```python
@spytial.orientation(
    selector='{ x : TreeNode, y : TreeNode | x.left = y }',  # which edges
    directions=['below', 'left'],                            # where the child goes
)
```

### `align`: line atoms up on a shared axis

1. **`selector`**: the atoms to align.
2. **`direction`**: the axis to share, `'horizontal'` or `'vertical'`.

### `cyclic`: arrange atoms in a ring

1. **`selector`**: the atoms or edges that form the cycle.
2. **`direction`**: the direction of the ring, `'clockwise'` or
   `'counterclockwise'`.

> These value sets are closed, and Spytial checks them at the point where they
> are written. A common mistake is to borrow another constraint's words. `align`
> takes the *axis* (`horizontal` or `vertical`), and `orientation` takes a
> *placement* (`above`, `left`, and so on). spytial-core does not report a swap
> of the two as an error. An unknown orientation direction drops the constraint
> without notice, and a misspelled `cyclic` direction is read as `clockwise`.
> The same applies to `flag`, which acts on exactly `hideDisconnected` and
> `hideDisconnectedBuiltIns`.

### `group`: enclose atoms in a labelled region

1. **`selector`**: the relation, or the atoms, whose members are grouped.
2. **`name`**: the label drawn on the bounding box.
3. **`addEdge`** *(optional)*: the connector between the group's key and the
   group. It is `'none'` (default), `'togroup'`, or `'fromgroup'`. To also style
   the connector, pass a `GroupEdge` instead of a bare string.
4. **`textStyle`** *(optional)*: styles the group's own label.

```python
from spytial import GroupEdge, LineStyle, TextStyle

@spytial.group(
    selector='Team.members',
    name='Team',
    addEdge=GroupEdge(points='togroup', lineStyle=LineStyle(pattern='dashed')),
    textStyle=TextStyle(color='navy'),
)
```

### `hold`: invert any constraint

Every constraint takes an optional **`hold`**. It defaults to `'always'`. Pass
`'never'` to require the opposite, so that the layout shall not satisfy the
constraint. Use `'never'` to state that atoms are not grouped, or that `y` is
never below `x`, instead of leaving the relationship unconstrained.

```python
@spytial.orientation(selector='children', directions=['below'], hold='never')
@spytial.group(selector='Team.members', name='Team', hold='never')
```

## Directives

### `attribute`: show a field as inline text

1. **`field`**: the field to fold into the node as a label, instead of a
   separate box and arrow.
2. **`textStyle`** *(optional)*: styles this attribute's line
   (`TextStyle(size=..., color=...)`).

```python
@spytial.attribute(field='value')
@spytial.attribute(field='weight', textStyle=spytial.TextStyle(size='small'))
```

### `atomStyle` and `edgeStyle`: styling

Styling is built from small **style blocks**, imported from `spytial`:

- `LineStyle(color, pattern, weight, highlight)`: a drawn edge line. `pattern` is
  `'solid'`, `'dashed'`, or `'dotted'`. `weight` is a number greater than 0.
- `TextStyle(size, color)`: any label. `size` is `'small'`, `'normal'`, or
  `'large'`.
- `BorderStyle(color, width)` and `FillStyle(color)`: an atom's outline and
  interior.

Every field is optional. Set only the fields that are needed. Plain dicts with
the same keys work everywhere the blocks do.

- `atomStyle`: **`selector`** (which atoms; omit for all), and any of
  **`borderStyle`**, **`fillStyle`**, and **`textStyle`**.
- `edgeStyle`: **`field`** (which relation), and any of **`lineStyle`**,
  **`textStyle`** (the edge's label), **`showLabel`**, and **`hidden`**, plus an
  optional `selector` or `filter`.

```python
from spytial import LineStyle, TextStyle, BorderStyle, FillStyle

@spytial.edgeStyle(field='next', lineStyle=LineStyle(color='crimson', pattern='dashed'))
@spytial.atomStyle(selector='Node', borderStyle=BorderStyle(color='steelblue'),
                   fillStyle=FillStyle(color='#eef6ff'))
```

> **Migrating from 2.x:** `atomColor` and `edgeColor` still work but are
> deprecated. They are rewritten to `atomStyle` or `edgeStyle` and raise a
> `DeprecationWarning`. The mapping is: `edgeColor.value` becomes
> `lineStyle.color`, `edgeColor.style` becomes `lineStyle.pattern`, and
> `edgeColor.weight` becomes `lineStyle.weight`; `atomColor.value` becomes
> `borderStyle.color`. The legacy directive colored the **border**, not the
> fill, so use `fillStyle` only for a filled look.

> **Breaking change in spytial-core 3.0:** two style rules that set the same
> property of the same edge or atom to *different* values now raise a
> `StyleCollisionError` at render time. Version 2.x kept the first rule without
> notice. Set each property in exactly one matching rule. Spytial warns at
> spec-collection time for the case that it can detect statically (identical
> `field`, `selector`, and `filter`).

### `hideAtom` and `hideField`: remove things from the picture

- `hideAtom`: **`selector`** (the atoms to hide).
- `hideField`: **`field`** (the relation to hide).

### `inferredEdge`: draw a derived edge

1. **`selector`**: the pairs to connect.
2. **`name`**: the label for the new edge.
3. **`lineStyle`** and **`textStyle`** *(optional)*: style the drawn edge and its
   label. These use the same blocks as `edgeStyle`. The inline `color`, `style`,
   and `weight` arguments are deprecated.
4. **`draw`** *(optional)*: where each end attaches. See below.

```python
@spytial.inferredEdge(
    selector='{ x : Vertex, y : Vertex | y in x.neighbors }',  # which pairs
    name='edge',                                               # edge label
)
```

#### `draw`: attach an end to a group's hull

By default, an inferred edge runs atom to atom. **`draw`** is a string
`'<end> -> <end>'`. Each end is either `'_'` (the atom itself) or the **name of a
`group` constraint**. For a group name, that end attaches to the hull of the
group *keyed by that end's atom*. This is what makes group-to-group and
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

`'_ -> regions'` runs from the atom to a group's hull. `'_ -> _'` is the same as
an omitted `draw`. In both cases the edge's own selector ranges over atoms. With
`draw`, a unary edge selector is allowed, and its atom feeds both ends.

> **The referenced group shall be keyed.** That is, it shall be declared with a
> *binary* selector, and the first element becomes the key. `draw` resolves each
> end by looking up the group of that name keyed by that end's atom. A group
> built from a unary selector (`selector='Team.members'`) has no key for any end
> to match, so the edge is dropped and nothing is drawn. A group *name* that
> matches no `group` constraint is a hard error at render time. An atom that keys
> no group of that name is reported in the browser console.

### `tag`: attach a computed label

1. **`toTag`**: the type to tag.
2. **`name`**: the label name.
3. **`value`**: the field or expression to show.
4. **`textStyle`** *(optional)*: styles this tag's line
   (`TextStyle(size=..., color=...)`).

### `size` and `icon`: adjust drawing

- `size`: **`selector`**, **`height`**, and **`width`**.
- `icon`: **`selector`** and **`path`** (plus optional `showLabels`).

### `flag`: a rendering switch

1. **`name`**: for example `'hideDisconnected'`, which drops atoms with no
   edges.

## Attaching operations

The same operations can be attached in three ways.

**As class decorators** (the most common way):

```python
import spytial

@spytial.orientation(selector='children', directions=['below'])
@spytial.attribute(field='value')
class Node:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []
```

**On a single object**, without a change to the class:

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

## Examples

Try these operations on real data structures in the
[Playground](playground/index.html). The
[`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) notebooks also show
idiomatic usage on heaps, trees, hash tables, disjoint sets, and graphs.
