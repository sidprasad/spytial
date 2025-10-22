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
from .dataclass_builder import dataclass_builder
from .annotations import (
    # Class decorators
    orientation,
    cyclic,
    align,
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
    flag,
    # Object annotation functions
    annotate,
    annotate_orientation,
    annotate_cyclic,
    annotate_align,
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
    annotate_flag,
    # Inheritance control decorators
    dont_inherit_constraints,
    dont_inherit_directives,
    dont_inherit_annotations,
    # Utility functions
    collect_decorators,
    serialize_to_yaml_string,
    reset_object_ids,
    apply_if,
)

# Main data instance builder
CnDDataInstanceBuilder = CnDDataInstanceBuilder


__all__ = [
    # Core functions
    "diagram",
    "evaluate",
    "dataclass_builder",
    # New relationalizer system
    "CnDDataInstanceBuilder",
    "RelationalizerBase",
    "RelationalizerRegistry",
    "relationalizer",
    # Class decorators
    "orientation",
    "cyclic",
    "align",
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
    "flag",
    # Object annotation functions
    "annotate",
    "annotate_orientation",
    "annotate_cyclic",
    "annotate_align",
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
    "annotate_flag",
    # Inheritance control decorators
    "dont_inherit_constraints",
    "dont_inherit_directives",
    "dont_inherit_annotations",
    # Utility functions
    "collect_decorators",
    "serialize_to_yaml_string",
    "reset_object_ids",
    "apply_if",
]
