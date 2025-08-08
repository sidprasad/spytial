from .provider_system import (
    # New relationalizer system
    CnDDataInstanceBuilder, RelationalizerBase, relationalizer, Atom, Relation,
    set_object_relationalizer, object_relationalizer, get_object_relationalizer,
    # Backward compatibility aliases
    DataInstanceProvider, data_provider,
    set_object_provider, object_provider, get_object_provider
)
from .visualizer import diagram
from .evaluator import evaluate
from .annotations import (
    # Class decorators
    orientation, cyclic, group, atomColor, size, icon, edgeColor, 
    projection, attribute, hideField, hideAtom, inferredEdge,
    # Object annotation functions
    annotate, annotate_orientation, annotate_cyclic, annotate_group,
    annotate_atomColor, annotate_size, annotate_icon, annotate_edgeColor,
    annotate_projection, annotate_attribute, annotate_hideField, 
    annotate_hideAtom, annotate_inferredEdge,
    # Utility functions
    collect_decorators, serialize_to_yaml_string, reset_object_ids
)

# Aliases for the new branding
SpyTialDataInstanceBuilder = CnDDataInstanceBuilder
SpyTialSerializer = CnDDataInstanceBuilder


__all__ = [
    # Core functions
    'diagram', 'evaluate',
    # New relationalizer system
    'CnDDataInstanceBuilder', 'SpyTialDataInstanceBuilder', 'RelationalizerBase', 
    'relationalizer', 'SpyTialSerializer', 'Atom', 'Relation',
    'set_object_relationalizer', 'object_relationalizer', 'get_object_relationalizer',
    # Backward compatibility aliases
    'DataInstanceProvider', 'data_provider',
    'set_object_provider', 'object_provider', 'get_object_provider',
    # Class decorators
    'orientation', 'cyclic', 'group', 'atomColor', 'size', 'icon', 'edgeColor', 
    'projection', 'attribute', 'hideField', 'hideAtom', 'inferredEdge',
    # Object annotation functions
    'annotate', 'annotate_orientation', 'annotate_cyclic', 'annotate_group',
    'annotate_atomColor', 'annotate_size', 'annotate_icon', 'annotate_edgeColor',
    'annotate_projection', 'annotate_attribute', 'annotate_hideField', 
    'annotate_hideAtom', 'annotate_inferredEdge',
    # Utility functions
    'collect_decorators', 'serialize_to_yaml_string', 'reset_object_ids'
]

