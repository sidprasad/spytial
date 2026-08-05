# Selectors

Most Spytial operations take a `selector`. A selector is a small expression for
**which atoms or edges a rule applies to**. It is a pattern match over the
*value graph* that Spytial builds from an object, so it matches across
instances, not one instance only. The selector language is a subset of
[Alloy](https://alloytools.org).

## The value graph: atoms, relations, types

Before any layout, Spytial turns an object into a graph:

- An **atom** is one object or value: a node, an `int`, a `str`, or `None`.
- A **relation** is a field. `node.left` becomes a relation named `left`. It is
  the set of `(source, dest)` tuples, one tuple for each object that has a
  `left`.
- A **type** is the set of all atoms of that type, named by the Python class:
  `TreeNode`, `int`, `str`, `list`, `dict`. The type of `None` is `NoneType`,
  not `None`.

## Unary and binary selectors

A selector selects one thing or two:

- A **unary** selector selects a set of atoms, for example `TreeNode` or
  `{ x : TreeNode | … }`. Operations that act on atoms (`hideAtom`, `atomStyle`)
  take a unary selector.
- A **binary** selector selects a set of `(source, dest)` tuples, for example
  `left`, `~left`, or `{ x : TreeNode, y : TreeNode | … }`. Operations that act
  on edges (`orientation`, `align`, `inferredEdge`) take a binary selector.

An edge label is already a selector. A field or relation name such as `left`,
`next`, or `parent` is a binary selector for that edge's `(source, dest)`
tuples. So `selector='left'` selects every left edge, and no comprehension is
required.

## Operators

| Selector | Arity | Meaning |
| --- | --- | --- |
| `TreeNode` | unary | every atom of that type |
| `left` | binary | an edge label: that relation's `(source, dest)` tuples |
| `{ x : T \| cond }` | unary | the atoms of `T` where `cond` holds |
| `{ x : T, y : T \| cond }` | binary | the pairs `(x, y)` where `cond` holds |
| `A.f` | unary | follow `f` from every atom in `A` (a join) |
| `~f` | binary | `f` reversed: swaps each tuple's two ends |
| `^f` | binary | reachability: `f` followed one or more times |
| `*f` | binary | `^f` plus identity: reachability including self |
| `a + b`, `a & b`, `a - b` | same | union, intersection, difference |
| `a -> b` | binary | cross product: every tuple `(x, y)`, `x in a`, `y in b` |

Inside a comprehension's `cond`, the following are available: the comparisons
`=`, `in`, `<`, `<=`, `>`, and `>=`; the multiplicities `some`, `no`, `one`, and
`lone`; an atom's display label `@:x` (for example `@:x = "10"`); and the
operators `and`, `or`, and `not`.

A string shall be written as a quoted literal. Double quotes are required. Single
quotes are a parse error.

A bare name that matches no type and no relation is the empty set. This fails
quietly. A comparison against the empty set is false, so the directive does not
apply. If both sides of the comparison are empty, the comparison is true, and the
directive applies to every atom. The diagram renders in both cases. Unresolved
names are reported on the diagram as a selector warning, which names the
directive and its selector.

## Container fields

A field that holds a container does not relate the object to the container's
elements. It relates the object to **the container**, which is an atom of its
own. The elements hang off that atom through a second relation. A selector that
names the field alone therefore reaches the container and stops there.

| Field type | Field relation | Element relation | Elements of `x.f` |
| --- | --- | --- | --- |
| `list` | `f : (obj, list)` | `idx : (list, int, value)` | `x.f.idx[int]` |
| `dict` | `f : (obj, dict)` | `kv : (dict, key, value)` | `x.f.kv[K]` |
| `set` | `f : (obj, set)` | `contains : (set, value)` | `x.f.contains` |
| `tuple` | `f : (obj, tuple)` | `t0`, `t1`, … one per position | `x.f.t0 + x.f.t1` |

For a list-valued field `kids`, the working form is:

```python
@spytial.orientation(
    selector='{ x : DagNode, y : DagNode | y in x.kids.idx[int] }',
    directions=['below'],
)
```

`x.kids` is the `list` atom. `x.kids.idx` is the `(index, value)` pairs it
holds. `[int]` joins over every index and leaves the values. The same bracket
takes one position: `x.kids.idx[0]` is the first element. For a `dict`, `K` is
the key type, so `x.f.kv[str]` is the values under string keys.

Omitting the projection is quiet. This matches nothing:

```python
selector='{ x : DagNode, y : DagNode | y in x.kids }'
```

It is well formed, and it names only relations that exist, so no selector
warning is reported. It matches no pair, because a `DagNode` is never a `list`.
The constraint is generated over an empty set, and the diagram renders with the
decorator doing nothing.

## Worked example: the binary tree

The [binary tree](getting-started.md) orients children with a two-variable
comprehension. This is a binary selector that matches parent and child
**pairs**:

```text
{ x : TreeNode, y : TreeNode | x.left = y }
```

`x` and `y` range over nodes. `x.left = y` keeps the pairs where `y` is the left
child of `x`. This is the set of left-child tuples, which is what `orientation`
needs. (`left` on its own is already a binary selector. The comprehension only
makes the intent explicit.) `hideAtom(selector='NoneType')` is the unary
counterpart. It drops the empty `None` leaves.

For a more precise result, combine operators. `left & (TreeNode -> TreeNode)`
keeps only the left edges whose endpoints are both nodes. `~left` is the
child-to-parent direction.

## Where selectors show up

A selector is used by every [operation](operations.md) that takes a `selector`
argument, and by the related `field` and `filter` arguments. For a simple
object, an edge label or a type name is usually enough. Use the operators above
to target exactly the right atoms or tuples.
