"""
Tests for structured input functionality.
"""

import pytest
import sys
from pathlib import Path

# Add the parent directory to the Python path for imports
sys.path.append(str(Path(__file__).parent.parent))

from spytial.structured_input import (
    Hole,
    StructuredTemplate,
    StructuredInputBuilder,
    create_hole,
    create_template,
    start_from_template,
    fill_hole_by_description,
    get_current_state,
    get_result,
    list_templates,
    reset,
    default_builder
)


class TestHole:
    """Test the Hole class functionality."""
    
    def test_hole_creation(self):
        """Test basic hole creation."""
        hole = Hole("str", "test_hole")
        assert hole.type_hint == "str"
        assert hole.description == "test_hole"
        assert hole.id is not None
        assert len(hole.id) == 8  # Short unique ID

    def test_hole_representation(self):
        """Test hole string representations."""
        hole = Hole("int", "age")
        assert "Hole(int): age" in repr(hole)
        assert "?age" in str(hole)

    def test_hole_without_type_hint(self):
        """Test hole creation without type hint."""
        hole = Hole(description="generic_hole")
        assert hole.type_hint is None
        assert hole.description == "generic_hole"

    def test_hole_with_auto_description(self):
        """Test hole with auto-generated description."""
        hole = Hole("str")
        assert hole.description.startswith("hole_")
        assert hole.id in hole.description


class TestStructuredTemplate:
    """Test the StructuredTemplate class functionality."""
    
    def test_template_creation(self):
        """Test basic template creation."""
        hole = create_hole("str", "name")
        template_data = {"name": hole, "age": 25}
        
        template = StructuredTemplate(
            name="person",
            template=template_data,
            description="Person template",
            holes=[hole]
        )
        
        assert template.name == "person"
        assert template.description == "Person template"
        assert len(template.holes) == 1
        assert not template.is_complete()

    def test_fill_hole(self):
        """Test filling holes in templates."""
        hole = create_hole("str", "name")
        template_data = {"name": hole, "age": 25}
        
        template = StructuredTemplate(
            name="person",
            template=template_data,
            holes=[hole]
        )
        
        filled_template = template.fill_hole(hole.id, "John")
        assert filled_template.template["name"] == "John"
        assert filled_template.template["age"] == 25
        assert len(filled_template.holes) == 0
        assert filled_template.is_complete()

    def test_fill_nested_hole(self):
        """Test filling holes in nested structures."""
        address_hole = create_hole("str", "city")
        template_data = {
            "name": "John",
            "address": {
                "street": "123 Main St",
                "city": address_hole
            }
        }
        
        template = StructuredTemplate(
            name="person_with_address",
            template=template_data,
            holes=[address_hole]
        )
        
        filled_template = template.fill_hole(address_hole.id, "Boston")
        assert filled_template.template["address"]["city"] == "Boston"
        assert filled_template.is_complete()

    def test_fill_hole_in_list(self):
        """Test filling holes in lists."""
        item_hole = create_hole("int", "item")
        template_data = ["first", item_hole, "third"]
        
        template = StructuredTemplate(
            name="list_template",
            template=template_data,
            holes=[item_hole]
        )
        
        filled_template = template.fill_hole(item_hole.id, 42)
        assert filled_template.template[1] == 42

    def test_to_dict(self):
        """Test template serialization to dictionary."""
        hole = create_hole("str", "name")
        template = StructuredTemplate(
            name="test",
            template={"name": hole},
            holes=[hole]
        )
        
        dict_repr = template.to_dict()
        assert dict_repr["name"] == "test"
        assert dict_repr["is_complete"] is False
        assert len(dict_repr["holes"]) == 1


class TestStructuredInputBuilder:
    """Test the StructuredInputBuilder class functionality."""
    
    def setup_method(self):
        """Set up each test with a fresh builder."""
        self.builder = StructuredInputBuilder()

    def test_builder_initialization(self):
        """Test builder initialization and builtin templates."""
        templates = self.builder.list_templates()
        assert "simple_dict" in templates
        assert "simple_list" in templates
        assert "tree_node" in templates

    def test_custom_template_registration(self):
        """Test registering custom templates."""
        hole = create_hole("str", "value")
        self.builder.register_template(
            "custom",
            {"data": hole},
            "Custom template",
            [hole]
        )
        
        templates = self.builder.list_templates()
        assert "custom" in templates
        
        template = self.builder.get_template("custom")
        assert template.name == "custom"
        assert template.description == "Custom template"

    def test_template_workflow(self):
        """Test complete workflow with templates."""
        # Start from template
        template = self.builder.start_from_template("simple_dict")
        assert template.name == "simple_dict"
        assert not template.is_complete()
        
        # Fill hole
        updated_template = self.builder.fill_hole_by_description("value", "test_value")
        assert updated_template.is_complete()
        
        # Get result
        result = self.builder.get_result()
        assert result["key1"] == "test_value"
        assert result["key2"] == "preset_value"

    def test_complex_template_workflow(self):
        """Test workflow with tree template."""
        # Start tree template
        self.builder.start_from_template("tree_node")
        
        # Fill holes step by step
        self.builder.fill_hole_by_description("node_value", "root")
        self.builder.fill_hole_by_description("left_child", None)
        self.builder.fill_hole_by_description("right_child", {"value": "right", "left": None, "right": None})
        
        result = self.builder.get_result()
        assert result["value"] == "root"
        assert result["left"] is None
        assert result["right"]["value"] == "right"

    def test_reset_functionality(self):
        """Test resetting the builder state."""
        self.builder.start_from_template("simple_dict")
        assert self.builder.current_template is not None
        
        self.builder.reset()
        assert self.builder.current_template is None

    def test_error_handling(self):
        """Test error handling for invalid operations."""
        # Try to fill hole without starting template
        with pytest.raises(ValueError, match="No current template"):
            self.builder.fill_hole("invalid_id", "value")
        
        # Try to get result without template
        with pytest.raises(ValueError, match="No current template"):
            self.builder.get_result()
        
        # Start template and try to get result before completion
        self.builder.start_from_template("simple_dict")
        with pytest.raises(ValueError, match="Template incomplete"):
            self.builder.get_result()


