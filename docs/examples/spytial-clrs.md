# CLRS Notebook Examples

[`spytial-clrs`](https://github.com/sidprasad/spytial-clrs) is a Jupyter
notebook collection. It implements the data structures from the **CLRS
algorithms textbook** (Cormen, Leiserson, Rivest, Stein) with Spytial.
Each notebook is organized by one CLRS chapter and covers one or more
textbook structures. The notebook declares the spatial constraints that
make each structure legible.

## What's in it

| Chapter | Structures | Notebook |
| --- | --- | --- |
| 6, 19 | Max heap, Fibonacci heap | `heaps.ipynb` |
| 10 | Stacks, queues | `stacksqueues.ipynb` |
| 10.2 | Singly, doubly, circular linked lists | `linked-lists.ipynb` |
| 11 | Direct-address and chained hash tables | `hash-tables.ipynb` |
| 12, 13, 14, 14.3, 18, 20 | BST, red-black, order statistic, interval, B-tree, van Emde Boas | `trees.ipynb` |
| 15.2 | Matrix-chain memoization tables | `memoization.ipynb` |
| 16.3 | Huffman codes | `huffman.ipynb` |
| 21.3 | Disjoint-set forests (forest and set views) | `disjoint-sets.ipynb` |
| 22, 22.4, 22.5, 23 | Graphs, topological sort, strongly connected components, MST | `graphs.ipynb` |

The collection also contains BDDs in `simple-bdd.ipynb`.

## Run the notebooks

The collection can be used in three ways. No local installation is
necessary beyond the notebooks themselves.

**Docker** (no local setup):

```bash
docker pull sidprasad/spytial-clrs:latest
docker run -p 8888:8888 sidprasad/spytial-clrs
# open http://localhost:8888
```

**JupyterLite** (in-browser, no installation): refer to the
[`spytial-clrs` README](https://github.com/sidprasad/spytial-clrs) for the
deployed link.

**Local clone**:

```bash
git clone https://github.com/sidprasad/spytial-clrs
cd spytial-clrs
pip install -r requirements.txt
jupyter notebook src/
```

## Reading guide

Use the notebooks as a guide, based on the structure to visualize:

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

- Start with `stacksqueues.ipynb` or `linked-lists.ipynb` for an
  introduction to Spytial.
- Browse `trees.ipynb` and `graphs.ipynb` for more complex layouts and
  more advanced operation combinations.
- Use the notebook closest to the target data shape as a template for a
  first diagram.
