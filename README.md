# CnD Python Integration

`CnDSerializer` is a Python library designed to serialize Python-like data structures into a format compatible with the CnD (Cope and Drag) diagramming language. 

## Features
- Serialize primitive types (`int`, `float`, `str`, `bool`).
- Handle collections like `list`, `tuple`, `set`, and `frozenset`.
- Serialize dictionaries, including their keys and values.
- Support for objects with `__dict__` and `__slots__`.
- Prevent infinite recursion with cyclic references.
- Graceful handling of unsupported types.

## Installation
Clone the repository and include the `cndviz` module in your project:

```bash
# Clone the repository
git clone <repository-url>

# Navigate to the project directory
cd cnd-py
```

## Usage

### Example
```python
from cndviz.serializer import CnDSerializer

# Create an instance of the serializer
serializer = CnDSerializer()

# Example data structure
data = {
    "name": "Alice",
    "age": 30,
    "hobbies": ["reading", "cycling"],
    "attributes": {"height": 5.5, "weight": 60},
}

# Serialize the data
result = serializer.serialize(data)

# Print the serialized output
import json
print(json.dumps(result, indent=2))
```

### Output
The serialized output will look like this:
```json
{
  "atoms": [
    {"id": "n0", "type": "dict", "label": "{'name': 'Alice', 'age': 30, 'hobbies': ['reading', 'cycling'], 'attributes': {'height': 5.5, 'weight': 60}}"},
    {"id": "n1", "type": "str", "label": "name"},
    {"id": "n2", "type": "str", "label": "Alice"},
    {"id": "n3", "type": "str", "label": "age"},
    {"id": "n4", "type": "int", "label": "30"},
    {"id": "n5", "type": "str", "label": "hobbies"},
    {"id": "n6", "type": "list", "label": "['reading', 'cycling']"},
    {"id": "n7", "type": "str", "label": "reading"},
    {"id": "n8", "type": "str", "label": "cycling"},
    {"id": "n9", "type": "str", "label": "attributes"},
    {"id": "n10", "type": "dict", "label": "{'height': 5.5, 'weight': 60}"},
    {"id": "n11", "type": "str", "label": "height"},
    {"id": "n12", "type": "float", "label": "5.5"},
    {"id": "n13", "type": "str", "label": "weight"},
    {"id": "n14", "type": "int", "label": "60"}
  ],
  "relations": [
    {"name": "key", "tuples": [["n0", "n1"], ["n0", "n3"], ["n0", "n5"], ["n0", "n9"]]},
    {"name": "val", "tuples": [["n0", "n2"], ["n0", "n4"], ["n0", "n6"], ["n0", "n10"]]},
    {"name": "item", "tuples": [["n6", "n7"], ["n6", "n8"]]},
    {"name": "key", "tuples": [["n10", "n11"], ["n10", "n13"]]},
    {"name": "val", "tuples": [["n10", "n12"], ["n10", "n14"]]}
  ]
}
```

## Limitations
- Does not handle functions, modules, or file handles.
- Limited support for custom serialization methods like `__reduce__` or `__getstate__`.
- Performance may degrade for very large or deeply nested objects.

## TODO:
- Extend annotations to the entire set of directives.
- Need to add tests for the annotations and provider systems E.g. how annotations become objects / yaml.

## License
This project is licensed under the MIT License. See the LICENSE file for details.
