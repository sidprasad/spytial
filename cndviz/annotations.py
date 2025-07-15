#
# Users should be able to annotate their classes with cnd constraints and directives.
# @cnd('cyclic', selector='left', direction='clockwise')
# @cnd('orientation', selector='left', directions=['left', 'below'])
# @cnd('group', field='fruit', groupOn=0, addToGroup=1)
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

def cnd(type_, **kwargs):
    """
    Decorator to annotate classes with constraints and directives.
    :param type_: The type of constraint or directive (e.g., 'cyclic', 'group', 'atomColor').
    :param kwargs: Additional parameters for the constraint or directive.
    """
    def decorator(cls):
        if not hasattr(cls, "__cnd_registry__"):
            cls.__cnd_registry__ = {
                "constraints": [],
                "directives": []
            }
        
        # Determine if it's a constraint or directive
        if type_ in CONSTRAINT_TYPES:
            # Validate fields for constraints
            validate_fields(type_, kwargs, CONSTRAINT_TYPES[type_])
            entry = {type_: kwargs}
            cls.__cnd_registry__["constraints"].append(entry)
        elif type_ in DIRECTIVE_TYPES:
            # Validate fields for directives
            validate_fields(type_, kwargs, DIRECTIVE_TYPES[type_])
            entry = {type_: kwargs}
            cls.__cnd_registry__["directives"].append(entry)
        else:
            raise ValueError(f"Unknown type '{type_}' for @cnd decorator.")
        
        return cls
    return decorator

def collect_decorators(obj):
    """
    Collect all decorators applied to the class of the given object.
    :param obj: The object whose class decorators should be collected.
    :return: A combined dictionary of constraints and directives.
    """
    combined_registry = {
        "constraints": [],
        "directives": []
    }

    # Traverse the class hierarchy
    for cls in obj.__class__.__mro__:
        if hasattr(cls, "__cnd_registry__"):
            combined_registry["constraints"].extend(cls.__cnd_registry__["constraints"])
            combined_registry["directives"].extend(cls.__cnd_registry__["directives"])
    
    return combined_registry

def serialize_to_yaml_string(decorators):
    """
    Serialize the collected constraints and directives to a YAML string.
    :param decorators: The collected decorators (constraints and directives).
    :return: YAML string representation of the decorators.
    """
    return yaml.dump(decorators, default_flow_style=False)

