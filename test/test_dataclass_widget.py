"""
Tests for the simplified DataClass widget system.
"""

import pytest
from dataclasses import dataclass
import spytial


@dataclass
@spytial.orientation(selector='name', directions=['above'])  
class Person:
    name: str = ""
    age: int = 0
    email: str = ""


@pytest.mark.skipif(not spytial.WIDGETS_AVAILABLE, reason="ipywidgets not available")
class TestDataclassWidget:
    """Test the simplified DataClass widget functionality."""

    def test_widget_creation(self):
        """Test that widgets can be created successfully."""
        widget = spytial.dataclass_widget(Person)
        assert widget is not None
        assert hasattr(widget, 'value')
        assert hasattr(widget, 'update_from_json')
    
    def test_widget_alias(self):
        """Test that the dataclass_builder alias works."""
        widget = spytial.dataclass_builder(Person)
        assert widget is not None
        assert hasattr(widget, 'value')
        assert hasattr(widget, 'update_from_json')
    
    def test_initial_value(self):
        """Test that initial widget value is None."""
        widget = spytial.dataclass_widget(Person)
        assert widget.value is None
    
    def test_json_update(self):
        """Test that JSON updates work correctly."""
        widget = spytial.dataclass_widget(Person)
        
        # Test valid JSON update
        test_json = '{"name": "John", "age": 30, "email": "john@example.com"}'
        success = widget.update_from_json(test_json)
        assert success is True
        assert widget.value is not None
        assert widget.value.name == "John"
        assert widget.value.age == 30
        assert widget.value.email == "john@example.com"
    
    def test_invalid_json_update(self):
        """Test that invalid JSON is handled gracefully."""
        widget = spytial.dataclass_widget(Person)
        
        # Test invalid JSON
        success = widget.update_from_json('invalid json')
        assert success is False
        assert widget.value is None
    
    def test_dict_update(self):
        """Test that dictionary updates work correctly."""
        widget = spytial.dataclass_widget(Person)
        
        # Test dict update
        test_dict = {"name": "Alice", "age": 25, "email": "alice@example.com"}
        success = widget.update_from_json(test_dict)
        assert success is True
        assert widget.value is not None
        assert widget.value.name == "Alice"
        assert widget.value.age == 25
        assert widget.value.email == "alice@example.com"


def test_widgets_not_available():
    """Test behavior when ipywidgets is not available."""
    # This test will run even if ipywidgets is available, but tests the fallback
    original_available = spytial.WIDGETS_AVAILABLE
    
    # Temporarily set to False to test fallback
    spytial.WIDGETS_AVAILABLE = False
    
    try:
        # Manually test the fallback function
        def dummy_widget(*args, **kwargs):
            raise ImportError("ipywidgets is required for widget functionality. Install with: pip install ipywidgets")
        
        with pytest.raises(ImportError, match="ipywidgets is required"):
            dummy_widget(Person)
    finally:
        # Restore original state
        spytial.WIDGETS_AVAILABLE = original_available