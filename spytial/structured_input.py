"""
sPyTial Structured Input Module

This module provides functionality for creating and manipulating structured data
interactively, supporting the construction of partial data structures with "holes"
and live visualization updates.
"""

import json
import uuid
from typing import Any, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field


class Hole:
    """Represents a placeholder or 'hole' in a data structure that can be filled later."""

    def __init__(
        self, type_hint: Optional[str] = None, description: Optional[str] = None
    ):
        self.id = str(uuid.uuid4())[:8]  # Short unique ID
        self.type_hint = type_hint
        self.description = description or f"hole_{self.id}"

    def __repr__(self):
        if self.type_hint:
            return f"<Hole({self.type_hint}): {self.description}>"
        return f"<Hole: {self.description}>"

    def __str__(self):
        return f"?{self.description}"


@dataclass
class StructuredTemplate:
    """A template for creating structured data with placeholders."""

    name: str
    template: Any
    description: str = ""
    holes: List[Hole] = field(default_factory=list)

    def fill_hole(self, hole_id: str, value: Any) -> "StructuredTemplate":
        """Create a new template with the specified hole filled."""
        new_template = self._deep_copy_template(self.template)
        new_holes = [h for h in self.holes if h.id != hole_id]

        self._fill_hole_recursive(new_template, hole_id, value)

        return StructuredTemplate(
            name=self.name,
            template=new_template,
            description=self.description,
            holes=new_holes,
        )

    def _deep_copy_template(self, obj):
        """Deep copy the template structure."""
        if isinstance(obj, Hole):
            return obj
        elif isinstance(obj, dict):
            return {k: self._deep_copy_template(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy_template(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._deep_copy_template(item) for item in obj)
        else:
            return obj

    def _fill_hole_recursive(self, obj, hole_id: str, value: Any):
        """Recursively find and fill holes in the template."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, Hole) and v.id == hole_id:
                    obj[k] = value
                else:
                    self._fill_hole_recursive(v, hole_id, value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, Hole) and item.id == hole_id:
                    obj[i] = value
                else:
                    self._fill_hole_recursive(item, hole_id, value)

    def get_holes(self) -> List[Hole]:
        """Get all unfilled holes in the template."""
        return self.holes.copy()

    def is_complete(self) -> bool:
        """Check if all holes have been filled."""
        return len(self.holes) == 0

    def to_dict(self) -> Dict:
        """Convert template to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "template": self._serialize_template(self.template),
            "holes": [
                {"id": h.id, "type_hint": h.type_hint, "description": h.description}
                for h in self.holes
            ],
            "is_complete": self.is_complete(),
        }

    def _serialize_template(self, obj):
        """Serialize template for JSON representation."""
        if isinstance(obj, Hole):
            return {"__hole__": True, "id": obj.id, "description": obj.description}
        elif isinstance(obj, dict):
            return {k: self._serialize_template(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_template(item) for item in obj]
        elif isinstance(obj, tuple):
            return {
                "__tuple__": True,
                "items": [self._serialize_template(item) for item in obj],
            }
        else:
            return obj


class StructuredInputBuilder:
    """Builder for creating structured data with interactive input capabilities."""

    def __init__(self):
        self.templates = {}
        self.current_template: Optional[StructuredTemplate] = None

        # Register common templates
        self._register_builtin_templates()

    def _register_builtin_templates(self):
        """Register common data structure templates."""

        # Simple dictionary template
        dict_hole = Hole("any", "value")
        self.register_template(
            "simple_dict",
            {"key1": dict_hole, "key2": "preset_value"},
            "Simple dictionary with one hole",
            [dict_hole],
        )

        # List template
        list_hole1 = Hole("any", "first_item")
        list_hole2 = Hole("any", "second_item")
        self.register_template(
            "simple_list",
            [list_hole1, "preset_item", list_hole2],
            "Simple list with holes",
            [list_hole1, list_hole2],
        )

        # Tree node template
        value_hole = Hole("any", "node_value")
        left_hole = Hole("TreeNode|None", "left_child")
        right_hole = Hole("TreeNode|None", "right_child")
        self.register_template(
            "tree_node",
            {"value": value_hole, "left": left_hole, "right": right_hole},
            "Binary tree node template",
            [value_hole, left_hole, right_hole],
        )

        # Graph node template
        node_value_hole = Hole("any", "node_value")
        neighbors_hole = Hole("list", "neighbors")
        self.register_template(
            "graph_node",
            {"id": node_value_hole, "neighbors": neighbors_hole, "visited": False},
            "Graph node with neighbors",
            [node_value_hole, neighbors_hole],
        )

    def register_template(
        self, name: str, template: Any, description: str = "", holes: List[Hole] = None
    ):
        """Register a new template."""
        if holes is None:
            holes = self._extract_holes(template)

        self.templates[name] = StructuredTemplate(
            name=name, template=template, description=description, holes=holes
        )

    def _extract_holes(self, obj) -> List[Hole]:
        """Extract all holes from a template structure."""
        holes = []

        def extract_recursive(item):
            if isinstance(item, Hole):
                holes.append(item)
            elif isinstance(item, dict):
                for v in item.values():
                    extract_recursive(v)
            elif isinstance(item, (list, tuple)):
                for item in item:
                    extract_recursive(item)

        extract_recursive(obj)
        return holes

    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self.templates.keys())

    def get_template(self, name: str) -> Optional[StructuredTemplate]:
        """Get a template by name."""
        return self.templates.get(name)

    def start_from_template(self, template_name: str) -> StructuredTemplate:
        """Start building from a template."""
        template = self.get_template(template_name)
        if template is None:
            raise ValueError(f"Template '{template_name}' not found")

        self.current_template = template
        return template

    def fill_hole(self, hole_id: str, value: Any) -> StructuredTemplate:
        """Fill a hole in the current template."""
        if self.current_template is None:
            raise ValueError("No current template. Call start_from_template() first.")

        self.current_template = self.current_template.fill_hole(hole_id, value)
        return self.current_template

    def fill_hole_by_description(
        self, description: str, value: Any
    ) -> StructuredTemplate:
        """Fill a hole by its description."""
        if self.current_template is None:
            raise ValueError("No current template. Call start_from_template() first.")

        holes = self.current_template.get_holes()
        matching_holes = [h for h in holes if h.description == description]

        if not matching_holes:
            raise ValueError(f"No hole found with description '{description}'")
        if len(matching_holes) > 1:
            raise ValueError(f"Multiple holes found with description '{description}'")

        return self.fill_hole(matching_holes[0].id, value)

    def get_current_state(self) -> Optional[Dict]:
        """Get the current template state."""
        if self.current_template is None:
            return None
        return self.current_template.to_dict()

    def get_result(self) -> Any:
        """Get the final result if template is complete."""
        if self.current_template is None:
            raise ValueError("No current template")
        if not self.current_template.is_complete():
            remaining_holes = [h.description for h in self.current_template.get_holes()]
            raise ValueError(f"Template incomplete. Remaining holes: {remaining_holes}")

        return self.current_template.template

    def reset(self):
        """Reset the current template."""
        self.current_template = None


def create_hole(
    type_hint: Optional[str] = None, description: Optional[str] = None
) -> Hole:
    """Convenience function for creating holes."""
    return Hole(type_hint, description)


def create_template(
    name: str, structure: Any, description: str = ""
) -> StructuredTemplate:
    """Convenience function for creating templates."""
    holes = StructuredInputBuilder()._extract_holes(structure)
    return StructuredTemplate(name, structure, description, holes)


# Global builder instance for convenience
default_builder = StructuredInputBuilder()


def start_from_template(template_name: str) -> StructuredTemplate:
    """Start building from a template using the default builder."""
    return default_builder.start_from_template(template_name)


def fill_hole(hole_id: str, value: Any) -> StructuredTemplate:
    """Fill a hole using the default builder."""
    return default_builder.fill_hole(hole_id, value)


def fill_hole_by_description(description: str, value: Any) -> StructuredTemplate:
    """Fill a hole by description using the default builder."""
    return default_builder.fill_hole_by_description(description, value)


def get_current_state() -> Optional[Dict]:
    """Get current state using the default builder."""
    return default_builder.get_current_state()


def get_result() -> Any:
    """Get result using the default builder."""
    return default_builder.get_result()


def list_templates() -> List[str]:
    """List available templates using the default builder."""
    return default_builder.list_templates()


def reset():
    """Reset the default builder."""
    default_builder.reset()
