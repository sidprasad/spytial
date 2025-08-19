"""Tests for the reify functionality in CnDDataInstanceBuilder."""

import pytest
from spytial import CnDDataInstanceBuilder


class TestReifyBasic:
    """Test basic reify functionality with primitive types and simple structures."""
    
    def test_reify_primitive_types(self):
        """Test reification of primitive Python types."""
        builder = CnDDataInstanceBuilder()
        
        # Test different primitive types
        test_values = [
            "hello world",
            42,
            3.14,
            True,
            False,
            None
        ]
        
        for original_value in test_values:
            # Build data instance
            data_instance = builder.build_instance(original_value)
            
            # Reify back to object
            reified_value = builder.reify(data_instance)
            
            # Should be equal to original
            assert reified_value == original_value, f"Failed for {original_value}"
            assert type(reified_value) == type(original_value), f"Type mismatch for {original_value}"
    
    def test_reify_simple_list(self):
        """Test reification of simple lists."""
        builder = CnDDataInstanceBuilder()
        
        original_list = [1, 2, 3, "hello", True]
        data_instance = builder.build_instance(original_list)
        reified_list = builder.reify(data_instance)
        
        assert reified_list == original_list
        assert type(reified_list) == list
    
    def test_reify_simple_dict(self):
        """Test reification of simple dictionaries."""
        builder = CnDDataInstanceBuilder()
        
        original_dict = {
            "name": "John",
            "age": 30,
            "active": True
        }
        data_instance = builder.build_instance(original_dict)
        reified_dict = builder.reify(data_instance)
        
        assert reified_dict == original_dict
        assert type(reified_dict) == dict
    
    def test_reify_tuple(self):
        """Test reification of tuples."""
        builder = CnDDataInstanceBuilder()
        
        original_tuple = (1, "hello", 3.14)
        data_instance = builder.build_instance(original_tuple)
        reified_tuple = builder.reify(data_instance)
        
        assert reified_tuple == original_tuple
        assert type(reified_tuple) == tuple
    
    def test_reify_set(self):
        """Test reification of sets."""
        builder = CnDDataInstanceBuilder()
        
        original_set = {1, 2, 3, "hello"}
        data_instance = builder.build_instance(original_set)
        reified_set = builder.reify(data_instance)
        
        assert reified_set == original_set
        assert type(reified_set) == set


class TestReifyNested:
    """Test reify functionality with nested data structures."""
    
    def test_reify_nested_dict(self):
        """Test reification of nested dictionaries."""
        builder = CnDDataInstanceBuilder()
        
        original_data = {
            "person": {
                "name": "John",
                "age": 30,
                "address": {
                    "street": "123 Main St",
                    "city": "Boston"
                }
            },
            "hobbies": ["reading", "cycling"]
        }
        
        data_instance = builder.build_instance(original_data)
        reified_data = builder.reify(data_instance)
        
        assert reified_data == original_data
    
    def test_reify_nested_list(self):
        """Test reification of nested lists."""
        builder = CnDDataInstanceBuilder()
        
        original_data = [
            [1, 2, 3],
            ["a", "b", "c"],
            [True, False]
        ]
        
        data_instance = builder.build_instance(original_data)
        reified_data = builder.reify(data_instance)
        
        assert reified_data == original_data
    
    def test_reify_mixed_structures(self):
        """Test reification of mixed data structures."""
        builder = CnDDataInstanceBuilder()
        
        original_data = {
            "numbers": [1, 2, 3],
            "settings": {
                "debug": True,
                "timeout": 30.5
            },
            "tags": {"python", "testing", "reify"}
        }
        
        data_instance = builder.build_instance(original_data)
        reified_data = builder.reify(data_instance)
        
        # Compare each part since set order may vary
        assert reified_data["numbers"] == original_data["numbers"]
        assert reified_data["settings"] == original_data["settings"]
        assert reified_data["tags"] == original_data["tags"]


class TestReifyGenericObjects:
    """Test reify functionality with generic Python objects."""
    
    def test_reify_simple_object(self):
        """Test reification of simple objects with attributes."""
        builder = CnDDataInstanceBuilder()
        
        class Person:
            def __init__(self, name, age):
                self.name = name
                self.age = age
        
        original_person = Person("John", 30)
        data_instance = builder.build_instance(original_person)
        reified_person = builder.reify(data_instance)
        
        # Check that attributes are preserved
        assert hasattr(reified_person, 'name')
        assert hasattr(reified_person, 'age')
        assert reified_person.name == original_person.name
        assert reified_person.age == original_person.age
    
    def test_reify_object_with_nested_data(self):
        """Test reification of objects with nested data structures."""
        builder = CnDDataInstanceBuilder()
        
        class Student:
            def __init__(self, name, grades, metadata):
                self.name = name
                self.grades = grades
                self.metadata = metadata
        
        original_student = Student(
            "Alice",
            [85, 90, 78],
            {"year": 2023, "major": "Computer Science"}
        )
        
        data_instance = builder.build_instance(original_student)
        reified_student = builder.reify(data_instance)
        
        assert reified_student.name == original_student.name
        assert reified_student.grades == original_student.grades
        assert reified_student.metadata == original_student.metadata


