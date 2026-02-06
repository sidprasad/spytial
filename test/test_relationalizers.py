#!/usr/bin/env python3
"""
Test file for the new relationalizer system (Issue #27).

This file tests:
- Relationalizers must inherit from RelationalizerBase to be registered
- Built-in relationalizers work as expected
- Priority system and built-in priority reservation
- New Atom and Relation structures
- Backward compatibility with provider system
"""

import pytest
from spytial import (
    RelationalizerBase, relationalizer, Atom, Relation,
    CnDDataInstanceBuilder, diagram,
)
from spytial.provider_system import RelationalizerRegistry


def _register_built_in_relationalizers():
    """Helper to re-register built-in relationalizers after clearing registry."""
    from spytial.domain_relationalizers import (
        PrimitiveRelationalizer, DictRelationalizer, ListRelationalizer, 
        SetRelationalizer, DataclassRelationalizer, GenericObjectRelationalizer, 
        FallbackRelationalizer
    )
    RelationalizerRegistry.register(PrimitiveRelationalizer, 10)
    RelationalizerRegistry.register(DictRelationalizer, 9) 
    RelationalizerRegistry.register(ListRelationalizer, 8)
    RelationalizerRegistry.register(SetRelationalizer, 8)
    RelationalizerRegistry.register(DataclassRelationalizer, 7)
    RelationalizerRegistry.register(GenericObjectRelationalizer, 5)
    RelationalizerRegistry.register(FallbackRelationalizer, 1)
from typing import Any, List, Tuple


def test_relationalizer_inheritance_requirement():
    """Test that relationalizers must inherit from RelationalizerBase to be registered."""
    
    # This should fail - not inheriting from RelationalizerBase
    with pytest.raises(TypeError, match="Relationalizer must inherit from RelationalizerBase"):
        @relationalizer(priority=100)
        class BadRelationalizer:
            def can_handle(self, obj):
                return False
            
            def relationalize(self, obj, walker_func):
                return None, []


def test_relationalizer_inheritance_requirement_manual():
    """Test inheritance requirement without pytest."""
    ok = False
    try:
        @relationalizer(priority=100)
        class BadRelationalizer:
            def can_handle(self, obj):
                return False
            
            def relationalize(self, obj, walker_func):
                return None, []
    except TypeError as e:
        ok = "Relationalizer must inherit from RelationalizerBase" in str(e)
    except Exception:
        ok = False

    assert ok



def test_basic_relationalizer_implementation():
    """Test implementing a basic custom relationalizer."""
    
    # Save current state
    original_relationalizers = RelationalizerRegistry._relationalizers.copy()
    original_instances = RelationalizerRegistry._instances.copy()
    
    try:
        @relationalizer(priority=100)  # Custom relationalizers should use priority >= 100
        class StringLengthRelationalizer(RelationalizerBase):
            """Custom relationalizer that shows string lengths."""
            
            def can_handle(self, obj: Any) -> bool:
                return isinstance(obj, str) and len(obj) > 5
            
            def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
                atom = Atom(
                    id=walker_func._get_id(obj),
                    type="long_string",
                    label=f'"{obj[:10]}..." (len={len(obj)})'
                )
                return [atom], []
        
        # Test the relationalizer
        builder = CnDDataInstanceBuilder()
        test_string = "This is a long string for testing"
        
        # Clear registry and re-register to ensure our relationalizer is used
        RelationalizerRegistry.clear()
        _register_built_in_relationalizers()
        # Re-register our custom relationalizer since clearing removed it
        RelationalizerRegistry.register(StringLengthRelationalizer, 100)
        
        data_instance = builder.build_instance(test_string)
        
        # Find the atom for our string
        string_atom = None
        for atom in data_instance['atoms']:
            if 'long_string' in atom.get('type', ''):
                string_atom = atom
                break
        
        assert string_atom is not None
        assert 'len=33' in string_atom['label']
    
    finally:
        # Restore original state
        RelationalizerRegistry._relationalizers = original_relationalizers
        RelationalizerRegistry._instances = original_instances


