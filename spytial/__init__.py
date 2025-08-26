from .provider_system import (
    # New relationalizer system
    CnDDataInstanceBuilder,
    RelationalizerBase,
    RelationalizerRegistry,
    relationalizer,
    Atom,
    Relation,
)
from .visualizer import diagram
from .evaluator import evaluate
from .annotations import (
    # Class decorators
    orientation,
    cyclic,
    group,
    atomColor,
    size,
    icon,
    edgeColor,
    projection,
    attribute,
    hideField,
    hideAtom,
    inferredEdge,
    # Object annotation functions
    annotate,
    annotate_orientation,
    annotate_cyclic,
    annotate_group,
    annotate_atomColor,
    annotate_size,
    annotate_icon,
    annotate_edgeColor,
    annotate_projection,
    annotate_attribute,
    annotate_hideField,
    annotate_hideAtom,
    annotate_inferredEdge,
    # Utility functions
    collect_decorators,
    serialize_to_yaml_string,
    reset_object_ids,
)
from .structured_input import (
    # Structured input classes
    Hole,
    StructuredTemplate,
    StructuredInputBuilder,
    # Convenience functions
    create_hole,
    create_template,
    start_from_template,
    fill_hole,
    fill_hole_by_description,
    get_current_state,
    get_result,
    list_templates,
    reset,
    # Global builder instance
    default_builder,
)

# Import the structured_input function with a different name to avoid collision
from .structured_evaluator import structured_input

# Main data instance builder
CnDDataInstanceBuilder = CnDDataInstanceBuilder


__all__ = [
    # Core functions
    "diagram",
    "evaluate",
    "structured_input",
    # New relationalizer system
    "CnDDataInstanceBuilder",
    "RelationalizerBase",
    "RelationalizerRegistry",
    "relationalizer",
    # Class decorators
    "orientation",
    "cyclic",
    "group",
    "atomColor",
    "size",
    "icon",
    "edgeColor",
    "projection",
    "attribute",
    "hideField",
    "hideAtom",
    "inferredEdge",
    # Object annotation functions
    "annotate",
    "annotate_orientation",
    "annotate_cyclic",
    "annotate_group",
    "annotate_atomColor",
    "annotate_size",
    "annotate_icon",
    "annotate_edgeColor",
    "annotate_projection",
    "annotate_attribute",
    "annotate_hideField",
    "annotate_hideAtom",
    "annotate_inferredEdge",
    # Utility functions
    "collect_decorators",
    "serialize_to_yaml_string",
    "reset_object_ids",
    # Structured input functionality
    "Hole",
    "StructuredTemplate",
    "StructuredInputBuilder",
    "create_hole",
    "create_template",
    "start_from_template",
    "fill_hole",
    "fill_hole_by_description",
    "get_current_state",
    "get_result",
    "list_templates",
    "reset",
    "default_builder",
]
