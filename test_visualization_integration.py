"""
Test that visualization works with the new @: operator syntax.
This creates a simple structure and generates the visualization data to ensure 
the integration with the CnD core works correctly.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spytial import atomColor, collect_decorators, serialize_to_yaml_string
from spytial.provider_system import CnDDataInstanceBuilder


def test_visualization_integration():
    """Test that the @: operator works with the full visualization pipeline."""
    print("Testing Visualization Integration with @: Operator")
    print("=" * 55)
    
    # Create a class with @: operator in selector
    @atomColor(selector='{ x : TestNode | @:(x.status) = active }', value='green')
    class TestNode:
        def __init__(self, name, status):
            self.name = name
            self.status = status
        
        def __repr__(self):
            return f"TestNode({self.name}, {self.status})"
    
    # Create test data
    root = TestNode("root", "active")
    child1 = TestNode("child1", "inactive")
    child2 = TestNode("child2", "active")
    root.children = [child1, child2]
    
    print("Created test structure:")
    print(f"  {root}")
    print(f"    {child1}")
    print(f"    {child2}")
    print()
    
    # Test annotation collection
    decorators = collect_decorators(root)
    print("Collected decorators:")
    yaml_output = serialize_to_yaml_string(decorators)
    print(yaml_output)
    
    # Test data instance building
    builder = CnDDataInstanceBuilder()
    data_instance = builder.build_instance(root)
    
    print("Generated data instance:")
    print(f"  Atoms: {len(data_instance['atoms'])}")
    print(f"  Relations: {len(data_instance['relations'])}")
    print(f"  Types: {len(data_instance['types'])}")
    print()
    
    # Verify the selector was processed correctly
    selector = decorators['directives'][0]['atomColor']['selector']
    expected = '{ x : TestNode | getLabelForValue(x.status) = active }'
    assert selector == expected, f"Expected {expected}, got {selector}"
    
    print("✓ Selector preprocessing works correctly")
    print("✓ Data instance generation works")
    print("✓ YAML serialization works")
    print()
    print("The visualization pipeline is ready for the @: operator!")


if __name__ == "__main__":
    test_visualization_integration()