# N-ary Relations in sPyTial

sPyTial now supports n-ary relations - relations that can connect any number of atoms (2 or more), not just binary relations.

## Quick Start

```python
from spytial.domain_relationalizers.base import Relation

# Binary relation (unchanged)
binary = Relation(name="follows", source_id="user1", target_id="user2")

# Ternary relation (3 atoms)
ternary = Relation.from_atoms("teaches", ["instructor", "course", "semester"])

# Quaternary relation (4 atoms) 
quaternary = Relation.from_atoms("meeting", ["person1", "person2", "location", "time"])

# Any arity
nary = Relation.from_atoms("transaction", ["sender", "receiver", "amount", "currency", "timestamp"])
```

## API Reference

### Relation Class

The `Relation` class has been extended to support n-ary relations while maintaining full backward compatibility.

#### Creating Relations

**Binary Relations (unchanged)**:
```python
# Original method still works
rel = Relation(name="follows", source_id="user1", target_id="user2")

# New explicit method for clarity
rel = Relation.binary("follows", "user1", "user2")
```

**N-ary Relations**:
```python
# Create relations with any number of atoms
rel = Relation.from_atoms("relation_name", ["atom1", "atom2", "atom3", ...])
```

#### Methods

- `is_binary()` - Returns True if the relation connects exactly 2 atoms
- `arity()` - Returns the number of atoms connected by this relation
- `to_tuple()` - Returns `(name, source_id, target_id)` for binary relations only
- `to_atoms_tuple()` - Returns `(name, [atom1, atom2, ...])` for any relation

## Custom Relationalizers with N-ary Relations

```python
from spytial import RelationalizerBase, relationalizer, Atom, Relation

@relationalizer(priority=100)
class CourseRelationalizer(RelationalizerBase):
    def can_handle(self, obj):
        return (isinstance(obj, dict) and 
                'instructor' in obj and 'course' in obj and 'semester' in obj)
    
    def relationalize(self, obj, walker_func):
        course_id = walker_func._get_id(obj)
        course_atom = Atom(id=course_id, type="course", label=f"Course: {obj['course']}")
        
        # Create ternary relation: instructor teaches course in semester
        instructor_id = walker_func(obj['instructor'])
        semester_id = walker_func(obj['semester'])
        
        teaches_relation = Relation.from_atoms(
            "teaches", [instructor_id, course_id, semester_id]
        )
        
        return [course_atom], [teaches_relation]
```

## Backward Compatibility

All existing code continues to work unchanged. Binary relations created with the original API are fully compatible with the new system.

## Examples

See `demo_nary_relations.py` for comprehensive examples of n-ary relations in action.