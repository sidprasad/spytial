#
# sPyTial Annotation System
#
# Users should be able to annotate their classes with spatial constraints and directives.
# @orientation(selector='left', directions=['left', 'below'])
# @cyclic(selector='left', direction='clockwise')
# @group(field='fruit', groupOn=0, addToGroup=1)
# @cnd('group', selector='{b : Basket, a : Fruit | (a in b.fruit) and a.status = Rotten }', name='rottenFruit')
# We want to build this into an object, that is then serialized into YAML, and passed to the visualizer.
#
# e.g.
#constraints:
#   - cyclic:
#       selector: left
#       direction: clockwise
#   - orientation:
#       selector: left
#       directions:
#         - left
#         - below
#  - group:
#       field: fruit
#       groupOn: 0
#       addToGroup: 1
#   - group:
#       selector: '{b : Basket, a : Fruit | (a in b.fruit) and a.status = Rotten }'
#       name: rottenFruit

### AND directives (which are also similar)


import yaml

# Registry to store constraints and directives
# This is now class-level, not global
CONSTRAINT_TYPES = {
    "cyclic": ["selector", "direction"],
    "orientation": ["selector", "directions"],
    "group": ["field", "groupOn", "addToGroup"]
}

DIRECTIVE_TYPES = {
    "atomColor": ["selector", "value"],
    "size": ["selector", "height", "width"],
    "icon": ["selector", "path", "showLabels"],
    "edgeColor": ["field", "color"],
    "projection": ["sig"],
    "attribute": ["field"],
    "hideField": ["field"],
    "hideAtom": ["selector"],
    "inferredEdge": ["name", "selector"]
}

# Object-level annotation storage attribute name
OBJECT_ANNOTATIONS_ATTR = "__spytial_object_annotations__"

# Global registry for objects that can't store annotations directly
_OBJECT_ANNOTATION_REGISTRY = {}

def validate_fields(type_, kwargs, valid_fields):
    """
    Validate that the required fields for a given type are present in kwargs.
    :param type_: The type of constraint or directive.
    :param kwargs: The provided fields for the decorator.
    :param valid_fields: The list of required fields for the type.
    :raises ValueError: If a required field is missing.
    """
    missing_fields = [field for field in valid_fields if field not in kwargs]
    if missing_fields:
        raise ValueError(f"Missing required fields for '{type_}': {', '.join(missing_fields)}")

def _create_decorator(constraint_type):
    """
    Create a decorator function for a specific constraint or directive type.
    :param constraint_type: The type of constraint or directive (e.g., 'cyclic', 'orientation').
    :return: A decorator function.
    """
    def decorator(**kwargs):
        def class_decorator(cls):
            if not hasattr(cls, "__spytial_registry__"):
                cls.__spytial_registry__ = {
                    "constraints": [],
                    "directives": []
                }
            
            # Determine if it's a constraint or directive
            if constraint_type in CONSTRAINT_TYPES:
                # Validate fields for constraints
                validate_fields(constraint_type, kwargs, CONSTRAINT_TYPES[constraint_type])
                entry = {constraint_type: kwargs}
                cls.__spytial_registry__["constraints"].append(entry)
            elif constraint_type in DIRECTIVE_TYPES:
                # Validate fields for directives
                validate_fields(constraint_type, kwargs, DIRECTIVE_TYPES[constraint_type])
                entry = {constraint_type: kwargs}
                cls.__spytial_registry__["directives"].append(entry)
            else:
                raise ValueError(f"Unknown type '{constraint_type}' for sPyTial decorator.")
            
            return cls
        return class_decorator
    return decorator

# Create individual decorator functions for each constraint and directive type
orientation = _create_decorator('orientation')
cyclic = _create_decorator('cyclic')
group = _create_decorator('group')
atomColor = _create_decorator('atomColor')
size = _create_decorator('size')
icon = _create_decorator('icon')
edgeColor = _create_decorator('edgeColor')
projection = _create_decorator('projection')
attribute = _create_decorator('attribute')
hideField = _create_decorator('hideField')
hideAtom = _create_decorator('hideAtom')
inferredEdge = _create_decorator('inferredEdge')

def _ensure_object_registry(obj):
    """
    Ensure an object has an annotation registry and return it.
    For objects that can't store attributes directly (like built-in types),
    use a global registry keyed by object id.
    :param obj: The object to ensure has an annotation registry.
    :return: The object's annotation registry.
    """
    # Try to store on the object directly first
    try:
        if not hasattr(obj, OBJECT_ANNOTATIONS_ATTR):
            setattr(obj, OBJECT_ANNOTATIONS_ATTR, {
                "constraints": [],
                "directives": []
            })
        return getattr(obj, OBJECT_ANNOTATIONS_ATTR)
    except (AttributeError, TypeError):
        # Object doesn't support attribute assignment (e.g., built-in types)
        # Use global registry instead
        obj_id = id(obj)
        if obj_id not in _OBJECT_ANNOTATION_REGISTRY:
            _OBJECT_ANNOTATION_REGISTRY[obj_id] = {
                "constraints": [],
                "directives": []
            }
        return _OBJECT_ANNOTATION_REGISTRY[obj_id]

