# Evaluator

`spytial.evaluate()` renders a lightweight evaluator view that shows the serialized data structure. It's useful for validating how your object is being interpreted before diagramming or when debugging relationalizers.

## Basic usage

```python
import spytial

spytial.evaluate({"total": 3, "items": [1, 2, 3]})
```

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
from typing import Annotated, Dict
from spytial import Attribute

Typed = Annotated[Dict[str, int], Attribute(label="Totals")]
spytial.evaluate({"apples": 2}, as_type=Typed)
```
