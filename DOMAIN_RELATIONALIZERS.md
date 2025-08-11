# Domain-Specific Relationalizers

This document demonstrates the domain-specific relationalizers added to sPyTial for popular Python libraries.

## Overview

sPyTial now includes specialized relationalizers for several popular domains:

- **Pydantic**: Data validation and serialization models
- **Attrs**: Python classes without boilerplate 
- **PyTorch**: Machine learning tensors and neural network modules
- **Pandas**: Data analysis DataFrames and Series
- **NetworkX**: Graph analysis and network structures
- **ANTLR**: Parse trees from language processing
- **Z3**: SMT solver models (enhanced existing support)

These relationalizers are automatically registered when the corresponding library is available, providing domain-aware visualizations with no additional configuration.

## Pydantic Models

```python
import spytial
from pydantic import BaseModel
from typing import List, Optional

class Address(BaseModel):
    street: str
    city: str
    zip_code: str

class Person(BaseModel):
    name: str
    age: int
    email: Optional[str] = None
    address: Optional[Address] = None
    friends: List[str] = []

# Create nested data model
address = Address(street="123 Main St", city="Boston", zip_code="02101")
person = Person(
    name="Alice Smith",
    age=30,
    email="alice@example.com", 
    address=address,
    friends=["Bob", "Charlie"]
)

# Visualize with domain-aware layout
spytial.diagram(person)
```

## Attrs Classes

```python
import spytial
import attr

@attr.s
class Point:
    x = attr.ib()
    y = attr.ib()
    
@attr.s  
class Shape:
    name = attr.ib()
    points = attr.ib(factory=list)

# Create structured data
triangle = Shape(
    name="triangle",
    points=[Point(0, 0), Point(1, 0), Point(0.5, 1)]
)

# Visualize attrs-decorated classes
spytial.diagram(triangle)
```

## PyTorch Models

```python
import spytial
import torch
import torch.nn as nn

class SimpleNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(3, 16, 3)
        self.pool = nn.MaxPool2d(2)
        self.conv2 = nn.Conv2d(16, 32, 3)
        self.fc1 = nn.Linear(32 * 6 * 6, 120)
        self.fc2 = nn.Linear(120, 84) 
        self.fc3 = nn.Linear(84, 10)

    def forward(self, x):
        x = self.pool(torch.relu(self.conv1(x)))
        x = self.pool(torch.relu(self.conv2(x)))
        x = x.view(-1, 32 * 6 * 6)
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        x = self.fc3(x)
        return x

net = SimpleNet()

# Visualize neural network architecture
spytial.diagram(net)

# Also visualize tensors
tensor = torch.randn(3, 4, 5)
spytial.diagram(tensor)
```

## Pandas Data Structures

```python
import spytial
import pandas as pd

# Create DataFrame
df = pd.DataFrame({
    'Name': ['Alice', 'Bob', 'Charlie', 'Diana'],
    'Age': [25, 30, 35, 28],
    'Department': ['Engineering', 'Sales', 'Engineering', 'Marketing'],
    'Salary': [75000, 65000, 85000, 70000]
})

# Visualize DataFrame structure
spytial.diagram(df)

# Visualize Series
ages = df['Age']
spytial.diagram(ages)
```

## NetworkX Graphs

```python
import spytial
import networkx as nx

# Create directed graph
G = nx.DiGraph()
G.add_edges_from([
    ('A', 'B'), ('A', 'C'),
    ('B', 'D'), ('C', 'D'),
    ('D', 'E')
])

# Add node attributes
nx.set_node_attributes(G, {
    'A': {'type': 'input'},
    'E': {'type': 'output'}, 
    'B': {'type': 'process'},
    'C': {'type': 'process'},
    'D': {'type': 'merge'}
})

# Visualize graph structure
spytial.diagram(G)

# Works with various graph types
undirected = nx.karate_club_graph()
spytial.diagram(undirected)
```

## ANTLR Parse Trees

```python
# Note: Requires ANTLR runtime and generated parser
import spytial
from antlr4 import *
from your_grammar import YourLexer, YourParser

# Parse input text
input_text = "your expression here"
input_stream = InputStream(input_text)
lexer = YourLexer(input_stream)
stream = CommonTokenStream(lexer)
parser = YourParser(stream)

# Get parse tree
tree = parser.your_start_rule()

# Visualize parse tree structure
spytial.diagram(tree)
```

## Installation

All domain-specific relationalizers work with optional dependencies:

```bash
# Core installation
pip install spytial

# Optional dependencies for enhanced functionality
pip install pydantic      # For Pydantic models
pip install attrs         # For attrs classes  
pip install torch         # For PyTorch tensors/modules
pip install pandas        # For DataFrame/Series
pip install networkx      # For graph structures
pip install antlr4-python3-runtime  # For parse trees
```

## Technical Details

### Priority System

Domain-specific relationalizers are registered with higher priorities than generic ones:

- Pandas DataFrames: Priority 17
- NetworkX Graphs: Priority 16  
- Pydantic Models: Priority 15
- Attrs Classes: Priority 14
- PyTorch Tensors: Priority 13
- PyTorch Modules: Priority 12
- ANTLR Parse Trees: Priority 11
- Generic objects: Priority 5

### Graceful Degradation

If a domain library is not installed:
- The relationalizer is not registered
- Objects fall back to generic visualization
- No errors or warnings are generated

### Custom Relationalizers

You can create your own domain-specific relationalizers:

```python
from spytial import RelationalizerBase, relationalizer, Atom, Relation

@relationalizer(priority=100)  # Use priority >= 100 for custom ones
class MyLibraryRelationalizer(RelationalizerBase):
    def can_handle(self, obj):
        return isinstance(obj, MyLibraryClass)
    
    def relationalize(self, obj, walker_func):
        atom = Atom(
            id=walker_func._get_id(obj),
            type="MyLibraryObject", 
            label=f"MyObj({obj.name})"
        )
        
        relations = []
        for field_name, value in obj.get_fields():
            vid = walker_func(value)
            relations.append(
                Relation(name=field_name, source_id=atom.id, target_id=vid)
            )
            
        return atom, relations
```