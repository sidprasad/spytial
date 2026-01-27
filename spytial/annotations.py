#
# sPyTial Annotation System
#


import yaml
import re


class NoAliasDumper(yaml.Dumper):
    def ignore_aliases(self, data):
        return True


# Registry to store constraints and directives
# This is now class-level, not global
CONSTRAINT_TYPES = {
    "cyclic": ["selector", "direction"],
    "orientation": ["selector", "directions"],
    "align": ["selector", "direction"],
    "group": [
        {
            "required": ["field", "groupOn", "addToGroup"],
            "optional": ["selector", "showLabel"],
        },  # Legacy, more ergonomic
        {
            "required": ["selector", "name"],
            "optional": ["addEdge"],
        },  # Selector-based group constraint
    ],
}

DIRECTIVE_TYPES = {
    "atomColor": ["selector", "value"],
    "size": ["selector", "height", "width"],
    "icon": ["selector", "path", "showLabels"],
    "edgeColor": {"required": ["field", "value"], "optional": ["selector", "style", "weight", "showLabel", "hideLabel"]},
    "projection": ["sig"],
    "attribute": {"required": ["field"], "optional": ["selector"]},
    "hideField": {"required": ["field"], "optional": ["selector"]},
    "hideAtom": ["selector"],
    "inferredEdge": {"required": ["name", "selector"], "optional": ["color"]},
    "flag": ["name"],
}

# Object-level annotation storage attribute name
OBJECT_ANNOTATIONS_ATTR = "__spytial_object_annotations__"

# Object ID storage attribute name (for self-reference)
OBJECT_ID_ATTR = "__spytial_object_id__"

# Global registry for objects that can't store annotations directly
_OBJECT_ANNOTATION_REGISTRY = {}

# Global registry for object IDs (for objects that can't store attributes)
_OBJECT_ID_REGISTRY = {}

# Counter for generating unique object IDs
_OBJECT_ID_COUNTER = 0

# =============================================
# Type Alias Annotation System using typing.Annotated
# =============================================
#
# This system leverages Python's typing.Annotated to attach spytial
# annotations directly to type aliases in a clean, declarative way:
#
#   from typing import Annotated
#   import spytial
#
#   IntList = Annotated[list[int],
#       spytial.Orientation(selector='items', directions=['horizontal']),
#       spytial.AtomColor(selector='self', value='blue')
#   ]
#
# This is the standard Python pattern for type metadata and works
# beautifully with type checkers.


class SpytialAnnotation:
    """
    Base class for spytial type annotations.

    Subclasses represent specific constraints or directives that can be
    attached to type aliases using typing.Annotated.
    """

    _annotation_type: str = None
    _is_constraint: bool = True

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def to_entry(self):
        """Convert to the internal registry format."""
        return {self._annotation_type: self.kwargs}

    def __repr__(self):
        args = ", ".join(f"{k}={v!r}" for k, v in self.kwargs.items())
        return f"{self.__class__.__name__}({args})"


# =============================================
# Constraint Annotation Classes
# =============================================


class Orientation(SpytialAnnotation):
    """
    Orientation constraint for spatial layout.

    Usage:
        from typing import Annotated
        IntList = Annotated[list[int], Orientation(selector='items', directions=['horizontal'])]
    """

    _annotation_type = "orientation"
    _is_constraint = True

    def __init__(self, *, selector: str, directions: list):
        super().__init__(selector=selector, directions=directions)


class Cyclic(SpytialAnnotation):
    """
    Cyclic constraint for circular layouts.

    Usage:
        NodeRing = Annotated[list[Node], Cyclic(selector='items', direction='clockwise')]
    """

    _annotation_type = "cyclic"
    _is_constraint = True

    def __init__(self, *, selector: str, direction: str):
        super().__init__(selector=selector, direction=direction)


class Align(SpytialAnnotation):
    """
    Alignment constraint.

    Usage:
        AlignedList = Annotated[list[int], Align(selector='items', direction='left')]
    """

    _annotation_type = "align"
    _is_constraint = True

    def __init__(self, *, selector: str, direction: str):
        super().__init__(selector=selector, direction=direction)


