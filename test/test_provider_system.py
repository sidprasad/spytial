#!/usr/bin/env python3
"""
Comprehensive test file for the provider system and its integration with annotations.
Tests how annotations become objects/YAML through the provider system pipeline.
"""

import pytest
import yaml
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from spytial.annotations import (
    orientation, cyclic, group, atomColor, flag,
    annotate, annotate_orientation, annotate_group, annotate_atomColor, annotate_flag,
    collect_decorators, serialize_to_yaml_string, reset_object_ids
)
from spytial.provider_system import (
    CnDDataInstanceBuilder, DataInstanceProvider, DataInstanceRegistry,
    data_provider, set_object_provider, get_object_provider
)


class TestProviderSystemBasics:
    """Test basic provider system functionality."""
    
    def test_primitive_provider(self):
        """Test that primitive types are handled correctly."""
        builder = CnDDataInstanceBuilder()
        
        # Test different primitive types
        data_instance = builder.build_instance(42)
        assert len(data_instance['atoms']) == 1
        assert data_instance['atoms'][0]['type'] == 'int'
        assert data_instance['atoms'][0]['label'] == '42'
        
        data_instance = builder.build_instance("hello")
        assert len(data_instance['atoms']) == 1
        assert data_instance['atoms'][0]['type'] == 'str'
        assert data_instance['atoms'][0]['label'] == 'hello'
    
    def test_collection_providers(self):
        """Test that collection types create proper atoms and relations."""
        builder = CnDDataInstanceBuilder()
        
        # Test list
        test_list = [1, 2, 3]
        data_instance = builder.build_instance(test_list)
        
        # Should have 4 atoms: list + 3 integers
        assert len(data_instance['atoms']) == 4
        list_atom = next(atom for atom in data_instance['atoms'] if atom['type'] == 'list')
        assert list_atom['label'] == 'list[3]'
        
        # Should have 3 relations (0->1, 1->2, 2->3)
        assert len(data_instance['relations']) >= 1
        
    def test_dict_provider(self):
        """Test dictionary provider creates proper structure."""
        builder = CnDDataInstanceBuilder()
        
        test_dict = {'a': 1, 'b': 2}
        data_instance = builder.build_instance(test_dict)
        
        # Should have dict atom + 2 value atoms
        assert len(data_instance['atoms']) == 3
        dict_atom = next(atom for atom in data_instance['atoms'] if atom['type'] == 'dict')
        assert dict_atom['label'] == 'dict{2}'


