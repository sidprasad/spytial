from .provider_system import CnDDataInstanceBuilder, DataInstanceProvider, data_provider
from .visualizer import diagram, quick_diagram
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
    collect_decorators, serialize_to_yaml_string
)

# Aliases for the new branding
SpyTialDataInstanceBuilder = CnDDataInstanceBuilder
SpyTialSerializer = CnDDataInstanceBuilder

# Backwards compatibility aliases
CnDSerializer = CnDDataInstanceBuilder

__all__ = [
    # Core functions
    'diagram', 'quick_diagram', 
    # Provider system
    'CnDDataInstanceBuilder', 'SpyTialDataInstanceBuilder', 'DataInstanceProvider', 
    'data_provider', 'SpyTialSerializer', 'CnDSerializer',
    # Class decorators
    'orientation', 'cyclic', 'group', 'atomColor', 'size', 'icon', 'edgeColor', 
    'projection', 'attribute', 'hideField', 'hideAtom', 'inferredEdge',
    # Object annotation functions
    'annotate', 'annotate_orientation', 'annotate_cyclic', 'annotate_group',
    'annotate_atomColor', 'annotate_size', 'annotate_icon', 'annotate_edgeColor',
    'annotate_projection', 'annotate_attribute', 'annotate_hideField', 
    'annotate_hideAtom', 'annotate_inferredEdge',
    # Utility functions
    'collect_decorators', 'serialize_to_yaml_string'
]