class Group(SpytialAnnotation):
    """
    Grouping constraint.

    Usage (field-based):
        Tree = Annotated[TreeNode, Group(field='children', groupOn=0, addToGroup=1)]

    Usage (selector-based):
        Grouped = Annotated[MyType, Group(selector='items', name='mygroup')]
    """

    _annotation_type = "group"
    _is_constraint = True

    def __init__(self, **kwargs):
        # Accept either field-based or selector-based parameters
        super().__init__(**kwargs)


# =============================================
# Directive Annotation Classes
# =============================================


class AtomColor(SpytialAnnotation):
    """
    Atom color directive.

    Usage:
        ColoredList = Annotated[list[int], AtomColor(selector='self', value='blue')]
    """

    _annotation_type = "atomColor"
    _is_constraint = False

    def __init__(self, *, selector: str, value: str):
        super().__init__(selector=selector, value=value)


class Size(SpytialAnnotation):
    """
    Size directive.

    Usage:
        SizedList = Annotated[list[int], Size(selector='items', height=50, width=50)]
    """

    _annotation_type = "size"
    _is_constraint = False

    def __init__(self, *, selector: str, height: int, width: int):
        super().__init__(selector=selector, height=height, width=width)


class Icon(SpytialAnnotation):
    """
    Icon directive.

    Usage:
        IconList = Annotated[list[int], Icon(selector='items', path='icon.svg', showLabels=True)]
    """

    _annotation_type = "icon"
    _is_constraint = False

    def __init__(self, *, selector: str, path: str, showLabels: bool = True):
        super().__init__(selector=selector, path=path, showLabels=showLabels)


class EdgeColor(SpytialAnnotation):
    """
    Edge color directive.

    Usage:
        ColoredEdges = Annotated[Tree, EdgeColor(field='children', value='red')]
        StyledEdges = Annotated[Tree, EdgeColor(field='Uses', value='#d10000', style='dashed', weight=3, showLabel=False)]
    """

    _annotation_type = "edgeColor"
    _is_constraint = False

    def __init__(self, *, field: str, value: str, selector: str = None,
                 style: str = None, weight: int = None, showLabel: bool = None,
                 hideLabel: bool = None):
        kwargs = {"field": field, "value": value}
        if selector is not None:
            kwargs["selector"] = selector
        if style is not None:
            kwargs["style"] = style
        if weight is not None:
            kwargs["weight"] = weight
        if showLabel is not None:
            kwargs["showLabel"] = showLabel
        if hideLabel is not None:
            kwargs["hideLabel"] = hideLabel
        super().__init__(**kwargs)


class HideField(SpytialAnnotation):
    """
    Hide field directive.

    Usage:
        CleanView = Annotated[MyClass, HideField(field='_private')]
    """

    _annotation_type = "hideField"
    _is_constraint = False

    def __init__(self, *, field: str, selector: str = None):
        kwargs = {"field": field}
        if selector is not None:
            kwargs["selector"] = selector
        super().__init__(**kwargs)


class HideAtom(SpytialAnnotation):
    """
    Hide atom directive.

    Usage:
        Filtered = Annotated[list[int], HideAtom(selector='hidden')]
    """

    _annotation_type = "hideAtom"
    _is_constraint = False

    def __init__(self, *, selector: str):
        super().__init__(selector=selector)


class Projection(SpytialAnnotation):
    """
    Projection directive.

    Usage:
        Projected = Annotated[MyType, Projection(sig='MySig')]
    """

    _annotation_type = "projection"
    _is_constraint = False

    def __init__(self, *, sig: str):
        super().__init__(sig=sig)


class Attribute(SpytialAnnotation):
    """
    Attribute directive.

    Usage:
        WithAttr = Annotated[MyType, Attribute(field='value')]
    """

    _annotation_type = "attribute"
    _is_constraint = False

    def __init__(self, *, field: str, selector: str = None):
        kwargs = {"field": field}
        if selector is not None:
            kwargs["selector"] = selector
        super().__init__(**kwargs)


class InferredEdge(SpytialAnnotation):
    """
    Inferred edge directive.

    Usage:
        WithEdges = Annotated[Graph, InferredEdge(name='connection', selector='nodes')]
    """

    _annotation_type = "inferredEdge"
    _is_constraint = False

    def __init__(self, *, name: str, selector: str, color: str = None):
        kwargs = {"name": name, "selector": selector}
        if color is not None:
            kwargs["color"] = color
        super().__init__(**kwargs)


