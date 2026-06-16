# Selectors

Most sPyTial operations take a `selector`: a small expression that says **which
atoms or edges a rule applies to**. A selector is a pattern match over the *value
graph* sPyTial builds from your object, so it works across instances — not just one.
The language is a subset of [Alloy](https://alloytools.org)/Forge; this page is a
guide for Python programmers.

## The value graph: atoms, relations, types

Before laying anything out, sPyTial turns your object into a graph:

- An **atom** is one object or value — a node, an `int`, a `str`, `None`.
- A **relation** is a field. `node.left` becomes a relation named `left`: the set of
  `(owner, target)` edges, one for each object that has a `left`.
- A **type** is the set of all atoms of that type, named by the Python class:
  `BSTNode`, `int`, `str`, `list`, `dict`. (The type of `None` is `NoneType` — not
  `None`.)

The two simplest selectors are a **type name** (`BSTNode`) and a **field name**
(`left`).

## Two kinds of result: atoms vs edges

A selector evaluates to one of two things, and each operation expects a particular
one:

- **Atom sets** — e.g. `BSTNode`, `{ x : BSTNode | … }`. Used by atom operations:
  `hideAtom`, `atomColor`.
- **Edge sets** — e.g. `left`, `~left`, `BSTNode -> BSTNode`. Used by edge
  operations: `orientation`, `align`.

Rule of thumb: **type names and comprehensions produce atoms**; a **bare field
name**, its reverse `~f`, its closures `^f` / `*f`, and products `a -> b` produce
**edges**. The set operators (`+`, `&`, `-`) keep the kind of their operands.

## Navigating with the dot `.`

`A.f` means: *for every atom in the set `A`, follow relation `f`, and collect the
results.*

```text
BSTNode.left        # every left-child of any BSTNode    ~  {a.left for a in BSTNode}
BSTNode.left.key    # the keys of those children         (chained)
```

When `A` is a single atom this looks like attribute access; when `A` is a whole type
it is a flat-map over the type. The left side is always a **set** — you cannot start
a selector with a bare lowercase name like `x` unless `x` is bound by a comprehension
or quantifier (next).

## Building up a selector

Each line below is a complete selector you could hand to an operation:

```text
BSTNode                              # 1. a type — all BST nodes (atoms)
left                                 # 2. a relation — all left-edges (edges)
{ x : BSTNode | x.key in NoneType }  # 3. a filter — nodes whose key is None (atoms)
left & (BSTNode -> BSTNode)          # 4. left-edges with both endpoints BSTNodes (edges)
```

The **comprehension** `{ x : T | cond }` is the workhorse — "the atoms of `T` where
`cond` holds." Inside `cond` you can use: comparisons `=`, `in`, `<`, `<=`, `>`,
`>=`; navigation (`x.key`); multiplicities `some e` / `no e` / `one e` / `lone e`
(`e` is non-empty / empty / exactly one / at most one); the label of an atom `@:x`
(the text it renders as, e.g. `@:x = "15"`); and `and` / `or` / `not`.

## Cheat sheet

| Selector | Result | Means |
| --- | --- | --- |
| `BSTNode` | atoms | all atoms of type `BSTNode` |
| `left` | edges | the `left` relation — every `(owner, left-child)` pair |
| `A.f` | atoms | follow `f` from every atom in `A` (a join) |
| `~f` | edges | `f` reversed: `{(parent, child)}` becomes `{(child, parent)}` |
| `^f` | edges | `f` followed one-or-more times (everything reachable) |
| `*f` | edges | `^f` together with identity — `a.*f` is `a` plus all it reaches |
| `a + b` | same | union (`a \| b`) |
| `a & b` | same | intersection (`a & b`) |
| `a - b` | same | difference (`a - b`) |
| `a -> b` | edges | every pair `(x, y)` with `x in a`, `y in b` — a product (edge set) |
| `{ x : T \| cond }` | atoms | atoms of `T` where `cond` holds |

These appear **inside `cond` / quantifiers**, not as standalone selectors:
comparisons (`= in < <= > >=`), `#a` (size), `@:x` (an atom's label string),
arithmetic (`add[a, b]`, `min[s]`, `max[s]`), multiplicities (`some` / `no` / `one`
/ `lone`), and quantifiers (`all x: T | …`, `some x: T | …`). The constant `univ` is
the set of every atom.

## Worked example: the BST selectors

The [binary search tree](getting-started.md) uses two selectors that look scary but
say something simple.

**Orient only real children** (`orientation`) — an edge set:

```text
left & (BSTNode -> (BSTNode - NoneType.~key))
```

- `NoneType.~key` — parses as `NoneType.(~key)`: follow `key` **backwards** from the
  `None` atoms, giving the node(s) whose `key` is `None` — the shared `NIL` sentinel.
- `BSTNode - NoneType.~key` — every BST node **except** the sentinel ("real nodes").
- `BSTNode -> (…)` — all `(any node, real node)` edges.
- `left & (…)` — keep only the `left` edges whose target is a real node.

Intersecting an edge set with an edge set is what stops the shared `NIL` from being
placed below-left of every node at once.

**Hide the plumbing** (`hideAtom`) — an atom set:

```text
{ x : BSTNode | (x.key in NoneType) } + BSTree + int + NoneType
```

- `{ x : BSTNode | x.key in NoneType }` — BST nodes whose `key` is `None` (the NIL
  sentinel).
- `+ BSTree + int + NoneType` — also the `BSTree` wrapper, the bare `int`
  key-values, and the `None` atoms.

All atom sets, unioned — so everything but the real keyed nodes is hidden.

## Where selectors show up

Every [operation](operations.md) that takes a `selector` argument (and the related
`field` / `filter` arguments). For simple objects a bare field or type name is
usually enough; reach for the relational operators when you need to target *exactly*
the right atoms or edges — like "real children, not the sentinel" above.
