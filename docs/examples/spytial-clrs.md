# `spytial-clrs` Examples

[`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) is the companion examples repository for `spytial-py`. It contains notebooks based on CLRS data structures and is the best source of realistic diagrams for docs, demos, and screenshots.

## Why it matters for this repo

For `spytial-py`, `spytial-clrs` is useful in three ways:

- it provides user-facing examples that are more realistic than toy `dict` and `list` snippets
- it shows which combinations of operations are expressive enough for classic data structures
- it gives contributors a repeatable corpus to smoke-test when diagram output changes

## Suggested documentation map

Use the notebooks as the source material for different sections of the docs:

| Notebook | Structures | Good docs topics |
| --- | --- | --- |
| `stacksqueues.ipynb` | stacks, queues | attributes, linear structure, first tutorial examples |
| `linked-lists.ipynb` | singly, doubly, circular linked lists | field hiding, attributes, cyclic layout |
| `heaps.ipynb` | max heap, Fibonacci heap | recursive structures, alignment, richer edge styling |
| `trees.ipynb` | BST, red-black tree, order statistic tree, interval tree, B-tree, van Emde Boas tree | annotations on recursive types, grouped structures, larger gallery examples |
| `hash-tables.ipynb` | direct-address and chained hash tables | grouping, selector-heavy examples, labeled fields |
| `graphs.ipynb` | graphs, MST, SCC views | graph-like structures, grouping, alternative visual projections |
| `disjoint-sets.ipynb` | disjoint set forests | group constraints and forest layouts |
| `memoization.ipynb` | matrix-style DP tables | alignment constraints and grid-like layouts |

## Recommended way to use it

If you keep extending the docs site, `spytial-clrs` should probably feed three kinds of pages:

1. short, focused snippets in the main usage docs
2. a visual gallery page with screenshots and notebook links
3. regression-oriented smoke tests for major rendering changes

## Local workflow

From the `spytial-clrs` repo:

```bash
pip install -r src/requirements.txt
jupyter notebook src/
```

If you want a browser-hosted notebook experience, that repo already contains a JupyterLite GitHub Pages deployment pipeline.