class Flag(SpytialAnnotation):
    """
    Flag directive.

    Usage:
        Flagged = Annotated[MyType, Flag(name='debug')]
    """

    _annotation_type = "flag"
    _is_constraint = False

    def __init__(self, *, name: str):
        super().__init__(name=name)

    def to_entry(self):
        """Flags store just the name as a scalar."""
        return {self._annotation_type: self.kwargs["name"]}


def extract_spytial_annotations(type_hint):
    """
    Extract spytial annotations from a typing.Annotated type hint.

    :param type_hint: A type hint, possibly Annotated with spytial markers.
    :return: A dict with 'constraints' and 'directives' lists, or None if no annotations.
    """
    import typing

    # Check if it's an Annotated type
    origin = typing.get_origin(type_hint)
    if origin is not typing.Annotated:
        return None

    args = typing.get_args(type_hint)
    if len(args) < 2:
        return None

    # First arg is the base type, rest are annotations
    annotations = args[1:]

    constraints = []
    directives = []

    for ann in annotations:
        if isinstance(ann, SpytialAnnotation):
            entry = ann.to_entry()
            if ann._is_constraint:
                constraints.append(entry)
            else:
                directives.append(entry)

    if not constraints and not directives:
        return None

    return {"constraints": constraints, "directives": directives}


def get_base_type(type_hint):
    """
    Get the base type from an Annotated type hint.

    :param type_hint: A type hint, possibly Annotated.
    :return: The base type (unwrapped from Annotated if applicable).
    """
    import typing

    origin = typing.get_origin(type_hint)
    if origin is typing.Annotated:
        args = typing.get_args(type_hint)
        if args:
            return args[0]
    return type_hint


# Legacy registry-based system (kept for backward compatibility)
_TYPE_ALIAS_ANNOTATION_REGISTRY = {}


def _normalize_type_alias_key(type_alias):
    """
    Normalize a type alias to a consistent hashable key.
    Handles generic aliases, typing constructs, and Python 3.12+ TypeAliasType.
    :param type_alias: The type alias to normalize.
    :return: A hashable key representing the type alias.
    """
    import typing
    import sys

    # For Python 3.12+ TypeAliasType (from `type X = ...` statement)
    if sys.version_info >= (3, 12):
        try:
            from typing import TypeAliasType

            if isinstance(type_alias, TypeAliasType):
                # Use the name and underlying value for uniqueness
                return ("TypeAliasType", type_alias.__name__, type_alias.__value__)
        except ImportError:
            pass

    # For generic aliases (list[int], dict[str, int], etc.)
    origin = typing.get_origin(type_alias)
    if origin is not None:
        args = typing.get_args(type_alias)
        return (origin, args)

    # For regular types and simple aliases
    return type_alias


def annotate_type_alias(type_alias, annotation_type, **kwargs):
    """
    Attach a spytial annotation to a type alias.

    This function allows you to annotate type aliases (e.g., list[int], MyTypeAlias)
    with spatial constraints and directives. When objects are visualized, if their
    type annotation matches a registered type alias, these annotations are applied.

    Usage:
        # Define a type alias
        IntList = list[int]

        # Annotate it
        annotate_type_alias(IntList, 'orientation', selector='items', directions=['horizontal'])
        annotate_type_alias(IntList, 'atomColor', selector='self', value='blue')

        # Or use the convenience functions:
        annotate_type_alias_orientation(IntList, selector='items', directions=['horizontal'])

    :param type_alias: The type alias to annotate (e.g., list[int], MyClass, etc.)
    :param annotation_type: The type of annotation ('orientation', 'group', etc.)
    :param kwargs: The annotation parameters.
    :return: The type alias (for chaining).
    """
    key = _normalize_type_alias_key(type_alias)

    if key not in _TYPE_ALIAS_ANNOTATION_REGISTRY:
        _TYPE_ALIAS_ANNOTATION_REGISTRY[key] = {"constraints": [], "directives": []}

    registry = _TYPE_ALIAS_ANNOTATION_REGISTRY[key]

    # Validate and add the annotation
    if annotation_type in CONSTRAINT_TYPES:
        validate_fields(annotation_type, kwargs, CONSTRAINT_TYPES[annotation_type])
        entry = {annotation_type: kwargs}
        registry["constraints"].append(entry)
    elif annotation_type in DIRECTIVE_TYPES:
        validate_fields(annotation_type, kwargs, DIRECTIVE_TYPES[annotation_type])
        # Special handling for flag directives - store as scalar
        if annotation_type == "flag" and "name" in kwargs:
            entry = {annotation_type: kwargs["name"]}
        else:
            entry = {annotation_type: kwargs}
        registry["directives"].append(entry)
    else:
        raise ValueError(
            f"Unknown annotation type '{annotation_type}' for type alias annotation."
        )

    return type_alias


