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

## Boolean and optional fields

A field is a relation, not a value. `n.flag` is the set of atoms the field
points at, so it cannot stand alone where a condition is required:

```python
selector='{ n : Node | n.flag }'
```

This is reported as `Expected the expression after the bar to be a boolean
value!` when the layout is generated. Unlike an omitted container projection,
it does not fail quietly. The working form compares the field against the atom
it holds:

```python
selector='{ n : Node | n.flag = True }'
```

`True` and `False` are atoms. There is one of each per diagram, shared by every
field that holds them.

`None` is an atom in the same way, of type `NoneType`. A field set to `None`
still has an atom on the other end, so a declared field is never empty:

| Intent | Form |
| --- | --- |
| the field is unset | `n.link = None` |
| the field is set | `some n.link & Node` |

`some n.link` is therefore true of every atom of the type, and `no n.link` is
true of none. Both are quiet: they are well formed, they name only relations
that exist, and no selector warning is reported.

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

## Selectors written in Python

A `selector` may be a Python function instead of an sgq expression. Three steps
turn one into the other:

1. The function returns the values to select. A value per row for a unary
   selector, a tuple per row for a higher arity.
2. Each value is translated to the ID of its atom. A value with no atom is an
   error.
3. The IDs become the selector: `->` within a tuple, `+` between elements.

The function runs during `spytial.diagram()`, after the walk and before the
specification is written, so the IDs it translates against are the ones the
relationalizer assigned to the instance about to be drawn. It is handed the
values the walk reached, which is exactly the set of values that have atoms:

```python
def child_edges(values):
    return [(n, k) for n in values if isinstance(n, Node) for k in n.kids]

def odd_nodes(values):
    return [n for n in values if isinstance(n, Node) and n.val % 2]

spytial.annotate_orientation(tree, selector=child_edges, directions=["below"])
spytial.annotate_atomStyle(
    tree, selector=odd_nodes, borderStyle=spytial.BorderStyle(color="coral")
)
```

Which compile to `n0 -> n2 + n0 -> n4 + n4 -> n6` and `n2 + n6`. An empty result
compiles to `none`, the empty relation.

The first value in the list is the diagrammed object itself, so a
root-anchored selector needs no extra parameter:

```python
selector=lambda values: [(values[0], k) for k in values[0].kids]
```

Because the function runs at diagramming time, the same one may be given to a
class decorator, where no instance exists yet:

```python
@spytial.orientation(selector=child_edges, directions=["below"])
@dataclass
class Node:
    val: int
    kids: list["Node"] = field(default_factory=list)
```

The reason to write a selector this way is that it reads the object's own
attributes. `n.kids` replaces `p.kids.idx[int]`, so the relationalization need
not be known. Nothing is intercepted: the comprehension is ordinary Python, so a
fault in it raises at the line that wrote it, with an ordinary traceback.

### Choosing between the two forms

Neither form replaces the other.

| | Python function | sgq expression |
| --- | --- | --- |
| Reads | the objects themselves | the relationalized instance |
| Suits | conditions on a value: `n.color == RED`, `n is NIL`, `len(n.keys) > 2` | conditions on the shape of the graph: `^parent`, `~next`, `iden` |
| Scope | translated per build, so `diagram()` and `sequence()` | any instance, `edit()` included |
| In the specification | a union of atom IDs | the expression as written |

A rough rule: reach for a Python function when the condition is about a value,
and for sgq when it is about the shape of the graph. A DSU forest oriented by
`^(~parent)` -- the transitive closure of the inverted parent relation -- has no
comprehension form; the Python version would be a hand-written fixpoint.

Because a translated selector names atom IDs, and an atom ID is a position in
one walk, it describes exactly the instance it was translated against. That is
why the function runs during the diagram rather than before it.

`spytial.sequence()` supports one. It rebuilds every frame in Python through a
single shared builder, which keeps atom IDs stable across frames, so the
function is run once per frame and the rows are unioned into one entry. A term
naming a value some frame does not hold simply matches nothing in that frame,
which is what a structure that grows over the sequence should do.

`spytial.edit()` does not. It writes the specification once and the browser
changes the data afterwards, so the function cannot run again and the selector
would go on naming the atoms of the seed. It rejects one with a `SelectorError`
naming the slot; write that selector as an sgq expression.

### What is reported

A value the walk never reached is dropped, with an `AtomNotInInstance` warning
naming it. The report cannot be left to the evaluator: a literal naming no atom
evaluates non-empty in sgq, so a wrong value would apply the rule to a phantom
atom silently. Make it fatal with
`warnings.simplefilter("error", spytial.AtomNotInInstance)`.

Rows of the wrong width for the slot raise, because spytial-core discards rows
of the wrong width and the directive would otherwise stop applying without a
word. (`group` accepts either width: a unary selector builds a single unkeyed
group.)

A `bytes` or `complex` value raises. Their atom IDs have no sgq spelling in any
form, so the error comes from the translation rather than from the browser. This
is a limit of naming such an atom in a selector at all, not of this form in
particular.

`str` values and `-inf` are emitted as a type binding -- `{s : str | @:s = "x"}`
-- rather than as literals. A quoted string is a *value* in sgq and not a member
of `univ`, so a directive given one selects no atom, and a `hideAtom` on a
string would draw it anyway. This is the spelling the sgq-written notebooks use
for the same reason.

## Where selectors show up

A selector is used by every [operation](operations.md) that takes a `selector`
argument, and by the related `field` and `filter` arguments. For a simple
object, an edge label or a type name is usually enough. Use the operators above
to target exactly the right atoms or tuples.