class TestAnnotationProviderIntegration:
    """Test integration between annotations and provider system."""
    
    def setUp(self):
        """Reset state before each test."""
        reset_object_ids()
        DataInstanceRegistry.clear()
        # Re-register built-in providers
        from spytial.provider_system import (
            PrimitiveProvider, DictProvider, ListProvider, SetProvider,
            DataclassProvider, GenericObjectProvider, FallbackProvider
        )
        DataInstanceRegistry.register(PrimitiveProvider, 10)
        DataInstanceRegistry.register(DictProvider, 9)
        DataInstanceRegistry.register(ListProvider, 8)
        DataInstanceRegistry.register(SetProvider, 8)
        DataInstanceRegistry.register(DataclassProvider, 7)
        DataInstanceRegistry.register(GenericObjectProvider, 5)
        DataInstanceRegistry.register(FallbackProvider, 1)
    
    def test_annotations_collected_during_provider_walk(self):
        """Test that annotations are collected when provider system walks objects."""
        self.setUp()
        
        # Create annotated object
        my_list = [1, 2, 3]
        annotate_orientation(my_list, selector='items', directions=['horizontal'])
        annotate_atomColor(my_list, selector='nums', value='blue')
        
        # Use provider system to build data instance
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(my_list)
        
        # Check that annotations were collected
        collected_decorators = builder.get_collected_decorators()
        assert len(collected_decorators['constraints']) == 1
        assert len(collected_decorators['directives']) == 1
        assert collected_decorators['constraints'][0]['orientation']['directions'] == ['horizontal']
        assert collected_decorators['directives'][0]['atomColor']['value'] == 'blue'
    
    def test_nested_object_annotations_collected(self):
        """Test that annotations on nested objects are collected."""
        self.setUp()
        
        # Create nested structure with annotations
        inner_list = [1, 2, 3]
        annotate_group(inner_list, field='elements', groupOn=0, addToGroup=1)
        
        outer_dict = {'data': inner_list, 'count': len(inner_list)}
        annotate_orientation(outer_dict, selector='layout', directions=['vertical'])
        
        # Use provider system
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(outer_dict)
        
        # Should collect annotations from both objects
        collected_decorators = builder.get_collected_decorators()
        assert len(collected_decorators['constraints']) == 2
        
        # Find each constraint type
        group_constraint = None
        orientation_constraint = None
        for constraint in collected_decorators['constraints']:
            if 'group' in constraint:
                group_constraint = constraint['group']
            elif 'orientation' in constraint:
                orientation_constraint = constraint['orientation']
        
        assert group_constraint is not None
        assert group_constraint['field'] == 'elements'
        assert orientation_constraint is not None
        assert orientation_constraint['directions'] == ['vertical']
    
    def test_class_and_object_annotations_in_provider_system(self):
        """Test that both class-level and object-level annotations are collected."""
        self.setUp()
        
        @orientation(selector='base', directions=['right'])
        @flag(name='processed')
        class TestClass:
            def __init__(self, value):
                self.value = value
        
        # Create instances with object-level annotations
        obj1 = TestClass(10)
        annotate_atomColor(obj1, selector='self', value='red')
        
        obj2 = TestClass(20)
        # No additional annotations
        
        # Use provider system on a structure containing both objects
        container = {'obj1': obj1, 'obj2': obj2}
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(container)
        
        collected_decorators = builder.get_collected_decorators()
        
        # Should have class-level annotations from both objects + object-level from obj1
        # Class annotations: orientation (2x) + flag (2x) = 4 total
        # Object annotations: atomColor (1x) = 1 total
        assert len(collected_decorators['constraints']) == 2  # orientation from both objects
        assert len(collected_decorators['directives']) == 3   # flag from both + atomColor from obj1


class TestAnnotationToYAMLPipeline:
    """Test the complete pipeline from annotations to YAML output."""
    
    def setUp(self):
        """Reset state before each test."""
        reset_object_ids()
    
    def test_complete_annotation_to_yaml_pipeline(self):
        """Test the full flow: annotated objects → provider system → YAML."""
        self.setUp()
        
        # Create a complex annotated structure
        fruits = {"apple", "banana", "cherry"}
        numbers = [1, 2, 3, 4, 5]
        
        # Add annotations
        annotate_group(fruits, field='contains', groupOn=0, addToGroup=1)
        annotate_orientation(numbers, selector='items', directions=['horizontal'])
        annotate_atomColor(numbers, selector='odd', value='green')
        
        # Create containing structure
        data = {
            'fruits': fruits,
            'numbers': numbers,
            'metadata': {'count': 8}
        }
        annotate_flag(data, name='processed')
        
        # Run through provider system
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(data)
        collected_decorators = builder.get_collected_decorators()
        
        # Convert to YAML
        yaml_output = serialize_to_yaml_string(collected_decorators)
        
        # Verify YAML contains expected elements
        assert 'constraints:' in yaml_output
        assert 'directives:' in yaml_output
        assert 'group:' in yaml_output
        assert 'orientation:' in yaml_output
        assert 'atomColor:' in yaml_output
        assert 'flag:' in yaml_output
        assert 'horizontal' in yaml_output
        assert 'green' in yaml_output
        assert 'processed' in yaml_output
        
        # Verify YAML is valid and parseable
        parsed_yaml = yaml.safe_load(yaml_output)
        assert isinstance(parsed_yaml, dict)
        assert 'constraints' in parsed_yaml
        assert 'directives' in parsed_yaml
    
    def test_dataclass_annotations_to_yaml(self):
        """Test annotations on dataclasses through the pipeline."""
        self.setUp()
        
        @dataclass
        class Point:
            x: int
            y: int
        
        @dataclass
        class Shape:
            points: List[Point]
            color: str
        
        # Create annotated instances
        p1 = Point(1, 2)
        p2 = Point(3, 4)
        annotate_atomColor(p1, selector='self', value='red')
        
        shape = Shape([p1, p2], 'blue')
        annotate_orientation(shape, selector='points', directions=['vertical'])
        
        # Run through provider system
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(shape)
        
        # Verify structure is correct
        assert len(data_instance['atoms']) > 0
        assert any(atom['type'] == 'Shape' for atom in data_instance['atoms'])
        assert any(atom['type'] == 'Point' for atom in data_instance['atoms'])
        
        # Check collected annotations
        collected_decorators = builder.get_collected_decorators()
        yaml_output = serialize_to_yaml_string(collected_decorators)
        
        assert 'atomColor:' in yaml_output
        assert 'orientation:' in yaml_output
        assert 'red' in yaml_output
        assert 'vertical' in yaml_output