def get_type_alias_annotations(type_alias):
    """
    Retrieve annotations registered for a type alias.

    :param type_alias: The type alias to look up.
    :return: A dictionary with 'constraints' and 'directives' lists, or None if not found.
    """
    key = _normalize_type_alias_key(type_alias)
    return _TYPE_ALIAS_ANNOTATION_REGISTRY.get(key)


def clear_type_alias_annotations(type_alias=None):
    """
    Clear annotations for a specific type alias or all type aliases.

    Note: This only clears the legacy registry-based annotations.
    Annotations using typing.Annotated are immutable and don't need clearing.

    :param type_alias: If provided, clear only this type alias's annotations.
                       If None, clear all type alias annotations.
    """
    global _TYPE_ALIAS_ANNOTATION_REGISTRY
    if type_alias is None:
        _TYPE_ALIAS_ANNOTATION_REGISTRY.clear()
    else:
        key = _normalize_type_alias_key(type_alias)
        if key in _TYPE_ALIAS_ANNOTATION_REGISTRY:
            del _TYPE_ALIAS_ANNOTATION_REGISTRY[key]


def list_type_alias_annotations():
    """
    List all registered type alias annotations (legacy registry).

    :return: A dictionary mapping type alias keys to their annotation registries.
    """
    return dict(_TYPE_ALIAS_ANNOTATION_REGISTRY)


def reset_object_ids():
    """
    Reset the global object ID state. Useful for testing or when you need
    deterministic object ID generation across multiple runs.

    Warning: This will clear all existing object ID mappings, so existing
    selectors that depend on previous object IDs may no longer work.
    """
    global _OBJECT_ID_COUNTER, _OBJECT_ID_REGISTRY
    _OBJECT_ID_COUNTER = 0
    _OBJECT_ID_REGISTRY.clear()

    # Also clear object ID attributes from any objects that have them
    # Note: We can't easily find all objects that have the attribute,
    # so this is a best-effort cleanup of the global registry only.


def _get_or_create_object_id(obj):
    """
    Get or create a unique ID for an object to enable self-reference in selectors.
    :param obj: The object to get/create an ID for.
    :return: A unique string ID for the object.
    """
    global _OBJECT_ID_COUNTER

    # Try to get existing ID from the object directly
    try:
        if hasattr(obj, OBJECT_ID_ATTR):
            return getattr(obj, OBJECT_ID_ATTR)
    except (AttributeError, TypeError):
        pass

    # Check global registry for objects that can't store attributes
    obj_python_id = id(obj)
    if obj_python_id in _OBJECT_ID_REGISTRY:
        return _OBJECT_ID_REGISTRY[obj_python_id]

    # Create new unique ID
    _OBJECT_ID_COUNTER += 1
    unique_id = f"obj_{_OBJECT_ID_COUNTER}"

    # Store the ID
    try:
        setattr(obj, OBJECT_ID_ATTR, unique_id)
    except (AttributeError, TypeError):
        # Object doesn't support attribute assignment, use global registry
        _OBJECT_ID_REGISTRY[obj_python_id] = unique_id

    return unique_id


def _process_selector_for_self_reference(selector, obj_id):
    """
    Process a selector string to replace 'self' references with the object's unique ID.
    :param selector: The original selector string.
    :param obj_id: The unique ID of the object being annotated.
    :return: The processed selector string.
    """
    if selector is None:
        return selector

    # Replace all instances of the entire word 'self' with the object's unique ID
    return re.sub(r"\bself\b", obj_id, selector)