class TestReifyErrorHandling:
    """Test error handling in reify functionality."""
    
    def test_reify_invalid_data_instance(self):
        """Test reify with invalid data instances."""
        builder = CnDDataInstanceBuilder()
        
        # Test with non-dict
        with pytest.raises(ValueError, match="data_instance must be a dictionary"):
            builder.reify("invalid")
        
        # Test with missing keys
        with pytest.raises(ValueError, match="data_instance must contain keys"):
            builder.reify({"atoms": []})
        
        # Test with empty atoms
        with pytest.raises(ValueError, match="data_instance must contain at least one atom"):
            builder.reify({"atoms": [], "relations": []})
    
    def test_can_reify_method(self):
        """Test the can_reify helper method."""
        builder = CnDDataInstanceBuilder()
        
        # Valid data instance
        original_data = {"name": "test", "value": 42}
        data_instance = builder.build_instance(original_data)
        assert builder.can_reify(data_instance) is True
        
        # Invalid data instances
        assert builder.can_reify("invalid") is False
        assert builder.can_reify({"atoms": []}) is False
        assert builder.can_reify({"atoms": [], "relations": []}) is False
        assert builder.can_reify({"atoms": [{"invalid": "atom"}], "relations": []}) is False


class TestReifyRoundTrip:
    """Test round-trip serialization and deserialization."""
    
    def test_round_trip_complex_data(self):
        """Test that complex data can survive round-trip serialization."""
        builder = CnDDataInstanceBuilder()
        
        original_data = {
            "users": [
                {"name": "Alice", "age": 25, "active": True},
                {"name": "Bob", "age": 30, "active": False}
            ],
            "settings": {
                "debug": True,
                "max_users": 100,
                "timeout": 30.5
            },
            "tags": ["production", "api", "v2"],
            "metadata": {
                "version": "2.1.0",
                "created": "2023-01-01"
            }
        }
        
        # Forward: object -> data instance
        data_instance = builder.build_instance(original_data)
        
        # Backward: data instance -> object
        reified_data = builder.reify(data_instance)
        
        # Should be equivalent
        assert reified_data == original_data
    
    def test_round_trip_with_object_annotations(self):
        """Test round-trip with object that has been annotated."""
        import spytial
        builder = CnDDataInstanceBuilder()
        
        # Create annotated object
        test_list = [1, 2, 3, 4, 5]
        spytial.annotate_orientation(test_list, selector='items', directions=['horizontal'])
        
        # Round trip
        data_instance = builder.build_instance(test_list)
        reified_list = builder.reify(data_instance)
        
        # Data should be preserved (annotations are metadata and may not survive reification)
        assert reified_list == test_list


class TestReifyExtensibility:
    """Test extensibility mechanisms for custom reification."""
    
    def test_register_custom_reifier(self):
        """Test registering a custom reifier for a specific type."""
        builder = CnDDataInstanceBuilder()
        
        # Create a custom class and custom reifier
        class Point:
            def __init__(self, x=0, y=0):
                self.x = x
                self.y = y
            
            def __eq__(self, other):
                return isinstance(other, Point) and self.x == other.x and self.y == other.y
            
            def __repr__(self):
                return f"Point({self.x}, {self.y})"
        
        def point_reifier(atom, relations, reify_atom):
            """Custom reifier that reconstructs Point objects correctly."""
            point = Point()
            for rel_name, target_ids in relations.items():
                if rel_name == "x" and target_ids:
                    point.x = reify_atom(target_ids[0])
                elif rel_name == "y" and target_ids:
                    point.y = reify_atom(target_ids[0])
            return point
        
        # Register the custom reifier
        builder.register_reifier("Point", point_reifier)
        
        # Test that it's registered
        assert "Point" in builder.list_reifiers()
        
        # Create and serialize a Point
        original_point = Point(10, 20)
        data_instance = builder.build_instance(original_point)
        
        # Reify with custom reifier
        reified_point = builder.reify(data_instance)
        
        # Should be reconstructed correctly
        assert isinstance(reified_point, Point)
        assert reified_point == original_point
        
        # Test unregistering
        builder.unregister_reifier("Point")
        assert "Point" not in builder.list_reifiers()
    
    def test_custom_reifier_with_nested_data(self):
        """Test custom reifier with nested data structures."""
        builder = CnDDataInstanceBuilder()
        
        class Container:
            def __init__(self, name="", items=None):
                self.name = name
                self.items = items or []
            
            def __eq__(self, other):
                return (isinstance(other, Container) and 
                       self.name == other.name and 
                       self.items == other.items)
        
        def container_reifier(atom, relations, reify_atom):
            """Custom reifier for Container objects."""
            container = Container()
            for rel_name, target_ids in relations.items():
                if rel_name == "name" and target_ids:
                    container.name = reify_atom(target_ids[0])
                elif rel_name == "items" and target_ids:
                    container.items = reify_atom(target_ids[0])
            return container
        
        builder.register_reifier("Container", container_reifier)
        
        # Test with nested data
        original_container = Container("test_container", [1, 2, 3, "hello"])
        data_instance = builder.build_instance(original_container)
        reified_container = builder.reify(data_instance)
        
        assert isinstance(reified_container, Container)
        assert reified_container.name == original_container.name
        assert reified_container.items == original_container.items


if __name__ == "__main__":
    pytest.main([__file__, "-v"])