def _annotate_object(obj, annotation_type, **kwargs):
    """
    Apply an annotation to a specific object instance.
    :param obj: The object to annotate.
    :param annotation_type: The type of annotation (e.g., 'orientation', 'cyclic').
    :param kwargs: The annotation parameters.
    :return: The annotated object (for chaining).
    """
    registry = _ensure_object_registry(obj)
    
    # Determine if it's a constraint or directive and validate
    if annotation_type in CONSTRAINT_TYPES:
        validate_fields(annotation_type, kwargs, CONSTRAINT_TYPES[annotation_type])
        entry = {annotation_type: kwargs}
        registry["constraints"].append(entry)
    elif annotation_type in DIRECTIVE_TYPES:
        validate_fields(annotation_type, kwargs, DIRECTIVE_TYPES[annotation_type])
        entry = {annotation_type: kwargs}
        registry["directives"].append(entry)
    else:
        raise ValueError(f"Unknown annotation type '{annotation_type}' for object annotation.")
    
    return obj

# Object-level annotation functions
def annotate_orientation(obj, **kwargs):
    """Apply orientation annotation to a specific object."""
    return _annotate_object(obj, 'orientation', **kwargs)

def annotate_cyclic(obj, **kwargs):
    """Apply cyclic annotation to a specific object."""
    return _annotate_object(obj, 'cyclic', **kwargs)

def annotate_group(obj, **kwargs):
    """Apply group annotation to a specific object."""
    return _annotate_object(obj, 'group', **kwargs)

def annotate_atomColor(obj, **kwargs):
    """Apply atomColor annotation to a specific object."""
    return _annotate_object(obj, 'atomColor', **kwargs)

def annotate_size(obj, **kwargs):
    """Apply size annotation to a specific object."""
    return _annotate_object(obj, 'size', **kwargs)

def annotate_icon(obj, **kwargs):
    """Apply icon annotation to a specific object."""
    return _annotate_object(obj, 'icon', **kwargs)

def annotate_edgeColor(obj, **kwargs):
    """Apply edgeColor annotation to a specific object."""
    return _annotate_object(obj, 'edgeColor', **kwargs)

def annotate_projection(obj, **kwargs):
    """Apply projection annotation to a specific object."""
    return _annotate_object(obj, 'projection', **kwargs)

def annotate_attribute(obj, **kwargs):
    """Apply attribute annotation to a specific object."""
    return _annotate_object(obj, 'attribute', **kwargs)

def annotate_hideField(obj, **kwargs):
    """Apply hideField annotation to a specific object."""
    return _annotate_object(obj, 'hideField', **kwargs)

def annotate_hideAtom(obj, **kwargs):
    """Apply hideAtom annotation to a specific object."""
    return _annotate_object(obj, 'hideAtom', **kwargs)

def annotate_inferredEdge(obj, **kwargs):
    """Apply inferredEdge annotation to a specific object."""
    return _annotate_object(obj, 'inferredEdge', **kwargs)

# General purpose function for applying any annotation type
def annotate(obj, annotation_type, **kwargs):
    """
    Apply any annotation type to a specific object.
    :param obj: The object to annotate.
    :param annotation_type: The type of annotation (e.g., 'orientation', 'cyclic').
    :param kwargs: The annotation parameters.
    :return: The annotated object (for chaining).
    """
    return _annotate_object(obj, annotation_type, **kwargs)

def collect_decorators(obj):
    """
    Collect all decorators applied to the class of the given object,
    as well as any annotations applied directly to the object instance.
    :param obj: The object whose class decorators and object annotations should be collected.
    :return: A combined dictionary of constraints and directives.
    """
    combined_registry = {
        "constraints": [],
        "directives": []
    }

    # Traverse the class hierarchy for class-level annotations
    for cls in obj.__class__.__mro__:
        if hasattr(cls, "__spytial_registry__"):
            combined_registry["constraints"].extend(cls.__spytial_registry__["constraints"])
            combined_registry["directives"].extend(cls.__spytial_registry__["directives"])
    
    # Add object-level annotations if they exist
    # First check if stored on object directly
    if hasattr(obj, OBJECT_ANNOTATIONS_ATTR):
        object_registry = getattr(obj, OBJECT_ANNOTATIONS_ATTR)
        combined_registry["constraints"].extend(object_registry["constraints"])
        combined_registry["directives"].extend(object_registry["directives"])
    
    # Then check global registry for objects that can't store attributes
    obj_id = id(obj)
    if obj_id in _OBJECT_ANNOTATION_REGISTRY:
        object_registry = _OBJECT_ANNOTATION_REGISTRY[obj_id]
        combined_registry["constraints"].extend(object_registry["constraints"])
        combined_registry["directives"].extend(object_registry["directives"])
    
    return combined_registry

def serialize_to_yaml_string(decorators):
    """
    Serialize the collected constraints and directives to a YAML string.
    :param decorators: The collected decorators (constraints and directives).
    :return: YAML string representation of the decorators.
    """
    return yaml.dump(decorators, default_flow_style=False)