def validate_fields(type_, kwargs, valid_fields):
    """
    Validate that the required fields for a given type are present in kwargs.
    For constraints that support multiple parameter sets (like group), try each set.
    :param type_: The type of constraint or directive.
    :param kwargs: The provided fields for the decorator.
    :param valid_fields: The list of required fields for the type, or a list of alternative field sets.
    :raises ValueError: If no valid field set matches the provided kwargs.
    """
    # Handle multiple alternatives (for group)
    if (
        isinstance(valid_fields, list)
        and len(valid_fields) > 0
        and isinstance(valid_fields[0], (list, dict))
    ):
        for field_set in valid_fields:
            if isinstance(field_set, dict):
                required = field_set.get("required", [])
                optional = field_set.get("optional", [])
            else:
                required = field_set
                optional = []

            missing_fields = [field for field in required if field not in kwargs]
            # Accept if all required fields are present
            if not missing_fields:
                # Optionally: check for unknown fields
                all_valid_fields = required + optional
                unknown_fields = [
                    field for field in kwargs if field not in all_valid_fields
                ]
                if unknown_fields:
                    print(
                        f"Warning: Unknown fields for '{type_}': {', '.join(unknown_fields)}"
                    )
                return

        # None matched - create error message
        field_set_descriptions = []
        for i, field_set in enumerate(valid_fields):
            if isinstance(field_set, dict):
                req = field_set.get("required", [])
                opt = field_set.get("optional", [])
                desc = (
                    f"Set {i+1}: required: {', '.join(req)}; optional: {', '.join(opt)}"
                )
            else:
                desc = f"Set {i+1}: {', '.join(field_set)}"
            field_set_descriptions.append(desc)

        raise ValueError(
            f"No valid field set found for '{type_}'. "
            f"Expected one of: {' OR '.join(field_set_descriptions)}. "
            f"Provided: {', '.join(kwargs.keys())}"
        )
    else:
        # Single set (list or dict)
        if isinstance(valid_fields, dict):
            required = valid_fields.get("required", [])
            optional = valid_fields.get("optional", [])
        else:
            required = valid_fields
            optional = []

        missing_fields = [field for field in required if field not in kwargs]
        if missing_fields:
            raise ValueError(
                f"Missing required fields for '{type_}': {', '.join(missing_fields)}"
            )

        # Optionally: check for unknown fields
        all_valid_fields = required + optional
        unknown_fields = [field for field in kwargs if field not in all_valid_fields]
        if unknown_fields:
            print(f"Warning: Unknown fields for '{type_}': {', '.join(unknown_fields)}")


def _create_decorator(constraint_type):
    """
    Create a decorator function for a specific constraint or directive type.
    This now works for both classes and objects in a more Pythonic way.
    :param constraint_type: The type of constraint or directive (e.g., 'cyclic', 'orientation').
    :return: A decorator function that works on both classes and objects.
    """

    def decorator(**kwargs):
        def unified_decorator(target):
            # Check if target is a class (type) or an object instance
            if isinstance(target, type):
                # Class decoration (original behavior)
                # Check if this CLASS (not inherited) has its own registry
                if "__spytial_registry__" not in target.__dict__:
                    # Create a new registry for this class
                    target.__spytial_registry__ = {"constraints": [], "directives": []}

                # Determine if it's a constraint or directive
                if constraint_type in CONSTRAINT_TYPES:
                    # Validate fields for constraints
                    validate_fields(
                        constraint_type, kwargs, CONSTRAINT_TYPES[constraint_type]
                    )
                    entry = {constraint_type: kwargs}
                    target.__spytial_registry__["constraints"].append(entry)
                elif constraint_type in DIRECTIVE_TYPES:
                    # Validate fields for directives
                    validate_fields(
                        constraint_type, kwargs, DIRECTIVE_TYPES[constraint_type]
                    )

                    # Special handling for flag directives - store as scalar
                    if constraint_type == "flag" and "name" in kwargs:
                        entry = {constraint_type: kwargs["name"]}
                    else:
                        entry = {constraint_type: kwargs}

                    target.__spytial_registry__["directives"].append(entry)
                else:
                    raise ValueError(
                        f"Unknown type '{constraint_type}' for sPyTial decorator."
                    )

                return target
            else:
                # Object annotation (new ergonomic behavior)
                return _annotate_object(target, constraint_type, **kwargs)

        return unified_decorator

    return decorator


