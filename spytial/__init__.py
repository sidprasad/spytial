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

# Import widget functionality with graceful fallback
try:
    from .dataclass_widget_cnd import dataclass_builder
    WIDGETS_AVAILABLE = True
except ImportError:
    WIDGETS_AVAILABLE = False
    # Create dummy function when widgets aren't available
    def dataclass_builder(*args, **kwargs):
        raise ImportError(
            "ipywidgets is required for widget functionality. "
            "Install with: pip install ipywidgets"
        )
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
    # Widget functionality
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
    # Utility functions
    "collect_decorators",
    "serialize_to_yaml_string",
    "reset_object_ids",
    "apply_if",
]
