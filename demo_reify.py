#!/usr/bin/env python
"""
Demonstration script for the new reify functionality in sPyTial.

This script shows how the reify method can reconstruct Python objects
from CnD data instances, enabling full round-trip serialization.
"""

import spytial


def demo_basic_reify():
    """Demonstrate basic reify functionality with primitive and collection types."""
    print("=== BASIC REIFY DEMO ===")
    
    builder = spytial.CnDDataInstanceBuilder()
    
    # Test data with various types
    test_data = {
        "name": "sPyTial Reify Demo",
        "version": 1.0,
        "features": ["visualization", "spatial", "constraints"],
        "settings": {
            "debug": True,
            "max_depth": 100,
            "timeout": None
        },
        "tags": {"python", "library", "research"}
    }
    
    print("Original data:")
    print(test_data)
    
    # Build data instance
    data_instance = builder.build_instance(test_data)
    print(f"\nData instance created with {len(data_instance['atoms'])} atoms")
    
    # Reify back to object
    reified_data = builder.reify(data_instance)
    print("\nReified data:")
    print(reified_data)
    
    # Validate round-trip
    success = reified_data == test_data
    print(f"\n✓ Round-trip successful: {success}")
    return success


def demo_custom_objects():
    """Demonstrate reify with custom Python objects."""
    print("\n=== CUSTOM OBJECTS DEMO ===")
    
    class Person:
        def __init__(self, name, age, skills=None):
            self.name = name
            self.age = age
            self.skills = skills or []
        
        def __repr__(self):
            return f"Person(name='{self.name}', age={self.age}, skills={self.skills})"
    
    # Create test objects
    original_person = Person("Alice", 30, ["Python", "sPyTial", "Visualization"])
    
    print("Original person:")
    print(original_person)
    
    # Round-trip through reify
    builder = spytial.CnDDataInstanceBuilder()
    data_instance = builder.build_instance(original_person)
    reified_person = builder.reify(data_instance)
    
    print("\nReified person:")
    print(f"Type: {type(reified_person).__name__}")
    print(f"Name: {reified_person.name}")
    print(f"Age: {reified_person.age}")
    print(f"Skills: {reified_person.skills}")
    
    # Validate attributes
    success = (reified_person.name == original_person.name and
               reified_person.age == original_person.age and
               reified_person.skills == original_person.skills)
    print(f"\n✓ Object reconstruction successful: {success}")
    return success


def demo_extensibility():
    """Demonstrate the extensibility mechanism with custom reifiers."""
    print("\n=== EXTENSIBILITY DEMO ===")
    
    class Point:
        def __init__(self, x=0, y=0):
            self.x = x
            self.y = y
        
        def __eq__(self, other):
            return isinstance(other, Point) and self.x == other.x and self.y == other.y
        
        def __repr__(self):
            return f"Point({self.x}, {self.y})"
    
    # Custom reifier for Point class
    def point_reifier(atom, relations, reify_atom):
        """Custom reifier that properly reconstructs Point objects."""
        point = Point()
        for rel_name, target_ids in relations.items():
            if rel_name == "x" and target_ids:
                point.x = reify_atom(target_ids[0])
            elif rel_name == "y" and target_ids:
                point.y = reify_atom(target_ids[0])
        return point
    
    # Register custom reifier
    builder = spytial.CnDDataInstanceBuilder()
    builder.register_reifier("Point", point_reifier)
    
    print(f"Registered reifiers: {builder.list_reifiers()}")
    
    # Test with custom object
    original_point = Point(10, 20)
    print(f"Original point: {original_point}")
    
    # Round-trip with custom reifier
    data_instance = builder.build_instance(original_point)
    reified_point = builder.reify(data_instance)
    
    print(f"Reified point: {reified_point}")
    print(f"Type: {type(reified_point).__name__}")
    
    success = reified_point == original_point
    print(f"\n✓ Custom reifier successful: {success}")
    return success


def demo_complex_nested():
    """Demonstrate reify with complex nested structures."""
    print("\n=== COMPLEX NESTED DEMO ===")
    
    # Complex nested data structure
    complex_data = {
        "project": "sPyTial",
        "metadata": {
            "version": "1.0.0",
            "authors": ["Alice", "Bob"],
            "license": "MIT"
        },
        "components": [
            {
                "name": "Visualizer",
                "files": ["visualizer.py", "templates.html"],
                "dependencies": {"jinja2", "pyyaml"}
            },
            {
                "name": "Provider System", 
                "files": ["provider_system.py"],
                "dependencies": set()
            }
        ],
        "tests": {
            "unit": 16,
            "integration": 5,
            "coverage": 95.5
        }
    }
    
    print("Original complex data structure:")
    print(f"Project: {complex_data['project']}")
    print(f"Version: {complex_data['metadata']['version']}")
    print(f"Components: {len(complex_data['components'])}")
    print(f"Test coverage: {complex_data['tests']['coverage']}%")
    
    # Round-trip through reify
    builder = spytial.CnDDataInstanceBuilder()
    data_instance = builder.build_instance(complex_data)
    reified_data = builder.reify(data_instance)
    
    print(f"\nData instance: {len(data_instance['atoms'])} atoms, {len(data_instance['relations'])} relations")
    
    print("\nReified complex data structure:")
    print(f"Project: {reified_data['project']}")
    print(f"Version: {reified_data['metadata']['version']}")
    print(f"Components: {len(reified_data['components'])}")
    print(f"Test coverage: {reified_data['tests']['coverage']}%")
    
    success = reified_data == complex_data
    print(f"\n✓ Complex nested reification successful: {success}")
    return success


def main():
    """Run all reify demonstrations."""
    print("🎯 sPyTial Reify Functionality Demonstration")
    print("=" * 50)
    
    results = [
        demo_basic_reify(),
        demo_custom_objects(), 
        demo_extensibility(),
        demo_complex_nested()
    ]
    
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print(f"✅ Passed: {sum(results)}/{len(results)}")
    if all(results):
        print("🎉 All reify demonstrations successful!")
        print("\nThe reify method successfully reconstructs Python objects from CnD data instances,")
        print("enabling full round-trip serialization and providing extensibility for custom types.")
    else:
        print("❌ Some demonstrations failed")
    
    return all(results)


if __name__ == "__main__":
    main()