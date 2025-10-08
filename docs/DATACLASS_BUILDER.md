# sPyTial Dataclass Builder Widget (CnD-core Integration)

## Overview

The sPyTial Dataclass Builder is a Jupyter widget that provides **visual, interactive construction** of dataclass instances using CnD-core's `structured-input-graph` component. It enables users to build complex data structures visually with spatial constraints and immediately access the result.

## Key Features

- **Visual Construction**: Uses CnD-core's graph-based visual interface
- **Spatial Annotations**: Automatically includes constraints from sPyTial decorators
- **No File I/O**: Direct JavaScript-Python communication via postMessage
- **Real-time Access**: `widget.value` always contains the current dataclass instance
- **No Timeouts**: Immediate updates when you export data

## Installation

```bash
pip install ipywidgets
jupyter nbextension enable --py widgetsnbextension
```

## Basic Usage

```python
from dataclasses import dataclass
import spytial

@dataclass
class Person:
    name: str = ""
    age: int = 0
    email: str = ""

# Create the widget
widget = spytial.dataclass_builder(Person)
widget  # Display in Jupyter

# After building and clicking "Export JSON":
person = widget.value
print(person)  # Person(name='Alice', age=30, email='alice@example.com')
```