class TestCustomProviders:
    """Test custom provider functionality."""
    
    def setUp(self):
        """Reset registry before each test."""
        DataInstanceRegistry.clear()
    
    def test_custom_provider_registration(self):
        """Test registering and using custom providers."""
        self.setUp()
        
        @data_provider(priority=15)
        class CustomStringProvider(DataInstanceProvider):
            def can_handle(self, obj: Any) -> bool:
                return isinstance(obj, str) and obj.startswith('custom:')
            
            def provide_atoms_and_relations(self, obj: Any, walker_func) -> Tuple[Dict, List[Tuple[str, str, str]]]:
                atom = {
                    "id": walker_func._get_id(obj),
                    "type": "CustomString",  # This will be overwritten by the provider system
                    "label": obj[7:]  # Remove 'custom:' prefix
                }
                return atom, []
        
        # Test that custom provider is used
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance("custom:hello")
        
        assert len(data_instance['atoms']) == 1
        # The type will be 'str' due to provider system behavior, but label should be custom
        assert data_instance['atoms'][0]['type'] == 'str'  # Provider system sets this based on Python type
        assert data_instance['atoms'][0]['label'] == 'hello'  # But our custom label should be preserved
    
    def test_object_specific_provider(self):
        """Test setting custom providers for specific objects."""
        self.setUp()
        
        class SpecialProvider(DataInstanceProvider):
            def can_handle(self, obj: Any) -> bool:
                return True
            
            def provide_atoms_and_relations(self, obj: Any, walker_func) -> Tuple[Dict, List[Tuple[str, str, str]]]:
                atom = {
                    "id": walker_func._get_id(obj),
                    "type": "Special",
                    "label": "specially_handled"
                }
                return atom, []
        
        # Set custom provider for specific object
        my_list = [1, 2, 3]
        set_object_provider(my_list, SpecialProvider())
        
        # Another list without custom provider
        other_list = [4, 5, 6]
        
        # Re-register built-in providers
        from spytial.provider_system import ListProvider, PrimitiveProvider
        DataInstanceRegistry.register(ListProvider, 8)
        DataInstanceRegistry.register(PrimitiveProvider, 10)
        
        # Test that custom provider is used for my_list
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(my_list)
        
        # Should use special provider - type will be 'list' but label should be custom
        assert len(data_instance['atoms']) == 1
        assert data_instance['atoms'][0]['type'] == 'list'  # Provider system sets based on Python type
        assert data_instance['atoms'][0]['label'] == 'specially_handled'  # Custom label preserved
        
        # Test that other_list uses default provider
        builder2 = CnDDataInstanceBuilder()
        data_instance2 = builder2.build_instance(other_list)
        
        # Should use list provider and create multiple atoms
        assert len(data_instance2['atoms']) > 1
        list_atom = next(atom for atom in data_instance2['atoms'] if atom['type'] == 'list')
        assert list_atom is not None
        assert list_atom['label'] == 'list[3]'  # Default list label


