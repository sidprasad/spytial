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
from .utils import AnnotatedType
from .annotations import (
    # Class decorators (for decorating classes)
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
    # Type alias annotation classes (for use with typing.Annotated)
    SpytialAnnotation,
    Orientation,
    Cyclic,
    Align,
    Group,
    AtomColor,
    Size,
    Icon,
    EdgeColor,
    HideField,
    HideAtom,
    Projection,
    Attribute,
    InferredEdge,
    Flag,
    extract_spytial_annotations,
    get_base_type,
    # Legacy type alias functions (prefer using typing.Annotated instead)
    annotate_type_alias,
    get_type_alias_annotations,
    clear_type_alias_annotations,
    list_type_alias_annotations,
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
    # Type alias annotation classes (for use with typing.Annotated)
    "SpytialAnnotation",
    "Orientation",
    "Cyclic",
    "Align",
    "Group",
    "AtomColor",
    "Size",
    "Icon",
    "EdgeColor",
    "HideField",
    "HideAtom",
    "Projection",
    "Attribute",
    "InferredEdge",
    "Flag",
    "extract_spytial_annotations",
    "get_base_type",
    # AnnotatedType for reusable type aliases with spytial annotations
    "AnnotatedType",
    # Legacy type alias functions
    "annotate_type_alias",
    "get_type_alias_annotations",
    "clear_type_alias_annotations",
    "list_type_alias_annotations",
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
