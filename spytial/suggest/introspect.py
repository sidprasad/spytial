"""Discover a class's fields without requiring it to be a dataclass.

Three tiers, best-effort, mirroring how the relationalizers read objects:
  1. dataclass  -> ``dataclasses.fields()`` (names + declared types)
  2. annotations -> class-level ``__annotations__``
  3. ``__init__`` -> AST of ``self.x = ...`` assignments + signature defaults

An optional ``instance`` is sampled to confirm/fill types that static reading
can't recover (e.g. a plain class whose children default to ``None``).
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import re
import sys
import textwrap
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ._model import ClassInfo, FieldInfo

_MISSING = object()

_SCALAR_NAMES = {"int", "float", "str", "bool", "bytes", "complex", "Decimal"}
_TYPING_WRAPPERS = {"Optional", "Union", "Final", "Annotated", "ClassVar", "typing"}
_CONTAINER_NAMES = {
    "list": "list",
    "List": "list",
    "dict": "dict",
    "Dict": "dict",
    "Mapping": "dict",
    "set": "set",
    "Set": "set",
    "frozenset": "set",
    "tuple": "tuple",
    "Tuple": "tuple",
    "Sequence": "list",
    "Iterable": "list",
}

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def build_class_info(cls: type, instance: Any = None) -> ClassInfo:
    """Return a :class:`ClassInfo` for ``cls``, optionally sampling ``instance``."""
    agg = _sample_graph(instance, cls) if instance is not None else None
    fields = _discover(cls, instance, agg)
    return ClassInfo(cls=cls, fields=fields)


# --------------------------------------------------------------------------- #
# Field discovery tiers
# --------------------------------------------------------------------------- #


def _discover(cls: type, instance: Any, agg: Optional[dict]) -> List[FieldInfo]:
    # Merge field names from every source rather than stopping at the first that
    # yields anything: a plain class can carry a few class annotations *and* set
    # other fields only in __init__, and an instance can reveal more still. The
    # first source to name a field also supplies its type/default; later sources
    # only fill gaps and contribute names not seen yet.
    order: List[str] = []
    merged: dict = {}

    def add(name: str, annotation: Any, default: Any, source: str) -> None:
        if name not in merged:
            order.append(name)
            merged[name] = [annotation, default, source]
        else:
            entry = merged[name]
            if entry[0] is None and annotation is not None:
                entry[0] = annotation
            if entry[1] is _MISSING and default is not _MISSING:
                entry[1] = default

    if dataclasses.is_dataclass(cls):
        for f in dataclasses.fields(cls):
            add(f.name, f.type, _dc_default(f), "dataclass")
    else:
        for n, t in getattr(cls, "__annotations__", {}).items():
            add(n, t, _MISSING, "annotations")

    init_names = _init_assignment_names(cls)
    if init_names:
        sig_types, sig_defaults = _init_params(cls)
        for n in init_names:
            add(n, sig_types.get(n), sig_defaults.get(n, _MISSING), "init_ast")

    if agg:
        for n in agg:
            add(n, None, _MISSING, "instance")

    return [
        _build_field(cls, name, annotation, default, agg, source)
        for name in order
        for annotation, default, source in [merged[name]]
    ]


def _build_field(
    cls: type,
    name: str,
    annotation: Any,
    default: Any,
    agg: Optional[dict],
    source: str,
) -> FieldInfo:
    type_repr = _type_repr(annotation)
    has_none = default is None

    # Infer a type from the default literal when no annotation is present.
    if type_repr is None and default is not _MISSING and default is not None:
        type_repr, _ = _value_facts(default)

    # An Optional[...] / X | None annotation is itself proof the value can be None,
    # even with no default — so the edge excludes None and NoneType atoms are hidden.
    annotated_nullable = _is_nullable_annotation(type_repr)
    has_none = has_none or annotated_nullable

    container = _container_of(type_repr)
    is_self_ref = _is_self_ref(type_repr, cls)
    enum_members = _enum_members_from(annotation, default, type_repr, cls)
    is_scalar = _is_scalar(type_repr, container, is_self_ref, enum_members)

    # Fold in evidence aggregated across every sampled node of this class.
    record = agg.get(name) if agg else None
    if record:
        is_self_ref = is_self_ref or record["self"]
        # Observation overrides the weak signal of an __init__ parameter that
        # defaults to None while the attribute is never None (e.g. ``x or []``).
        # An Optional annotation, however, is authoritative and survives sampling.
        has_none = record["none"] or annotated_nullable
        if record["containers"]:
            container = container or sorted(record["containers"])[0]
        if enum_members is None and record["enum"]:
            enum_members = record["enum"]
        if type_repr is None and record["types"]:
            type_repr = sorted(record["types"])[0]
        is_scalar = is_scalar or _is_scalar(
            type_repr, container, is_self_ref, enum_members
        )

    return FieldInfo(
        name=name,
        type_repr=type_repr,
        is_self_ref=is_self_ref,
        container=container,
        is_scalar=is_scalar,
        enum_members=enum_members,
        has_none_default=has_none,
        is_private=name.startswith("_"),
        source=source,
    )


# --------------------------------------------------------------------------- #
# Type string analysis
# --------------------------------------------------------------------------- #


def _type_repr(annotation: Any) -> Optional[str]:
    if annotation is None or annotation is _MISSING:
        return None
    if isinstance(annotation, str):
        return annotation
    if isinstance(annotation, type):
        return annotation.__name__
    text = str(annotation)
    return text[len("typing.") :] if text.startswith("typing.") else text


def _referenced_names(type_repr: Optional[str]) -> set:
    if not type_repr:
        return set()
    return {
        m.group(0) for m in _IDENT.finditer(type_repr.replace("'", "").replace('"', ""))
    }


def _container_of(type_repr: Optional[str]) -> Optional[str]:
    for name in _referenced_names(type_repr):
        if name in _CONTAINER_NAMES:
            return _CONTAINER_NAMES[name]
    return None


def _is_nullable_annotation(type_repr: Optional[str]) -> bool:
    """True if the annotation admits None (``Optional[X]``, ``Union[X, None]``,
    ``X | None``) — independent of any default value."""
    names = _referenced_names(type_repr)
    return bool(names & {"Optional", "None", "NoneType"})


def _is_self_ref(type_repr: Optional[str], cls: type) -> bool:
    if not type_repr:
        return False
    names = _referenced_names(type_repr)
    if cls.__name__ in names:
        return True
    # A sibling class in the same module that itself looks node-like also counts.
    module = sys.modules.get(cls.__module__)
    if module is not None:
        for nm in names - _TYPING_WRAPPERS - _SCALAR_NAMES:
            obj = getattr(module, nm, None)
            if isinstance(obj, type) and obj is not cls and _looks_node_like(obj):
                return True
    return False


def _looks_node_like(other: type) -> bool:
    """A class is node-like if any of its own fields reference itself."""
    try:
        if dataclasses.is_dataclass(other):
            return any(
                other.__name__ in _referenced_names(_type_repr(f.type))
                for f in dataclasses.fields(other)
            )
        ann = getattr(other, "__annotations__", {})
        return any(
            other.__name__ in _referenced_names(_type_repr(t)) for t in ann.values()
        )
    except Exception:
        return False


def _is_scalar(
    type_repr: Optional[str],
    container: Optional[str],
    is_self_ref: bool,
    enum_members: Optional[List[str]],
) -> bool:
    if container or is_self_ref or enum_members or not type_repr:
        return False
    names = _referenced_names(type_repr) - _TYPING_WRAPPERS - {"NoneType", "None"}
    return bool(names) and names <= _SCALAR_NAMES


# --------------------------------------------------------------------------- #
# Enum / value facts
# --------------------------------------------------------------------------- #


def _enum_members_from(
    annotation: Any, default: Any, type_repr: Optional[str], cls: type
) -> Optional[List[str]]:
    # Default value is an actual enum member (e.g. ``color=BLACK``).
    if isinstance(default, Enum):
        return [m.name for m in type(default)]
    # Annotation resolves to an Enum subclass.
    resolved = (
        annotation if isinstance(annotation, type) else _resolve_type(type_repr, cls)
    )
    if isinstance(resolved, type) and issubclass(resolved, Enum):
        return [m.name for m in resolved]
    return None


def _resolve_type(type_repr: Optional[str], cls: type) -> Optional[type]:
    module = sys.modules.get(cls.__module__)
    if module is None:
        return None
    for nm in _referenced_names(type_repr) - _TYPING_WRAPPERS:
        obj = getattr(module, nm, None)
        if isinstance(obj, type):
            return obj
    return None


def _value_facts(value: Any, cls: Optional[type] = None) -> Tuple[Optional[str], bool]:
    """Return ``(type_repr, is_self_ref)`` for a concrete value."""
    if value is None:
        return None, False
    if isinstance(value, Enum):
        return type(value).__name__, False
    if isinstance(value, bool):
        return "bool", False
    if isinstance(value, (list, dict, set, tuple)):
        return type(value).__name__, False
    name = type(value).__name__
    is_self = cls is not None and name == cls.__name__
    return name, is_self


def _container_of_value(value: Any) -> Optional[str]:
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, set):
        return "set"
    if isinstance(value, tuple):
        return "tuple"
    return None


def _container_items(value: Any):
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(value)
    return []


def _instance_attrs(obj: Any) -> List[Tuple[str, Any]]:
    """Return ``(name, value)`` pairs for ``obj``, slots-aware.

    ``vars(obj)`` raises ``TypeError`` for a class that defines ``__slots__`` and
    carries no ``__dict__`` — which would silently drop every node of such a
    class from the graph walk. Read the instance ``__dict__`` when present and
    union in the slots declared across the MRO, skipping slots left unset on this
    instance (their descriptor raises ``AttributeError``).
    """
    items: Dict[str, Any] = {}
    inst_dict = getattr(obj, "__dict__", None)
    if isinstance(inst_dict, dict):
        items.update(inst_dict)
    for klass in type(obj).__mro__:
        slots = klass.__dict__.get("__slots__")
        if slots is None:
            continue
        if isinstance(slots, str):
            slots = (slots,)
        for name in slots:
            if name in ("__dict__", "__weakref__") or name in items:
                continue
            value = getattr(obj, name, _MISSING)
            if value is not _MISSING:
                items[name] = value
    return list(items.items())


def _sample_graph(root: Any, cls: type, max_nodes: int = 1000) -> dict:
    """Aggregate per-attribute type evidence over all reachable nodes of ``cls``.

    A bounded walk of the object graph starting at ``root``. For each attribute
    seen on a ``cls`` instance it records the value types, container kinds, enum
    members, and whether any value is itself a ``cls`` — so a field reads as
    structural if it is populated on *any* sampled node, not just ``root``.
    """
    from collections import deque

    agg: dict = {}
    seen = set()
    queue = deque([root])
    visited = 0
    while queue and visited < max_nodes:
        obj = queue.popleft()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        if not isinstance(obj, cls):
            continue
        visited += 1
        for name, value in _instance_attrs(obj):
            rec = agg.setdefault(
                name,
                {
                    "types": set(),
                    "containers": set(),
                    "enum": None,
                    "self": False,
                    "none": False,
                },
            )
            if value is None:
                rec["none"] = True
                continue
            if isinstance(value, Enum):
                rec["enum"] = [m.name for m in type(value)]
                continue
            container = _container_of_value(value)
            if container:
                rec["containers"].add(container)
                for item in _container_items(value):
                    if isinstance(item, cls):
                        rec["self"] = True
                    if id(item) not in seen:
                        queue.append(item)
            else:
                rec["types"].add(type(value).__name__)
                if isinstance(value, cls):
                    rec["self"] = True
                    if id(value) not in seen:
                        queue.append(value)
    return agg


# --------------------------------------------------------------------------- #
# __init__ introspection (AST + signature)
# --------------------------------------------------------------------------- #


def _init_assignment_names(cls: type) -> List[str]:
    init = cls.__dict__.get("__init__")
    if init is None:
        return []
    try:
        src = textwrap.dedent(inspect.getsource(init))
        tree = ast.parse(src)
    except (OSError, TypeError, SyntaxError, IndentationError):
        return []

    self_name = _self_param_name(tree)
    names: List[str] = []

    def record(target: ast.AST) -> None:
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == self_name
            and target.attr not in names
        ):
            names.append(target.attr)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, (ast.Tuple, ast.List)):
                    for elt in tgt.elts:
                        record(elt)
                else:
                    record(tgt)
        elif isinstance(node, ast.AnnAssign):
            record(node.target)
    return names


def _self_param_name(tree: ast.AST) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.args.args:
            return node.args.args[0].arg
    return "self"


def _init_params(cls: type) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    try:
        sig = inspect.signature(cls.__init__)
    except (ValueError, TypeError):
        return {}, {}
    types: Dict[str, Any] = {}
    defaults: Dict[str, Any] = {}
    for i, (name, param) in enumerate(sig.parameters.items()):
        if i == 0 or name in ("args", "kwargs"):
            continue
        if param.annotation is not inspect.Parameter.empty:
            types[name] = param.annotation
        if param.default is not inspect.Parameter.empty:
            defaults[name] = param.default
    return types, defaults


def _dc_default(field: "dataclasses.Field") -> Any:
    # Never invoke a default_factory: this is a static pass and the factory could
    # have side effects (open resources, mutate state) or be slow. The field's
    # annotation already carries the type, and a factory default is never None, so
    # _MISSING (an unknown, non-None default) is all the analyzer needs.
    if field.default is not dataclasses.MISSING:
        return field.default
    return _MISSING