class TestConvenienceFunctions:
    """Test the module-level convenience functions."""
    
    def setup_method(self):
        """Reset global state before each test."""
        reset()

    def test_global_workflow(self):
        """Test the global convenience functions."""
        # List templates
        templates = list_templates()
        assert "simple_dict" in templates
        
        # Start from template
        template = start_from_template("simple_dict")
        assert template.name == "simple_dict"
        
        # Check state
        state = get_current_state()
        assert state is not None
        assert state["name"] == "simple_dict"
        
        # Fill hole
        updated_template = fill_hole_by_description("value", "global_test")
        assert updated_template.is_complete()
        
        # Get result
        result = get_result()
        assert result["key1"] == "global_test"

    def test_create_hole_function(self):
        """Test the create_hole convenience function."""
        hole = create_hole("int", "test_int")
        assert isinstance(hole, Hole)
        assert hole.type_hint == "int"
        assert hole.description == "test_int"

    def test_create_template_function(self):
        """Test the create_template convenience function."""
        hole = create_hole("str", "name")
        template = create_template(
            "test_template",
            {"name": hole, "type": "person"},
            "Test person template"
        )
        
        assert isinstance(template, StructuredTemplate)
        assert template.name == "test_template"
        assert len(template.holes) == 1

    def test_error_propagation(self):
        """Test that errors are properly propagated from global functions."""
        # Try operations without starting template
        with pytest.raises(ValueError):
            get_result()
        
        with pytest.raises(ValueError):
            fill_hole_by_description("nonexistent", "value")


class TestIntegration:
    """Integration tests for structured input functionality."""
    
    def test_round_trip_serialization(self):
        """Test that structures can be created and properly serialized."""
        reset()
        
        # Create a complex nested structure
        start_from_template("tree_node")
        fill_hole_by_description("node_value", "root")
        
        left_subtree = {"value": "left", "left": None, "right": None}
        right_subtree = {"value": "right", "left": None, "right": None}
        
        fill_hole_by_description("left_child", left_subtree)
        fill_hole_by_description("right_child", right_subtree)
        
        result = get_result()
        
        # Verify structure
        assert result["value"] == "root"
        assert result["left"]["value"] == "left"
        assert result["right"]["value"] == "right"
        
        # Should be serializable
        import json
        json_str = json.dumps(result)
        reconstructed = json.loads(json_str)
        assert reconstructed == result

    def test_multiple_builders(self):
        """Test that multiple builders can work independently."""
        builder1 = StructuredInputBuilder()
        builder2 = StructuredInputBuilder()
        
        # Start different templates in each builder
        template1 = builder1.start_from_template("simple_dict")
        template2 = builder2.start_from_template("simple_list")
        
        # Fill holes differently
        builder1.fill_hole_by_description("value", "dict_value")
        builder2.fill_hole_by_description("first_item", "list_item1")
        builder2.fill_hole_by_description("second_item", "list_item2")
        
        # Get different results
        result1 = builder1.get_result()
        result2 = builder2.get_result()
        
        assert result1["key1"] == "dict_value"
        assert result2[0] == "list_item1"
        assert result2[2] == "list_item2"

    def test_template_with_complex_holes(self):
        """Test templates with complex nested hole structures."""
        reset()
        
        # Create a custom template with multiple nested holes
        builder = StructuredInputBuilder()
        
        value_hole = create_hole("any", "node_value")
        children_hole = create_hole("list", "children")
        
        builder.register_template(
            "n_ary_tree",
            {
                "value": value_hole,
                "children": children_hole,
                "metadata": {
                    "depth": 0,
                    "created_at": "2024-01-01"
                }
            },
            "N-ary tree node",
            [value_hole, children_hole]
        )
        
        # Use the template
        builder.start_from_template("n_ary_tree")
        builder.fill_hole_by_description("node_value", "root")
        builder.fill_hole_by_description("children", [
            {"value": "child1", "children": [], "metadata": {"depth": 1, "created_at": "2024-01-01"}},
            {"value": "child2", "children": [], "metadata": {"depth": 1, "created_at": "2024-01-01"}}
        ])
        
        result = builder.get_result()
        assert result["value"] == "root"
        assert len(result["children"]) == 2
        assert result["children"][0]["value"] == "child1"


if __name__ == "__main__":
    pytest.main([__file__])