"""
Relationalizer for generic objects with __dict__ or __slots__.

Design Decisions:
- Comprehensive inspection: Use inspect.getmembers to enumerate all attributes, ensuring we capture properties, descriptors, and inherited fields that serialization might include.
- Filtering for relevance: Skip language-hidden names (dunders and name-mangled `_Class__x` privates — single-underscore names are structure and stay), plus methods, functions, and modules, to focus on meaningful data for visualization. Values the walker refuses (spytial's own machinery) draw no edge.
- Serialization alignment: Include attributes even if not obviously serializable, as the relationalizer creates relations and the provider system handles serialization downstream.
- Property/descriptor handling: Evaluate properties and descriptors on the instance to get actual values, preventing issues with dynamic attributes.
- Performance: Limit to small/medium objects (<1 second) by using try-except for safe access and avoiding deep recursion.
- Overlap avoidance: Expand can_handle to include class-based objects but exclude basic types handled by other relationalizers (e.g., lists, dicts).
- Consistency: Maintain binary relations for simplicity, as established for generic objects.
"""

import inspect
from typing import Any, List, Tuple
from .base import RelationalizerBase, Atom, Relation

try:  # Python 3.14+ (PEP 649) exposes the annotation formats here.
    import annotationlib
except ImportError:  # pragma: no cover - the common path on older interpreters
    annotationlib = None


def _own_annotation_names(klass: type) -> List[str]:
    """Names *klass* itself annotates, ignoring the ones it inherits.

    Python 3.14 (PEP 649) keeps class annotations behind a lazily-called
    annotate function, so ``vars(klass)`` no longer carries an
    ``__annotations__`` entry and a plain dict lookup would report every class
    as fieldless. ``inspect.get_annotations`` reads them through the runtime
    API and, for a class, returns only that class's own annotations — which is
    what the MRO walk wants, and why ``klass.__annotations__`` is not consulted
    directly (it silently falls back to an inherited dict).

    Only the names are used, so the unevaluated form is requested wherever the
    interpreter offers the choice: under 3.14 the default format evaluates each
    annotation, and an unresolvable forward reference would raise where a dict
    lookup never could.
    """
    get_annotations = getattr(inspect, "get_annotations", None)
    if get_annotations is None:  # Python < 3.10
        return list(vars(klass).get("__annotations__", {}))

    kwargs = {}
    if annotationlib is not None:
        kwargs["format"] = annotationlib.Format.STRING
    try:
        return list(get_annotations(klass, **kwargs))
    except Exception:
        return list(vars(klass).get("__annotations__", {}))


def _mangling_prefixes(cls: type) -> Tuple[str, ...]:
    """The ``_Class__`` prefixes CPython gives ``__x`` names written in this MRO."""
    return tuple(f"_{k.__name__.lstrip('_')}__" for k in cls.__mro__ if k is not object)


def _is_hidden(name: str, mangling_prefixes: Tuple[str, ...]) -> bool:
    """True for names the *language* hides, rather than ones convention marks.

    A dunder is interpreter machinery, and a ``_Class__x`` name was written
    ``__x`` — private to the class body by an explicit language rule. A single
    leading underscore is convention only: Python decides state by assignment
    alone, and ``_next`` participates in the structure exactly as ``next``
    does. This is the reasoning DataclassRelationalizer already records for
    dataclass fields; applying it here keeps a ``_next`` pointer drawing an
    edge whether or not its class happens to be a dataclass.
    """
    if name.startswith("__") and name.endswith("__"):
        return True
    return any(name.startswith(prefix) for prefix in mangling_prefixes)


class GenericObjectRelationalizer(RelationalizerBase):
    """Handles generic objects with __dict__ or __slots__."""

    def can_handle(self, obj: Any) -> bool:
        # Handle objects with __dict__, __slots__, or any class-based object (excluding built-ins handled elsewhere)
        return (
            hasattr(obj, "__dict__")
            or hasattr(obj, "__slots__")
            or (
                hasattr(obj, "__class__")
                and not isinstance(
                    obj, (list, tuple, dict, str, int, float, bool, type)
                )
            )
        )

    def declared_relations(self, obj: Any) -> List[str]:
        """Annotated and slotted names across the MRO, set or not.

        Filtered by the same rule relationalize applies, so a declared name is
        always one an instance could populate.
        """
        mangling_prefixes = _mangling_prefixes(type(obj))
        names: List[str] = []
        for klass in type(obj).__mro__:
            if klass is object:
                continue
            declared = _own_annotation_names(klass)
            slots = vars(klass).get("__slots__", ())
            # __slots__ accepts a bare string for the single-slot case.
            declared.extend((slots,) if isinstance(slots, str) else slots)
            for name in declared:
                if not _is_hidden(name, mangling_prefixes) and name not in names:
                    names.append(name)
        return names

    def relationalize(self, obj: Any, walker_func) -> Tuple[List[Atom], List[Relation]]:
        obj_id = walker_func._get_id(obj)
        typ = type(obj).__name__
        caller_namespace = getattr(walker_func, "_caller_namespace", None)
        label = self._make_label_with_fallback(
            obj, typ, caller_namespace, obj_id, walker_func
        )
        atom = Atom(id=obj_id, type=typ, label=label)

        relations = []

        # Use inspect to get all members, filtering for relevant attributes
        mangling_prefixes = _mangling_prefixes(type(obj))
        for name, value in inspect.getmembers(obj):
            # Skip language-hidden names, methods, functions, modules, and built-ins.
            # A single leading underscore is not a skip: `_next` is structure, and
            # dropping it left a pointer drawing no edge on every non-dataclass.
            if (
                _is_hidden(name, mangling_prefixes)
                or inspect.ismethod(value)
                or inspect.isfunction(value)
                or inspect.ismodule(value)
                or inspect.isbuiltin(value)  # Catch built-in methods
            ):
                continue

            # Handle properties and descriptors by evaluating on the instance
            if isinstance(value, property) or hasattr(value, "__get__"):
                try:
                    actual_value = getattr(obj, name)
                    # Skip if it's still a descriptor or primitive
                    if actual_value is value:
                        continue
                    vid = walker_func(actual_value)
                    if vid is None:  # refused: spytial machinery, no edge
                        continue
                    relations.append(Relation(name, [obj_id, vid]))
                except (AttributeError, TypeError, ValueError):
                    continue
            else:
                vid = walker_func(value)
                if vid is None:  # refused: spytial machinery, no edge
                    continue
                relations.append(Relation(name, [obj_id, vid]))

        return [atom], relations
