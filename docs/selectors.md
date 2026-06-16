# Selectors

Most sPyTial operations take a `selector`: a small expression for **which atoms or
edges a rule applies to**. It is a pattern match over the *value graph* sPyTial
builds from your object, so it matches across instances — not just one. The selector
language is a subset of [Alloy](https://alloytools.org).

## The value graph: atoms, relations, types

Before laying anything out, sPyTial turns your object into a graph:

- An **atom** is one object or value — a node, an `int`, a `str`, `None`.
- A **relation** is a field. `node.left` becomes a relation named `left`: the set of
  `(source, dest)` tuples, one for each object that has a `left`.
- A **type** is the set of all atoms of that type, named by the Python class:
  `TreeNode`, `int`, `str`, `list`, `dict`. (The type of `None` is `NoneType` — not
  `None`.)

## Unary and binary selectors

A selector selects either **one thing or two**:

- A **unary** selector selects a **set** of atoms — e.g. `TreeNode`,
  `{ x : TreeNode | … }`. Operations that act on atoms (`hideAtom`, `atomColor`)
  take a unary selector.
- A **binary** selector selects a **set of `(source, dest)` tuples** — e.g. `left`,
  `~left`, `{ x : TreeNode, y : TreeNode | … }`. Operations that act on edges
  (`orientation`, `align`, `inferredEdge`) take a binary selector.

**An edge label is already a selector.** A field/relation name like `left`, `next`,
or `parent` is a binary selector standing for that edge's `(source, dest)` tuples —
so `selector='left'` selects every left-edge, no comprehension required.

## Operators

| Selector | Arity | Meaning |
| --- | --- | --- |
| `TreeNode` | unary | every atom of that type |
| `left` | binary | an edge label — that relation's `(source, dest)` tuples |
| `{ x : T \| cond }` | unary | the atoms of `T` where `cond` holds |
| `{ x : T, y : T \| cond }` | binary | the pairs `(x, y)` where `cond` holds |
| `A.f` | unary | follow `f` from every atom in `A` (a join) |
| `~f` | binary | `f` reversed — swaps each tuple's two ends |
| `^f` | binary | reachability — `f` followed one or more times |
| `*f` | binary | `^f` plus identity — reachability including self |
| `a + b`, `a & b`, `a - b` | same | union, intersection, difference |
| `a -> b` | binary | cross product — every tuple `(x, y)`, `x in a`, `y in b` |

Inside a comprehension's `cond` you can use comparisons (`=`, `in`, `<`, `<=`, `>`,
`>=`), the multiplicities `some` / `no` / `one` / `lone`, an atom's display label
`@:x` (e.g. `@:x = "10"`), and `and` / `or` / `not`.

## Worked example: the binary tree

The [binary tree](getting-started.md) orients children with a two-variable
comprehension — a binary selector matching parent/child **pairs**:

```text
{ x : TreeNode, y : TreeNode | x.left = y }
```

`x` and `y` range over nodes, and `x.left = y` keeps the pairs where `y` is `x`'s
left child — so this is the set of left-child tuples, exactly what `orientation`
needs. (`left` on its own is already a binary selector; the comprehension just makes
the intent explicit.) `hideAtom(selector='NoneType')` is the unary counterpart — it
drops the empty `None` leaves.

When you need to be surgical, combine operators: `left & (TreeNode -> TreeNode)`
keeps only left-edges whose endpoints are both nodes, and `~left` is the
child→parent direction.

## Where selectors show up

Every [operation](operations.md) that takes a `selector` (and the related `field` /
`filter` arguments). For simple objects an edge label or a type name is usually
enough; reach for the operators above when you need to target *exactly* the right
atoms or tuples.
