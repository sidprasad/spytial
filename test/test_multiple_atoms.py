#!/usr/bin/env python3
"""
Test file demonstrating the new multiple atoms functionality.

This test shows how relationalizers can now return multiple atoms
for a single object, enabling more complex visualizations.
"""

import pytest
from spytial import RelationalizerBase, relationalizer, Atom, Relation, CnDDataInstanceBuilder
from spytial.provider_system import RelationalizerRegistry
from typing import Any, List, Tuple


def test_relationalizer_returns_multiple_atoms():
    """Test that a relationalizer can return multiple atoms for a single object."""
    
    # Save current state
    original_relationalizers = RelationalizerRegistry._relationalizers.copy()
    original_instances = RelationalizerRegistry._instances.copy()
    
    try:
        @relationalizer(priority=200)  # High priority to ensure it's used
        class MultiAtomRelationalizer(RelationalizerBase):
            """Relationalizer that creates multiple atoms for a complex number."""
            
            def can_handle(self, obj: Any) -> bool:
                return isinstance(obj, complex)
            
            def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
                base_id = walker_func._get_id(obj)
                
                # Create three atoms: one for the complex number itself, one for real part, one for imaginary part
                complex_atom = Atom(
                    id=f"{base_id}",
                    type="complex", 
                    label=f"{obj}"
                )
                
                real_atom = Atom(
                    id=f"{base_id}_real",
                    type="real_part",
                    label=f"Real: {obj.real}"
                )
                
                imag_atom = Atom(
                    id=f"{base_id}_imag", 
                    type="imag_part",
                    label=f"Imag: {obj.imag}"
                )
                
                # Create relations connecting the main atom to its components
                relations = [
                    Relation.binary("real_part", base_id, f"{base_id}_real"),
                    Relation.binary("imag_part", base_id, f"{base_id}_imag")
                ]
                
                return [complex_atom, real_atom, imag_atom], relations
        
        # Test with a complex number
        test_complex = 3 + 4j
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(test_complex)
        
        # Should have 3 atoms for the complex number
        complex_atoms = [atom for atom in data_instance['atoms'] 
                        if any(t in atom.get('type', '') for t in ['complex', 'real_part', 'imag_part'])]
        assert len(complex_atoms) == 3
        
        # Check that we have all three types
        atom_types = [atom['type'] for atom in complex_atoms]
        assert 'complex' in atom_types
        assert 'real_part' in atom_types
        assert 'imag_part' in atom_types
        
        # Check that we have the expected relations
        relations = data_instance['relations']
        relation_names = []
        for rel in relations:
            relation_names.extend([tuple_info for tuple_info in rel.get('tuples', [])])
        
        # Should have at least the real_part and imag_part relations
        assert any('real_part' in str(rel) for rel in relations)
        assert any('imag_part' in str(rel) for rel in relations)
        
        print("✓ Multi-atom relationalizer test passed!")
        
    finally:
        # Restore original state
        RelationalizerRegistry._relationalizers = original_relationalizers
        RelationalizerRegistry._instances = original_instances


def test_relationalizer_returns_composite_object_as_multiple_atoms():
    """Test returning multiple atoms for a composite data structure."""
    
    # Save current state  
    original_relationalizers = RelationalizerRegistry._relationalizers.copy()
    original_instances = RelationalizerRegistry._instances.copy()
    
    try:
        class Range:
            """Simple range class for testing."""
            def __init__(self, start, end):
                self.start = start
                self.end = end
        
        @relationalizer(priority=201)
        class RangeRelationalizer(RelationalizerBase):
            """Relationalizer that creates separate atoms for range boundaries."""
            
            def can_handle(self, obj: Any) -> bool:
                return isinstance(obj, Range)
            
            def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
                base_id = walker_func._get_id(obj)
                
                # Create atoms for range, start boundary, and end boundary
                range_atom = Atom(
                    id=f"{base_id}",
                    type="range",
                    label=f"Range [{obj.start}, {obj.end}]"
                )
                
                start_atom = Atom(
                    id=f"{base_id}_start",
                    type="boundary",
                    label=f"Start: {obj.start}"
                )
                
                end_atom = Atom(
                    id=f"{base_id}_end",
                    type="boundary", 
                    label=f"End: {obj.end}"
                )
                
                # Relations connecting range to its boundaries
                relations = [
                    Relation.binary("start_boundary", base_id, f"{base_id}_start"),
                    Relation.binary("end_boundary", base_id, f"{base_id}_end")
                ]
                
                return [range_atom, start_atom, end_atom], relations
        
        # Test with a range object
        test_range = Range(10, 20)
        builder = CnDDataInstanceBuilder()
        data_instance = builder.build_instance(test_range)
        
        # Should have atoms for range and its boundaries
        range_atoms = [atom for atom in data_instance['atoms'] 
                      if atom.get('type') in ['range', 'boundary']]
        assert len(range_atoms) == 3  # 1 range + 2 boundaries
        
        # Verify atom types
        atom_types = [atom['type'] for atom in range_atoms]
        assert atom_types.count('range') == 1
        assert atom_types.count('boundary') == 2
        
        print("✓ Composite object multi-atom test passed!")
        
    finally:
        # Restore original state
        RelationalizerRegistry._relationalizers = original_relationalizers  
        RelationalizerRegistry._instances = original_instances


def test_backward_compatibility_single_atom():
    """Test that existing single-atom relationalizers still work correctly."""
    
    # Test that primitive types still work as expected
    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance("simple string")
    
    # Should have exactly one atom for the string
    string_atoms = [atom for atom in data_instance['atoms'] 
                   if atom.get('type') == 'str']
    assert len(string_atoms) == 1
    assert string_atoms[0]['label'] == 'simple string'
    
    print("✓ Backward compatibility test passed!")


if __name__ == "__main__":
    print("Testing Multiple Atoms Functionality")
    
    test_functions = [
        test_relationalizer_returns_multiple_atoms,
        test_relationalizer_returns_composite_object_as_multiple_atoms,
        test_backward_compatibility_single_atom
    ]
    
    for test_func in test_functions:
        try:
            test_func()
            print(f"✓ {test_func.__name__}")
        except Exception as e:
            print(f"✗ {test_func.__name__}: {e}")
    
    print("\n🎉 Multiple atoms functionality tests completed!")