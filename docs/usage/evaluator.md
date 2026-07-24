# Evaluator

`spytial.evaluate()` renders a lightweight view of the serialized data
instance. Use this function to check how Python objects translate before
layout work begins.

## Basic usage

```python
import spytial

spytial.evaluate({"total": 3, "items": [1, 2, 3]})
```

## When it helps

The evaluator helps in these cases:

- a custom class does not relationalize as expected
- a selector does not match as expected
- a custom relationalizer is being written, and its emitted atoms and relations need inspection

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
