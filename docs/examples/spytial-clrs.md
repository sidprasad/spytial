# `spytial-clrs` Examples

[`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) is the companion examples repository for `spytial-py`. It contains notebooks based on CLRS data structures and is the best source of realistic diagrams for docs, demos, and screenshots.

## Why it is useful

If you want to see what sPyTial looks like on larger structures, `spytial-clrs` is the best place to start:

- it provides realistic examples that go beyond toy `dict` and `list` inputs
- it shows how different layout operations help explain specific data structures
- it gives you a gallery of end-to-end examples you can adapt for your own work

## Example guide

Use the notebooks as a guide depending on what you want to visualize:

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

## How to use these examples

- Start with `stacksqueues.ipynb` or `linked-lists.ipynb` if you are new to sPyTial.
- Browse `trees.ipynb` and `graphs.ipynb` for richer layouts and more advanced operation combinations.
- Use the notebook closest to your own data shape as a template for your first diagram.
