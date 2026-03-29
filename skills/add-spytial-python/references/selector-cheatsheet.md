# Selector Cheatsheet

This cheatsheet is based on `simple-graph-query` syntax as used by sPyTial selectors.

## Core set and relation operators

- Union: `A + B`
- Intersection: `A & B`
- Difference: `A - B`
- Join: `A.rel` or `rel.Type`
- Product: `A -> B`
- Transpose: `~rel`
- Transitive closure: `^rel`
- Reflexive-transitive closure: `*rel`

Examples:

- `Node.key`
- `edge.edge`
- `~parent`
- `^next`
- `Node - NoneType`

## Predicates and logic

- Membership: `x in S`
- Equality/inequality: `x = y`, `x != y`
- Boolean ops: `and`, `or`, `!`, `=>`, `<=>`
- Quantifiers: `all`, `some`, `no`, `one`, `lone`

Examples:

- `some x: Node | x in roots`
- `all x: Item | some y: Item | x != y`
- `all disj i, j: Int | not i = j`

## Comprehensions (great for `group`/`orientation` selectors)

Unary:

```txt
{x : Item | x.value > 10}
```

Binary:

```txt
{b : Basket, a : Fruit | (a in b.fruit) and a.status = Rotten}
```

Numeric ordering (common for array-backed structures):

```txt
{x, y : idx[object][object] | @num:(x[idx[object]]) < @num:(y[idx[object]])}
```

## Built-ins that matter most

- `univ`: all atoms
- `iden`: identity relation (all `(a, a)` pairs)
- `Int`: integer atoms

## Label conversion helpers

- `@:(expr)` convert to string label form
- `@num:(expr)` convert to number for numeric comparisons

Examples:

- `@:(n14) = @:(12)`
- `@num:(x[idx[object]]) < @num:(y[idx[object]])`

## Reserved keyword identifiers

If a field/type name conflicts with a keyword, use backticks:

- `` `set` ``
- `` item0.`in` ``

## Debugging workflow for selectors

1. Open `spytial.evaluate(obj)` to inspect available atoms/relations.
2. Start with a broad selector (`TypeName` or relation name).
3. Add one operator at a time (`&`, `-`, join, then comprehension).
4. Re-run and verify before using it in an annotation.
5. Keep selectors readable; factor complex expressions into local constants.