def test_built_in_relationalizers_work():
    """Test that all built-in relationalizers work as expected."""
    
    # Test data with various types
    test_data = {
        'number': 42,
        'text': 'hello',
        'bool_val': True,
        'none_val': None,
        'list_data': [1, 2, 3],
        'set_data': {4, 5, 6},
        'nested_dict': {'inner': 'value'}
    }
    
    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance(test_data)
    
    # Verify we have atoms for all our data
    assert len(data_instance['atoms']) >= 8  # At least one for each element plus the root dict
    
    # Verify we have relations connecting the dict to its values
    relations = data_instance['relations']
    assert len(relations) > 0
    
    # Check that we can generate a diagram
    result = diagram(test_data, method='file', auto_open=False)
    assert result.endswith('.html')






def test_registry_management():
    """Test relationalizer registry management."""
    
    # Save current state
    original_relationalizers = RelationalizerRegistry._relationalizers.copy()
    original_instances = RelationalizerRegistry._instances.copy()
    
    try:
        # Clear and test empty registry
        RelationalizerRegistry.clear()
        assert len(RelationalizerRegistry._relationalizers) == 0
        assert len(RelationalizerRegistry._instances) == 0
        
        # Register a test relationalizer
        @relationalizer(priority=100)
        class TestRelationalizer(RelationalizerBase):
            def can_handle(self, obj: Any) -> bool:
                return isinstance(obj, str) and obj == 'test'
            
            def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
                atom = Atom(id=walker_func._get_id(obj), type="test", label="Test")
                return [atom], []
        
        # Verify registration
        assert len(RelationalizerRegistry._relationalizers) == 1
        assert len(RelationalizerRegistry._instances) == 1
        
        # Test finding relationalizer
        found_relationalizer = RelationalizerRegistry.find_relationalizer('test')
        assert found_relationalizer is not None
        assert isinstance(found_relationalizer, TestRelationalizer)
        
        # Test not finding relationalizer
        not_found_relationalizer = RelationalizerRegistry.find_relationalizer('not_test')
        assert not_found_relationalizer is None
        
    finally:
        # Restore original state
        RelationalizerRegistry._relationalizers = original_relationalizers
        RelationalizerRegistry._instances = original_instances


def test_integration_with_existing_functionality():
    """Test that the relationalizer system integrates well with existing annotations."""
    
    from spytial import annotate_orientation, annotate_group
    
    # Create test data with annotations
    test_data = [1, 2, 3, 4, 5]
    annotate_orientation(test_data, selector='items', directions=['horizontal'])
    annotate_group(test_data, field='elements', groupOn=0, addToGroup=1)
    
    # Test that visualization still works
    result = diagram(test_data, method='file', auto_open=False)
    assert result.endswith('.html')
    
    # Test that builder collects annotations
    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance(test_data)
    decorators = builder.get_collected_decorators()
    
    assert len(decorators['constraints']) >= 2  # At least orientation and group


if __name__ == "__main__":
    print("Testing Relationalizer System (Issue #27)")
    
    # Run tests manually since pytest might not be available
    test_functions = [
        test_built_in_relationalizers_work,
        test_registry_management,
        test_integration_with_existing_functionality
    ]
    
    for test_func in test_functions:
        try:
            test_func()
            print(f"✓ {test_func.__name__}")
        except Exception as e:
            print(f"✗ {test_func.__name__}: {e}")
    
    # Test inheritance requirement separately since it expects an exception
    if test_relationalizer_inheritance_requirement_manual():
        print("✓ test_relationalizer_inheritance_requirement")
    else:
        print("✗ test_relationalizer_inheritance_requirement: Should have raised TypeError")
    
    print("\n🎉 Relationalizer system tests completed!")
    print("\nExample usage:")
    print("  from spytial import RelationalizerBase, relationalizer, Atom, Relation")
    print("  ")
    print("  @relationalizer(priority=100)")
    print("  class MyRelationalizer(RelationalizerBase):")
    print("      def can_handle(self, obj): ...")
    print("      def relationalize(self, obj, walker_func): ...")
