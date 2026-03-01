# Evaluator

`spytial.evaluate()` renders a lightweight view of the serialized data instance. Use it when you want to check how Python objects are being translated before you worry about layout.

## Basic usage

```python
import spytial

spytial.evaluate({"total": 3, "items": [1, 2, 3]})
```

## When it helps

The evaluator is especially useful when:

- a custom class is not relationalizing the way you expect
- an annotation selector is not matching what you think it is matching
- you are writing a custom relationalizer and want to inspect the emitted atoms and relations

## Display methods

```python
spytial.evaluate(data, method="browser")  # open a new tab
spytial.evaluate(data, method="file")     # save as cnd_evaluator.html
spytial.evaluate(data, method="inline")   # force notebook output
```

## Size options

```python
spytial.evaluate(data, width=800, height=300)
```

## Using annotated types

```python
from typing import Dict, List
from spytial import AnnotatedType, InferredEdge, Orientation

Graph = AnnotatedType(
    Dict[int, List[int]],
    InferredEdge(name="edge", selector="values"),
    Orientation(selector="values", directions=["right"]),
)

spytial.evaluate({0: [1, 2], 1: [3]}, as_type=Graph)
```

## Recommended workflow

Use `evaluate()` first when debugging serialization, then switch to `diagram()` once the data instance looks right.
