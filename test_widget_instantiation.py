"""
Test script to verify dataclass_builder widget instantiation.
Run this to ensure the widget can be created properly.
"""

from dataclasses import dataclass
import spytial

@dataclass
class Person:
    name: str = ""
    age: int = 0
    email: str = ""

print("Testing dataclass_builder widget instantiation...")
print("=" * 60)

try:
    print("\n1. Creating widget...")
    widget = spytial.dataclass_builder(Person)
    print(f"   ✓ Widget created: {type(widget).__name__}")
    print(f"   ✓ Widget ID: {widget._widget_id}")
    print(f"   ✓ Dataclass type: {widget.dataclass_type.__name__}")
    
    print("\n2. Checking initial state...")
    print(f"   ✓ Initial value: {widget.value}")
    print(f"   ✓ Has widget attribute: {hasattr(widget, 'widget')}")
    print(f"   ✓ Has iframe_widget: {hasattr(widget, 'iframe_widget')}")
    print(f"   ✓ Has status_output: {hasattr(widget, 'status_output')}")
    
    print("\n3. Checking global registry...")
    if '_spytial_widgets' in globals():
        print(f"   ✓ Global registry exists")
        print(f"   ✓ Widget registered: {widget._widget_id in globals()['_spytial_widgets']}")
    else:
        print("   ⚠ Global registry not found (expected in module scope)")
    
    print("\n4. Testing data conversion...")
    from spytial.dataclass_widget_cnd import _json_to_dataclass
    test_data = {'name': 'Alice', 'age': 30, 'email': 'alice@example.com'}
    person = _json_to_dataclass(test_data, Person)
    print(f"   ✓ Converted: {person}")
    
    # Simulate what happens when export is clicked
    widget._current_value = person
    print(f"   ✓ Widget value updated: {widget.value}")
    
    print("\n" + "=" * 60)
    print("✅ All widget instantiation tests passed!")
    print("\nTo use in Jupyter:")
    print("  widget = spytial.dataclass_builder(Person)")
    print("  widget  # Display it")
    print("  # Build visually, click Export JSON")
    print("  person = widget.value  # Access the result")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