# Create individual decorator functions for each constraint and directive type
orientation = _create_decorator("orientation")
cyclic = _create_decorator("cyclic")
align = _create_decorator("align")
group = _create_decorator("group")
atomColor = _create_decorator("atomColor")
size = _create_decorator("size")
icon = _create_decorator("icon")
edgeColor = _create_decorator("edgeColor")
projection = _create_decorator("projection")
attribute = _create_decorator("attribute")
hideField = _create_decorator("hideField")
hideAtom = _create_decorator("hideAtom")
inferredEdge = _create_decorator("inferredEdge")
flag = _create_decorator("flag")


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
            setattr(obj, OBJECT_ANNOTATIONS_ATTR, {"constraints": [], "directives": []})
        return getattr(obj, OBJECT_ANNOTATIONS_ATTR)
    except (AttributeError, TypeError):
        # Object doesn't support attribute assignment (e.g., built-in types)
        # Use global registry instead
        obj_id = id(obj)
        if obj_id not in _OBJECT_ANNOTATION_REGISTRY:
            _OBJECT_ANNOTATION_REGISTRY[obj_id] = {"constraints": [], "directives": []}
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

    # Get or create unique ID for this object to enable self-reference
    obj_id = _get_or_create_object_id(obj)

    # Process any selectors in kwargs to handle self-reference
    processed_kwargs = kwargs.copy()
    if "selector" in processed_kwargs:
        processed_kwargs["selector"] = _process_selector_for_self_reference(
            processed_kwargs["selector"], obj_id
        )

    # Determine if it's a constraint or directive and validate
    if annotation_type in CONSTRAINT_TYPES:
        validate_fields(
            annotation_type, processed_kwargs, CONSTRAINT_TYPES[annotation_type]
        )
        entry = {annotation_type: processed_kwargs}
        registry["constraints"].append(entry)
    elif annotation_type in DIRECTIVE_TYPES:
        validate_fields(
            annotation_type, processed_kwargs, DIRECTIVE_TYPES[annotation_type]
        )

        # Special handling for flag directives - store as scalar
        if annotation_type == "flag" and "name" in processed_kwargs:
            entry = {annotation_type: processed_kwargs["name"]}
        else:
            entry = {annotation_type: processed_kwargs}

        registry["directives"].append(entry)
    else:
        raise ValueError(
            f"Unknown annotation type '{annotation_type}' for object annotation."
        )

    return obj


# Object-level annotation functions
def annotate_orientation(obj, **kwargs):
    """Apply orientation annotation to a specific object."""
    return _annotate_object(obj, "orientation", **kwargs)


def annotate_cyclic(obj, **kwargs):
    """Apply cyclic annotation to a specific object."""
    return _annotate_object(obj, "cyclic", **kwargs)


def annotate_align(obj, **kwargs):
    """Apply align annotation to a specific object."""
    return _annotate_object(obj, "align", **kwargs)


def annotate_group(obj, **kwargs):
    """Apply group annotation to a specific object."""
    return _annotate_object(obj, "group", **kwargs)


def annotate_atomColor(obj, **kwargs):
    """Apply atomColor annotation to a specific object."""
    return _annotate_object(obj, "atomColor", **kwargs)


def annotate_size(obj, **kwargs):
    """Apply size annotation to a specific object."""
    return _annotate_object(obj, "size", **kwargs)


def annotate_icon(obj, **kwargs):
    """Apply icon annotation to a specific object."""
    return _annotate_object(obj, "icon", **kwargs)


def annotate_edgeColor(obj, **kwargs):
    """Apply edgeColor annotation to a specific object."""
    return _annotate_object(obj, "edgeColor", **kwargs)


def annotate_projection(obj, **kwargs):
    """Apply projection annotation to a specific object."""
    return _annotate_object(obj, "projection", **kwargs)


def annotate_attribute(obj, **kwargs):
    """Apply attribute annotation to a specific object."""
    return _annotate_object(obj, "attribute", **kwargs)


def annotate_hideField(obj, **kwargs):
    """Apply hideField annotation to a specific object."""
    return _annotate_object(obj, "hideField", **kwargs)


def annotate_hideAtom(obj, **kwargs):
    """Apply hideAtom annotation to a specific object."""
    return _annotate_object(obj, "hideAtom", **kwargs)


def annotate_inferredEdge(obj, **kwargs):
    """Apply inferredEdge annotation to a specific object."""
    return _annotate_object(obj, "inferredEdge", **kwargs)


def annotate_flag(obj, **kwargs):
    """Apply flag annotation to a specific object."""
    return _annotate_object(obj, "flag", **kwargs)


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


