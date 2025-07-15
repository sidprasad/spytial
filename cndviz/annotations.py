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
from functools import wraps

# Registry to store constraints and directives
cnd_registry = {
    "constraints": [],
    "directives": []
}

# Define valid types and their required fields
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
    Decorator to annotate classes or methods with constraints and directives.
    :param type_: The type of constraint or directive (e.g., 'cyclic', 'group', 'atomColor').
    :param kwargs: Additional parameters for the constraint or directive.
    """
    def decorator(obj):
        # Determine if it's a constraint or directive
        if type_ in CONSTRAINT_TYPES:
            # Validate fields for constraints
            validate_fields(type_, kwargs, CONSTRAINT_TYPES[type_])
            entry = {type_: kwargs}
            cnd_registry["constraints"].append(entry)
        elif type_ in DIRECTIVE_TYPES:
            # Validate fields for directives
            validate_fields(type_, kwargs, DIRECTIVE_TYPES[type_])
            entry = {type_: kwargs}
            cnd_registry["directives"].append(entry)
        else:
            raise ValueError(f"Unknown type '{type_}' for @cnd decorator.")

        return obj
    return decorator

def serialize_to_yaml_string():
    """
    Serialize the collected constraints and directives to a YAML string.
    :return: YAML string representation of the registry.
    """
    return yaml.dump(cnd_registry, default_flow_style=False)



## Do we even need this I guess?
def collect_decorators(obj):
    """
    Collect all decorators applied to the given object, including its children and related objects.
    :param obj: The root object (class or function) to start collecting decorators from.
    :return: A combined dictionary of constraints and directives.
    """
    combined_registry = {
        "constraints": [],
        "directives": []
    }

    # Helper function to merge registries
    def merge_registry(target_registry, source_registry):
        target_registry["constraints"].extend(source_registry["constraints"])
        target_registry["directives"].extend(source_registry["directives"])

    # Collect decorators for the current object
    if hasattr(obj, "__dict__"):
        for attr_name, attr_value in obj.__dict__.items():
            if callable(attr_value) or isinstance(attr_value, type):
                # Check if the attribute has decorators
                if hasattr(attr_value, "__module__") and hasattr(attr_value, "__qualname__"):
                    # Simulate decorator collection for this attribute
                    entry = {
                        "type": "unknown",  # Replace with actual type if available
                        "target": f"{attr_value.__module__}.{attr_value.__qualname__}"
                    }
                    combined_registry["constraints"].append(entry)

    # Recursively collect decorators from base classes (if obj is a class)
    if isinstance(obj, type):
        for base_class in obj.__bases__:
            base_registry = collect_decorators(base_class)
            merge_registry(combined_registry, base_registry)

    return combined_registry

