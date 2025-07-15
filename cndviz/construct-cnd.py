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

def cnd(type_, **kwargs):
    """
    Decorator to annotate classes or methods with constraints and directives.
    :param type_: The type of constraint or directive (e.g., 'cyclic', 'group').
    :param kwargs: Additional parameters for the constraint or directive.
    """
    def decorator(obj):
        # Add the constraint/directive to the registry
        entry = {"type": type_, **kwargs}
        if callable(obj):
            # If applied to a function or method
            entry["target"] = f"{obj.__module__}.{obj.__qualname__}"
        else:
            # If applied to a class
            entry["target"] = obj.__name__
        
        if type_ in ["cyclic", "orientation", "group"]:
            cnd_registry["constraints"].append(entry)
        else:
            cnd_registry["directives"].append(entry)
        
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