# Conditional decorator macro for sPyTial
def apply_if(condition, *decorators):
    """
    Conditional decorator macro for sPyTial.
    Usage:
        @apply_if(CONDITION,
            orientation(...),
            hideField(...),
            attribute(...),
            ...
        )
        class MyClass: ...
    If CONDITION is True, applies all decorators in order to the class.
    If CONDITION is False, returns the class unchanged.
    """

    def decorator(cls):
        if condition:
            for deco in decorators:
                cls = deco(cls)
        return cls

    return decorator


def collect_decorators(obj, type_hint=None):
    """
    Collect all decorators applied to the class of the given object,
    as well as any annotations applied directly to the object instance,
    and any annotations registered for matching type aliases.
    Respects inheritance control flags (dont_inherit_constraints, dont_inherit_directives).
    :param obj: The object whose class decorators and object annotations should be collected.
    :param type_hint: Optional type hint to look up type alias annotations.
    :return: A combined dictionary of constraints and directives.
    """
    combined_registry = {"constraints": [], "directives": []}

    # Check if current class has inheritance control flags
    should_inherit_constraints = not getattr(
        obj.__class__, "__spytial_no_inherit_constraints__", False
    )
    should_inherit_directives = not getattr(
        obj.__class__, "__spytial_no_inherit_directives__", False
    )

    # Traverse the class hierarchy
    for i, cls in enumerate(obj.__class__.__mro__):
        is_current_class = i == 0

        if hasattr(cls, "__spytial_registry__"):
            cls_registry = cls.__spytial_registry__

            if is_current_class:
                # For current class: include all from its registry
                combined_registry["constraints"].extend(cls_registry["constraints"])
                combined_registry["directives"].extend(cls_registry["directives"])
            else:
                # For parent classes: only include if inheritance is enabled
                if should_inherit_constraints:
                    combined_registry["constraints"].extend(cls_registry["constraints"])

                if should_inherit_directives:
                    combined_registry["directives"].extend(cls_registry["directives"])

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

    # Check for type alias annotations if a type hint was provided
    if type_hint is not None:
        type_alias_annotations = get_type_alias_annotations(type_hint)
        if type_alias_annotations:
            combined_registry["constraints"].extend(
                type_alias_annotations["constraints"]
            )
            combined_registry["directives"].extend(type_alias_annotations["directives"])

    return combined_registry


def serialize_to_yaml_string(decorators):
    """
    Serialize the collected constraints and directives to a YAML string.
    :param decorators: The collected decorators (constraints and directives).
    :return: YAML string representation of the decorators.
    """
    return yaml.dump(decorators, default_flow_style=False, Dumper=NoAliasDumper)


# Inheritance Control


def dont_inherit_constraints(cls):
    """
    Mark a class to not inherit constraints from parent classes.

    This is useful when you want to override a parent class's constraints.
    Constraints applied directly to this class are still included.

    Example:
        @orientation(selector='children', directions=['below'])
        class Parent:
            pass

        @dont_inherit_constraints
        class Child(Parent):
            # Will NOT have Parent's orientation constraint
            pass

    :param cls: The class to mark as not inheriting constraints.
    :return: The class (for chaining).
    """
    cls.__spytial_no_inherit_constraints__ = True
    return cls


def dont_inherit_directives(cls):
    """
    Mark a class to not inherit directives from parent classes.

    This is useful when you want to override a parent class's directives.
    Directives applied directly to this class are still included.

    Example:
        @atomColor(selector='root', value='red')
        class Parent:
            pass

        @dont_inherit_directives
        class Child(Parent):
            # Will NOT have Parent's atomColor directive
            pass

    :param cls: The class to mark as not inheriting directives.
    :return: The class (for chaining).
    """
    cls.__spytial_no_inherit_directives__ = True
    return cls


def dont_inherit_annotations(cls):
    """
    Mark a class to not inherit any annotations from parent classes.

    Shorthand for applying both dont_inherit_constraints and dont_inherit_directives.

    Example:
        @orientation(selector='children', directions=['below'])
        @atomColor(selector='root', value='red')
        class Parent:
            pass

        @dont_inherit_annotations
        class Child(Parent):
            # Will NOT have any annotations from Parent
            pass

    :param cls: The class to mark as not inheriting annotations.
    :return: The class (for chaining).
    """
    cls.__spytial_no_inherit_constraints__ = True
    cls.__spytial_no_inherit_directives__ = True
    return cls


# Export apply_if in module __all__
__all__ = [
    # ...other exports...
    "apply_if",
]
