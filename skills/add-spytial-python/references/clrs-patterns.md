# CLRS Patterns

Use these patterns as first defaults for standard data structures before inventing new selectors.

## Linked structures (stack/queue/list)

Recommended defaults:

- Linear flow: `orientation(selector="next", directions=["directlyRight"])`
- Show payload: `attribute(field="data")`
- Hide sentinels/primitive noise: `hideAtom(selector="NoneType + int + str")` (adjust per model)

```python
import spytial

@spytial.orientation(selector="next", directions=["directlyRight"])
@spytial.attribute(field="data")
class Node:
    def __init__(self, data, nxt=None):
        self.data = data
        self.next = nxt
```

## Trees (BST/RB/heap-like)

Recommended defaults:

- Left branch: `orientation(..., ["below", "left"])`
- Right branch: `orientation(..., ["below", "right"])`
- Optional sibling alignment: `align(..., direction="horizontal")`
- Surface key metadata with `attribute(field="key")`

```python
import spytial

@spytial.orientation(selector="left & (TreeNode->TreeNode)", directions=["below", "left"])
@spytial.orientation(selector="right & (TreeNode->TreeNode)", directions=["below", "right"])
@spytial.attribute(field="key")
class TreeNode:
    def __init__(self, key, left=None, right=None):
        self.key = key
        self.left = left
        self.right = right
```

## Graphs from adjacency structures

Recommended defaults:

- Derive explicit edges with `inferredEdge`
- Hide raw container atoms (`list`, tuples, helper wrappers)
- Keep node labels through `attribute(field="key")` or domain field names

```python
import spytial

graph = spytial.inferredEdge(
    selector="{a, b : Node | b in a.neighbors}",
    name="edge",
)(graph_obj)
graph = spytial.hideAtom(selector="list + tuple")(graph)
spytial.diagram(graph)
```

## Hash-table and bucketed layouts

Recommended defaults:

- Group buckets with selector-based `group(...)`
- Orient chain relations directly left/right
- Hide housekeeping fields such as `prev` where needed

Selectors from CLRS-style examples often look like:

- `group(selector="(NoneType.~key) - ((iden & next).Node)", name="T")`
- `orientation(selector="next & (Node->Node)", directions=["directlyRight"])`

## Matrix / DP table layouts

Recommended defaults:

- Build row and column selectors
- `align` rows and columns
- Add directional orientation across row/column deltas

Pattern from memoization examples:

- `align(selector=SAME_ROW, direction="horizontal")`
- `align(selector=SAME_COL, direction="vertical")`
- `orientation(selector=DIFF_ROWS, directions=["below"])`
- `orientation(selector=DIFF_COLS, directions=["right"])`

## Disjoint sets / grouped regions

Recommended defaults:

- Group by selector to expose set membership
- Hide technical atoms (`int`, helper lists) after structure checks
- Keep representative fields visible with `attribute(...)`

## Picking the closest notebook

Map use case to source notebook:

- Stacks/queues: `spytial-clrs/src/stacksqueues.ipynb`
- Linked lists: `spytial-clrs/src/linked-lists.ipynb`
- Heaps: `spytial-clrs/src/heaps.ipynb`
- Trees: `spytial-clrs/src/trees.ipynb`
- Hash tables: `spytial-clrs/src/hash-tables.ipynb`
- Graphs: `spytial-clrs/src/graphs.ipynb`
- Disjoint sets: `spytial-clrs/src/disjoint-sets.ipynb`
- Memoization tables: `spytial-clrs/src/memoization.ipynb`
