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
  `(source, dest)` tuples, one for each object that has a `left`.
- A **type** is the set of all atoms of that type, named by the Python class:
  `TreeNode`, `int`, `str`, `list`, `dict`. (The type of `None` is `NoneType` — not
  `None`.)

## Unary and binary selectors

A selector picks out either **one thing or two**:

- A **unary selector** selects a **set** of atoms — e.g. `TreeNode`,
  `{ x : TreeNode | … }`. Operations that act on atoms (`hideAtom`, `atomColor`)
  take a unary selector.
- A **binary selector** selects a **set of tuples** — pairs `(source, dest)` —
  e.g. `left`, `~left`, `{ x : TreeNode, y : TreeNode | … }`. Operations that act
  on edges (`orientation`, `align`, `inferredEdge`) take a binary selector.

**An edge label is already a selector.** A field / relation name — `left`, `next`,
`parent` — *is* a binary selector: it stands for that edge's `(source, dest)`
tuples. So `selector='left'` selects every left-edge, no comprehension required.

Rule of thumb: **type names** and **single-variable comprehensions** are unary;
**edge labels**, their reverse `~f`, their closures `^f` / `*f`, products `a -> b`,
and **two-variable comprehensions** are binary. The set operators (`+`, `&`, `-`)
keep the arity of their operands.

## Navigating with the dot `.`

`A.f` means: *for every atom in the set `A`, follow relation `f`, and collect the
results.* Joining a unary selector through a binary one gives a unary selector
again:

```text
TreeNode.left        # every left-child of any TreeNode   ~  {a.left for a in TreeNode}
TreeNode.left.value  # the values of those children       (chained)
```

When `A` is a single atom this looks like attribute access; when `A` is a whole type
it is a flat-map over the type. The left side is always a **set** — you cannot start
a selector with a bare lowercase name like `x` unless `x` is bound by a comprehension
or quantifier (next).

## Building up a selector

Each line below is a complete selector you could hand to an operation:

```text
TreeNode                                       # 1. a type — all tree nodes (unary)
left                                           # 2. an edge label — all left-edges (binary)
{ x : TreeNode | no x.left }                   # 3. a filter — nodes with no left child (unary)
{ x : TreeNode, y : TreeNode | x.left = y }    # 4. matched pairs — left-child edges (binary)
```

Comprehensions are the workhorse:

- `{ x : T | cond }` — the **atoms** of `T` where `cond` holds (unary).
- `{ x : T, y : T | cond }` — the **pairs** `(x, y)` where `cond` holds (binary).
  This is how the examples say "connect each node to its child."

Inside `cond` you can use comparisons (`=`, `in`, `<`, `<=`, `>`, `>=`); navigation
(`x.left`); multiplicities `some e` / `no e` / `one e` / `lone e` (`e` is non-empty /
empty / exactly one / at most one); the label of an atom `@:x` (the text it renders
as, e.g. `@:x = "10"`); and `and` / `or` / `not`.

## Cheat sheet

| Selector | Arity | Means |
| --- | --- | --- |
| `TreeNode` | unary | all atoms of type `TreeNode` |
| `left` | binary | the `left` edge label — its `(source, dest)` tuples |
| `A.f` | unary | follow `f` from every atom in `A` (a join) |
| `~f` | binary | `f` reversed: `(parent, child)` becomes `(child, parent)` |
| `^f` | binary | `f` followed one-or-more times (everything reachable) |
| `*f` | binary | `^f` together with identity — `a.*f` is `a` plus all it reaches |
| `a + b` | same | union (`a \| b`) |
| `a & b` | same | intersection (`a & b`) |
| `a - b` | same | difference (`a - b`) |
| `a -> b` | binary | every tuple `(x, y)` with `x in a`, `y in b` (a product) |
| `{ x : T \| cond }` | unary | atoms of `T` where `cond` holds |
| `{ x : T, y : T \| cond }` | binary | pairs of `T` where `cond` holds |

These appear **inside `cond` / quantifiers**, not as standalone selectors:
comparisons (`= in < <= > >=`), `#a` (size), `@:x` (an atom's label string),
arithmetic (`add[a, b]`, `min[s]`, `max[s]`), multiplicities (`some` / `no` / `one`
/ `lone`), and quantifiers (`all x: T | …`, `some x: T | …`). The constant `univ` is
the set of every atom.

## Worked example: the binary tree

The [binary tree](getting-started.md) orients children with two binary selectors.
Its `left` field is already a binary selector (all left-edges), but to be precise it
uses a two-variable comprehension that matches **pairs**:

```text
{ x : TreeNode, y : TreeNode | x.left = y }
```

- `x : TreeNode, y : TreeNode` — range over pairs of nodes.
- `x.left = y` — keep the pairs where `y` is `x`'s left child.

So this evaluates to the **left-child tuples** — exactly what `orientation` needs.
The mirror `{ x : TreeNode, y : TreeNode | x.right = y }` gives the right-child
tuples. Then `hideAtom(selector='NoneType')` (a unary selector) drops the empty
`None` leaves, and the `hideDisconnected` flag removes any atom left with no edges.

### Going further

When you need to be surgical, combine operators: `left & (TreeNode -> TreeNode)`
keeps only left-edges whose endpoints are both nodes; `~left` is the child→parent
direction; `^left` is every descendant reached through `left` pointers. The
[`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) notebooks use these to
do things like "the real children, not the shared sentinel."

## Where selectors show up

Every [operation](operations.md) that takes a `selector` argument (and the related
`field` / `filter` arguments). For simple objects an edge label or a type name is
usually enough; reach for the relational operators when you need to target *exactly*
the right atoms or tuples.