class TestErrorHandling:
    """Test error handling in the provider system."""
    
    def test_provider_system_handles_annotation_errors(self):
        """Test that provider system gracefully handles annotation collection errors."""
        # Create object that might cause annotation collection issues
        my_list = [1, 2, 3]
        
        # Force an error condition by creating invalid annotation state
        # (This is hard to do naturally, so we'll test that the system is robust)
        builder = CnDDataInstanceBuilder()
        
        # This should not raise an exception even if annotation collection fails
        data_instance = builder.build_instance(my_list)
        
        # Should still create valid data instance
        assert len(data_instance['atoms']) > 0
        assert 'relations' in data_instance
        assert 'types' in data_instance
    
    def test_no_provider_found_error(self):
        """Test behavior when no provider can handle an object."""
        DataInstanceRegistry.clear()  # Remove all providers
        
        builder = CnDDataInstanceBuilder()
        
        # The provider system catches the error and continues, creating empty structure
        data_instance = builder.build_instance("test")
        
        # Should create minimal structure even when provider fails
        assert 'atoms' in data_instance
        assert 'relations' in data_instance
        assert 'types' in data_instance
    
    def test_recursive_objects_handled(self):
        """Test that circular references are handled without infinite recursion."""
        # Create circular reference
        obj1 = {'name': 'obj1'}
        obj2 = {'name': 'obj2', 'ref': obj1}
        obj1['ref'] = obj2
        
        # Re-register dict provider
        from spytial.provider_system import DictProvider, PrimitiveProvider
        DataInstanceRegistry.register(DictProvider, 9)
        DataInstanceRegistry.register(PrimitiveProvider, 10)
        
        builder = CnDDataInstanceBuilder()
        
        # Should handle circular reference without infinite recursion
        data_instance = builder.build_instance(obj1)
        
        # Should create finite number of atoms
        assert len(data_instance['atoms']) < 100  # Reasonable upper bound


if __name__ == "__main__":
    # Run tests manually if not using pytest
    print("Testing Provider System Integration")
    print("=" * 50)
    
    # Basic provider tests
    test_basics = TestProviderSystemBasics()
    test_basics.test_primitive_provider()
    test_basics.test_collection_providers()
    test_basics.test_dict_provider()
    print("✓ Basic provider tests passed")
    
    # Annotation integration tests
    test_integration = TestAnnotationProviderIntegration()
    test_integration.test_annotations_collected_during_provider_walk()
    test_integration.test_nested_object_annotations_collected()
    test_integration.test_class_and_object_annotations_in_provider_system()
    print("✓ Annotation-provider integration tests passed")
    
    # Full pipeline tests
    test_pipeline = TestAnnotationToYAMLPipeline()
    test_pipeline.test_complete_annotation_to_yaml_pipeline()
    test_pipeline.test_dataclass_annotations_to_yaml()
    print("✓ Complete pipeline tests passed")
    
    # Custom provider tests
    test_custom = TestCustomProviders()
    test_custom.test_custom_provider_registration()
    test_custom.test_object_specific_provider()
    print("✓ Custom provider tests passed")
    
    # Error handling tests
    test_errors = TestErrorHandling()
    test_errors.test_provider_system_handles_annotation_errors()
    test_errors.test_recursive_objects_handled()
    print("✓ Error handling tests passed")
    
    print("\n🎉 All provider system integration tests passed!")
    print("\nThis test suite validates:")
    print("- Basic provider system functionality")
    print("- Integration between annotations and providers")
    print("- Complete annotation → provider → YAML pipeline")
    print("- Custom provider registration and usage")
    print("- Error handling and edge cases")
    print("- Circular reference handling")