#
# sPyTial Annotation System
#


import yaml
import re
import json
import warnings
import weakref
from dataclasses import dataclass, fields as _dataclass_fields


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
            "optional": ["addEdge", "textStyle"],
        },  # Selector-based group constraint
    ],
}

DIRECTIVE_TYPES = {
    # Legacy 2.x form; desugars to atomStyle (value -> borderStyle.color).
    "atomColor": ["selector", "value"],
    "atomStyle": {
        "required": [],
        "optional": ["selector", "fillStyle", "borderStyle", "textStyle"],
    },
    "size": ["selector", "height", "width"],
    "icon": ["selector", "path", "showLabels"],
    # Legacy 2.x form; desugars to edgeStyle (value -> lineStyle.color,
    # style -> lineStyle.pattern, weight -> lineStyle.weight).
    "edgeColor": {
        "required": ["field", "value"],
        "optional": ["selector", "filter", "style", "weight", "showLabel", "hidden"],
    },
    "edgeStyle": {
        "required": ["field"],
        "optional": ["selector", "filter", "lineStyle", "textStyle", "showLabel", "hidden"],
    },
    "projection": ["sig"],
    "attribute": {"required": ["field"], "optional": ["selector", "filter", "textSize"]},
    "hideField": {"required": ["field"], "optional": ["selector", "filter"]},
    "hideAtom": ["selector"],
    "inferredEdge": {
        "required": ["name", "selector"],
        # color/style/weight are the legacy inline form; they desugar to lineStyle.
        "optional": ["color", "style", "weight", "lineStyle", "textStyle"],
    },
    "tag": {"required": ["toTag", "name", "value"], "optional": ["textSize"]},
    "flag": ["name"],
}

# =============================================
# Style blocks (spytial-core 3.0 style system)
# =============================================
#
# spytial-core 3.0 combined the flat edge/atom styling directives into
# `edgeStyle` / `atomStyle` with nested style blocks. The blocks below are the
# Python-side vocabulary for those YAML blocks: small frozen dataclasses that
# validate at construction and flatten to sparse dicts at registration. Plain
# dicts with the same keys are accepted everywhere and coerced through the same
# dataclass, so there is exactly one validator per block shape.
#
# spytial-core itself silently drops invalid block leaves, so this
# author-time strictness is the only place a typo is ever surfaced.

LINE_PATTERNS = ("solid", "dashed", "dotted")
TEXT_SIZES = ("small", "normal", "large")
GROUP_EDGE_DIRECTIONS = ("none", "togroup", "fromgroup")


def _require_choice(value, choices, what):
    if value is not None and value not in choices:
        raise ValueError(f"{what} must be one of {', '.join(choices)}; got {value!r}")


def _require_positive(value, what):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{what} must be a number greater than 0; got {value!r}")


@dataclass(frozen=True)
class _StyleBlock:
    """Base for style blocks: sparse to_dict() emitting only the fields set."""

    def to_dict(self):
        out = {}
        for f in _dataclass_fields(self):
            value = getattr(self, f.name)
            if value is None:
                continue
            if isinstance(value, _StyleBlock):
                value = value.to_dict()
            out[f.name] = value
        return out


@dataclass(frozen=True)
class LineStyle(_StyleBlock):
    """Styling for a drawn edge line (edgeStyle, inferredEdge, GroupEdge connector).

    All fields optional: color (CSS color), pattern ('solid'|'dashed'|'dotted'),
    weight (number > 0), highlight (CSS color).
    """

    color: str = None
    pattern: str = None
    weight: float = None
    highlight: str = None

    def __post_init__(self):
        _require_choice(self.pattern, LINE_PATTERNS, "LineStyle.pattern")
        _require_positive(self.weight, "LineStyle.weight")


@dataclass(frozen=True)
class TextStyle(_StyleBlock):
    """Styling for a label (edge labels, atom labels, group labels).

    All fields optional: size ('small'|'normal'|'large'), color (CSS color).
    """

    size: str = None
    color: str = None

    def __post_init__(self):
        _require_choice(self.size, TEXT_SIZES, "TextStyle.size")


@dataclass(frozen=True)
class BorderStyle(_StyleBlock):
    """Styling for an atom's border: color (CSS color), width (number > 0)."""

    color: str = None
    width: float = None

    def __post_init__(self):
        _require_positive(self.width, "BorderStyle.width")


@dataclass(frozen=True)
class FillStyle(_StyleBlock):
    """Styling for an atom's interior fill: color (CSS color)."""

    color: str = None


@dataclass(frozen=True)
class GroupEdge(_StyleBlock):
    """Rich form of a selector-group's ``addEdge``: direction plus connector styling.

    ``points`` ('none'|'togroup'|'fromgroup') says which way the connector
    between the group's key and the group points — the same key the YAML block
    uses; ``lineStyle`` / ``textStyle`` style the connector edge and its label.
    Serializes to ``addEdge: {points: ..., lineStyle: ..., textStyle: ...}``.
    """

    points: str = "none"
    lineStyle: LineStyle = None
    textStyle: TextStyle = None

    def __post_init__(self):
        _require_choice(self.points, GROUP_EDGE_DIRECTIONS, "GroupEdge.points")
        if isinstance(self.lineStyle, dict):
            object.__setattr__(self, "lineStyle", LineStyle(**self.lineStyle))
        if isinstance(self.textStyle, dict):
            object.__setattr__(self, "textStyle", TextStyle(**self.textStyle))


# Which kwargs of which annotation types are style blocks, and their shape.
_STYLE_BLOCK_FIELDS = {
    "edgeStyle": {"lineStyle": LineStyle, "textStyle": TextStyle},
    "atomStyle": {
        "fillStyle": FillStyle,
        "borderStyle": BorderStyle,
        "textStyle": TextStyle,
    },
    "inferredEdge": {"lineStyle": LineStyle, "textStyle": TextStyle},
    "group": {"addEdge": GroupEdge, "textStyle": TextStyle},
}


def _coerce_block(block_cls, value, context):
    """Coerce a style-block value (instance or dict) to its sparse dict form."""
    if isinstance(value, block_cls):
        return value.to_dict()
    if isinstance(value, dict):
        try:
            return block_cls(**value).to_dict()
        except TypeError:
            valid = ", ".join(f.name for f in _dataclass_fields(block_cls))
            unknown = [k for k in value if k not in {f.name for f in _dataclass_fields(block_cls)}]
            raise ValueError(
                f"Unknown key(s) {unknown} in {context}; valid keys: {valid}"
            ) from None
    raise ValueError(
        f"{context} must be a {block_cls.__name__} or a dict; got {type(value).__name__}"
    )


def _coerce_style_blocks(annotation_type, kwargs):
    """Return a fresh kwargs dict with style blocks flattened to sparse dicts.

    Always copies (registries must never alias caller-held dicts) and validates
    block payloads and scalar enums (textSize, bare addEdge directions).
    """
    block_fields = _STYLE_BLOCK_FIELDS.get(annotation_type, {})
    out = {}
    for key, value in kwargs.items():
        block_cls = block_fields.get(key)
        if block_cls is not None and value is not None:
            if annotation_type == "group" and key == "addEdge":
                # Bare direction string / legacy bool passes through untouched.
                if isinstance(value, (str, bool)):
                    if isinstance(value, str):
                        _require_choice(value, GROUP_EDGE_DIRECTIONS, "group.addEdge")
                    out[key] = value
                    continue
            value = _coerce_block(block_cls, value, f"{annotation_type}.{key}")
        out[key] = value
    if annotation_type in ("attribute", "tag"):
        _require_choice(out.get("textSize"), TEXT_SIZES, f"{annotation_type}.textSize")
    return out


def _drop_invalid_legacy(value, ok, what):
    """Legacy desugar mirrors core's lenience: drop bad values (visibly), don't raise."""
    if value is None or ok(value):
        return value
    warnings.warn(
        f"Ignoring invalid {what} {value!r}; the rendered output falls back to the default.",
        UserWarning,
        stacklevel=4,
    )
    return None


def _legacy_line_style(color=None, style=None, weight=None):
    """Build a lineStyle dict from legacy flat keys, normalizing like core does."""
    pattern = None
    if style is not None:
        normalized = style.strip().lower() if isinstance(style, str) else style
        pattern = _drop_invalid_legacy(
            normalized, lambda v: v in LINE_PATTERNS, "edge style/pattern"
        )
    weight = _drop_invalid_legacy(
        weight,
        lambda v: not isinstance(v, bool) and isinstance(v, (int, float)) and v > 0,
        "edge weight",
    )
    return LineStyle(color=color, pattern=pattern, weight=weight).to_dict()


def _desugar_legacy_style(annotation_type, kwargs, *, stacklevel=3):
    """Rewrite deprecated 2.x style forms into their 3.0 equivalents.

    Returns a (annotation_type, kwargs) pair; non-legacy input passes through
    unchanged, so the rewrite is idempotent. Validates the *legacy* schema
    before rewriting so legacy authoring errors keep their legacy messages.
    """
    if annotation_type == "edgeColor":
        validate_fields("edgeColor", kwargs, DIRECTIVE_TYPES["edgeColor"])
        warnings.warn(
            "edgeColor is deprecated as of spytial-core 3.0; use edgeStyle with "
            "lineStyle=LineStyle(color=...) instead (this call is rewritten to edgeStyle).",
            DeprecationWarning,
            stacklevel=stacklevel,
        )
        new_kwargs = {"field": kwargs["field"]}
        for key in ("selector", "filter"):
            if kwargs.get(key) is not None:
                new_kwargs[key] = kwargs[key]
        line_style = _legacy_line_style(
            color=kwargs["value"], style=kwargs.get("style"), weight=kwargs.get("weight")
        )
        if line_style:
            new_kwargs["lineStyle"] = line_style
        for key in ("showLabel", "hidden"):
            if kwargs.get(key) is not None:
                new_kwargs[key] = kwargs[key]
        return "edgeStyle", new_kwargs

    if annotation_type == "atomColor":
        validate_fields("atomColor", kwargs, DIRECTIVE_TYPES["atomColor"])
        warnings.warn(
            "atomColor is deprecated as of spytial-core 3.0; use atomStyle with "
            "borderStyle=BorderStyle(color=...) instead (this call is rewritten to "
            "atomStyle; the legacy value colored the border, not the fill).",
            DeprecationWarning,
            stacklevel=stacklevel,
        )
        return "atomStyle", {
            "selector": kwargs["selector"],
            "borderStyle": BorderStyle(color=kwargs["value"]).to_dict(),
        }

    if annotation_type == "inferredEdge" and any(
        kwargs.get(key) is not None for key in ("color", "style", "weight")
    ):
        if kwargs.get("lineStyle") is not None:
            raise ValueError(
                "inferredEdge got both the deprecated inline color/style/weight "
                "and a lineStyle block; use lineStyle only."
            )
        validate_fields("inferredEdge", kwargs, DIRECTIVE_TYPES["inferredEdge"])
        warnings.warn(
            "inferredEdge's inline color/style/weight are deprecated as of "
            "spytial-core 3.0; use lineStyle=LineStyle(...) instead.",
            DeprecationWarning,
            stacklevel=stacklevel,
        )
        new_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key not in ("color", "style", "weight") and value is not None
        }
        line_style = _legacy_line_style(
            color=kwargs.get("color"), style=kwargs.get("style"), weight=kwargs.get("weight")
        )
        if line_style:
            new_kwargs["lineStyle"] = line_style
        return "inferredEdge", new_kwargs

    return annotation_type, kwargs


# Object-level annotation storage attribute name
OBJECT_ANNOTATIONS_ATTR = "__spytial_object_annotations__"

# Object ID storage attribute name (for self-reference)
OBJECT_ID_ATTR = "__spytial_object_id__"

_MISSING = object()


class _IdentityKeyedRegistry:
    """A process-global map keyed by object identity, safe against id reuse.

    Some built-in values (``list``, ``dict``, ``tuple``) can store neither a
    marker attribute nor a weak reference, so any per-object state for them must
    live in a module-global map. Keying that map by raw ``id(obj)`` is unsafe:
    once the object is garbage-collected its id can be reused by a brand-new
    object, which would then silently inherit the dead object's entry.

    Each entry therefore retains a *reference* to the object it belongs to:

    * weak-referenceable objects (``set``, custom instances) get a ``weakref``
      whose finalizer evicts the entry the instant the object dies — so its id
      is never simultaneously freed and still mapped;
    * objects that support neither attribute storage nor weakref (``list``,
      ``dict``, ``tuple``) get a *strong* reference, which pins the id for as
      long as the entry lives, so the id cannot be reused while it is mapped.

    Lookups additionally verify object identity, so even under a reused id no
    object can ever read another object's value. Keys are ``id(obj)`` ints, so
    unhashable objects (lists, dicts) are fine.
    """

    def __init__(self):
        # id(obj) -> (holder, is_weak, value); holder is a weakref or the obj.
        self._entries = {}

    def _live_object(self, entry):
        holder, is_weak, _value = entry
        return holder() if is_weak else holder

    def _make_evictor(self, oid):
        def _evict(dead_ref):
            entry = self._entries.get(oid)
            # Only drop the entry if it still belongs to the object that died,
            # never a newer entry that reused the id.
            if entry is not None and entry[0] is dead_ref:
                del self._entries[oid]

        return _evict

    def _store(self, obj, value):
        oid = id(obj)
        try:
            holder = weakref.ref(obj, self._make_evictor(oid))
            is_weak = True
        except TypeError:
            # Cannot weak-reference this type (list/dict/tuple/...). Hold a
            # strong reference: it pins the id so reuse is impossible.
            holder = obj
            is_weak = False
        self._entries[oid] = (holder, is_weak, value)

    def get(self, obj, default=None):
        entry = self._entries.get(id(obj))
        if entry is None:
            return default
        if self._live_object(entry) is obj:
            return entry[2]
        # Stale: a reused id (or a dead weakref not yet finalized). Evict.
        self._entries.pop(id(obj), None)
        return default

    def __contains__(self, obj):
        return self.get(obj, _MISSING) is not _MISSING

    def get_or_create(self, obj, factory):
        existing = self.get(obj, _MISSING)
        if existing is not _MISSING:
            return existing
        value = factory()
        self._store(obj, value)
        return value

    def set(self, obj, value):
        self._store(obj, value)

    def clear(self):
        self._entries.clear()


# Global registry for objects that can't store annotations directly
_OBJECT_ANNOTATION_REGISTRY = _IdentityKeyedRegistry()

# Global registry for object IDs (for objects that can't store attributes)
_OBJECT_ID_REGISTRY = _IdentityKeyedRegistry()

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

    def __init__(self, *, selector: str, directions: list, hold: str = "always"):
        if hold not in ("always", "never"):
            raise ValueError(f"hold must be 'always' or 'never', got {hold!r}")
        kwargs = dict(selector=selector, directions=directions)
        if hold == "never":
            kwargs["hold"] = hold
        super().__init__(**kwargs)


class Cyclic(SpytialAnnotation):
    """
    Cyclic constraint for circular layouts.

    Usage:
        NodeRing = Annotated[list[Node], Cyclic(selector='items', direction='clockwise')]
    """

    _annotation_type = "cyclic"
    _is_constraint = True

    def __init__(self, *, selector: str, direction: str, hold: str = "always"):
        if hold not in ("always", "never"):
            raise ValueError(f"hold must be 'always' or 'never', got {hold!r}")
        kwargs = dict(selector=selector, direction=direction)
        if hold == "never":
            kwargs["hold"] = hold
        super().__init__(**kwargs)


class Align(SpytialAnnotation):
    """
    Alignment constraint.

    Usage:
        AlignedList = Annotated[list[int], Align(selector='items', direction='left')]
    """

    _annotation_type = "align"
    _is_constraint = True

    def __init__(self, *, selector: str, direction: str, hold: str = "always"):
        if hold not in ("always", "never"):
            raise ValueError(f"hold must be 'always' or 'never', got {hold!r}")
        kwargs = dict(selector=selector, direction=direction)
        if hold == "never":
            kwargs["hold"] = hold
        super().__init__(**kwargs)


class Group(SpytialAnnotation):
    """
    Grouping constraint.

    Usage (field-based):
        Tree = Annotated[TreeNode, Group(field='children', groupOn=0, addToGroup=1)]

    Usage (selector-based):
        Grouped = Annotated[MyType, Group(selector='items', name='mygroup')]

    For a selector-based group, ``addEdge`` controls the edge drawn between the
    group's key and the group itself. For a binary selector with tuples
    ``(a, b), (a, c), (a, d)`` the group is keyed by ``a`` and contains
    ``{b, c, d}``:

        - ``'none'``      -> draw nothing (default)
        - ``'togroup'``   -> edge from the key into the group (a -> group)
        - ``'fromgroup'`` -> edge from the group back to the key (group -> a)

    Legacy ``addEdge=True`` is still accepted and maps to ``'togroup'``.

        Grouped = Annotated[MyType, Group(selector='...', name='g', addEdge='togroup')]

    To also style the connector, pass a ``GroupEdge`` (spytial-core 3.0), and
    style the group's own label with a top-level ``textStyle``:

        Grouped = Annotated[MyType, Group(selector='...', name='g',
            addEdge=GroupEdge(points='togroup', lineStyle=LineStyle(pattern='dashed')),
            textStyle=TextStyle(color='navy'))]
    """

    _annotation_type = "group"
    _is_constraint = True

    def __init__(self, *, hold: str = "always", **kwargs):
        if hold not in ("always", "never"):
            raise ValueError(f"hold must be 'always' or 'never', got {hold!r}")
        if hold == "never":
            kwargs["hold"] = hold
        # Accept either field-based or selector-based parameters
        super().__init__(**_coerce_style_blocks("group", kwargs))


# =============================================
# Directive Annotation Classes
# =============================================


class AtomStyle(SpytialAnnotation):
    """
    Atom style directive (spytial-core 3.0).

    Styles an atom's border, interior fill, and label independently.

    Usage:
        Styled = Annotated[list[int], AtomStyle(selector='self', borderStyle=BorderStyle(color='blue'))]
        Filled = Annotated[Tree, AtomStyle(selector='Node', fillStyle=FillStyle(color='#eef6ff'),
                                           textStyle=TextStyle(size='large'))]
    """

    _annotation_type = "atomStyle"
    _is_constraint = False

    def __init__(
        self,
        *,
        selector: str = None,
        fillStyle=None,
        borderStyle=None,
        textStyle=None,
    ):
        kwargs = {}
        if selector is not None:
            kwargs["selector"] = selector
        if fillStyle is not None:
            kwargs["fillStyle"] = fillStyle
        if borderStyle is not None:
            kwargs["borderStyle"] = borderStyle
        if textStyle is not None:
            kwargs["textStyle"] = textStyle
        super().__init__(**_coerce_style_blocks("atomStyle", kwargs))


class AtomColor(AtomStyle):
    """
    Deprecated legacy atom color directive; use AtomStyle instead.

    Rewrites to an atomStyle entry with ``value`` as the border color (the
    legacy directive colored the border, not the fill).
    """

    def __init__(self, *, selector: str, value: str):
        _, kwargs = _desugar_legacy_style(
            "atomColor", {"selector": selector, "value": value}, stacklevel=3
        )
        super().__init__(**kwargs)


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


class EdgeStyle(SpytialAnnotation):
    """
    Edge style directive (spytial-core 3.0).

    Styles the edges of a field/relation: the drawn line via ``lineStyle``,
    the edge's label via ``textStyle``, plus the showLabel/hidden flags.

    Usage:
        StyledEdges = Annotated[Tree, EdgeStyle(field='children',
                                                lineStyle=LineStyle(color='red', pattern='dashed'))]
        LabeledEdges = Annotated[Tree, EdgeStyle(field='Uses',
                                                 lineStyle=LineStyle(color='#d10000', weight=3),
                                                 textStyle=TextStyle(size='small'), showLabel=True)]
        HiddenEdges = Annotated[Tree, EdgeStyle(field='internal', hidden=True)]
    """

    _annotation_type = "edgeStyle"
    _is_constraint = False

    def __init__(
        self,
        *,
        field: str,
        selector: str = None,
        filter: str = None,
        lineStyle=None,
        textStyle=None,
        showLabel: bool = None,
        hidden: bool = None,
    ):
        kwargs = {"field": field}
        if selector is not None:
            kwargs["selector"] = selector
        if filter is not None:
            kwargs["filter"] = filter
        if lineStyle is not None:
            kwargs["lineStyle"] = lineStyle
        if textStyle is not None:
            kwargs["textStyle"] = textStyle
        if showLabel is not None:
            kwargs["showLabel"] = showLabel
        if hidden is not None:
            kwargs["hidden"] = hidden
        super().__init__(**_coerce_style_blocks("edgeStyle", kwargs))


class EdgeColor(EdgeStyle):
    """
    Deprecated legacy edge color directive; use EdgeStyle instead.

    Rewrites to an edgeStyle entry: ``value`` -> lineStyle.color,
    ``style`` -> lineStyle.pattern, ``weight`` -> lineStyle.weight.
    """

    def __init__(
        self,
        *,
        field: str,
        value: str,
        selector: str = None,
        filter: str = None,
        style: str = None,
        weight: int = None,
        showLabel: bool = None,
        hidden: bool = None,
    ):
        legacy = {"field": field, "value": value}
        if selector is not None:
            legacy["selector"] = selector
        if filter is not None:
            legacy["filter"] = filter
        if style is not None:
            legacy["style"] = style
        if weight is not None:
            legacy["weight"] = weight
        if showLabel is not None:
            legacy["showLabel"] = showLabel
        if hidden is not None:
            legacy["hidden"] = hidden
        _, kwargs = _desugar_legacy_style("edgeColor", legacy, stacklevel=3)
        super().__init__(**kwargs)


class HideField(SpytialAnnotation):
    """
    Hide field directive.

    Usage:
        CleanView = Annotated[MyClass, HideField(field='_private')]
        Filtered = Annotated[MyClass, HideField(field='debug', filter='debug & Production')]
    """

    _annotation_type = "hideField"
    _is_constraint = False

    def __init__(self, *, field: str, selector: str = None, filter: str = None):
        kwargs = {"field": field}
        if selector is not None:
            kwargs["selector"] = selector
        if filter is not None:
            kwargs["filter"] = filter
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
        Filtered = Annotated[MyType, Attribute(field='status', filter='status & Active')]
    """

    _annotation_type = "attribute"
    _is_constraint = False

    def __init__(
        self,
        *,
        field: str,
        selector: str = None,
        filter: str = None,
        textSize: str = None,
    ):
        kwargs = {"field": field}
        if selector is not None:
            kwargs["selector"] = selector
        if filter is not None:
            kwargs["filter"] = filter
        if textSize is not None:
            kwargs["textSize"] = textSize
        super().__init__(**_coerce_style_blocks("attribute", kwargs))


class InferredEdge(SpytialAnnotation):
    """
    Inferred edge directive.

    Styling uses the shared lineStyle/textStyle blocks (spytial-core 3.0); the
    inline color/style/weight keys are deprecated and rewritten into lineStyle.

    Usage:
        WithEdges = Annotated[Graph, InferredEdge(name='connection', selector='nodes')]
        StyledEdges = Annotated[Graph, InferredEdge(name='ancestor', selector='^parent',
                                                    lineStyle=LineStyle(color='gray', pattern='dotted'))]
    """

    _annotation_type = "inferredEdge"
    _is_constraint = False

    def __init__(
        self,
        *,
        name: str,
        selector: str,
        color: str = None,
        style: str = None,
        weight: int = None,
        lineStyle=None,
        textStyle=None,
    ):
        kwargs = {"name": name, "selector": selector}
        if color is not None:
            kwargs["color"] = color
        if style is not None:
            kwargs["style"] = style
        if weight is not None:
            kwargs["weight"] = weight
        if lineStyle is not None:
            kwargs["lineStyle"] = lineStyle
        if textStyle is not None:
            kwargs["textStyle"] = textStyle
        _, kwargs = _desugar_legacy_style("inferredEdge", kwargs, stacklevel=3)
        super().__init__(**_coerce_style_blocks("inferredEdge", kwargs))


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


class Tag(SpytialAnnotation):
    """
    Tag directive for adding computed attributes to nodes.

    Unlike 'attribute', this does NOT remove edges - it adds computed
    attribute values to nodes based on selector evaluation.

    Usage:
        # Simple binary tag - displays as "age: 25"
        Tagged = Annotated[MyType, Tag(toTag='Person', name='age', value='age')]

        # Ternary selector - displays as "score[Math]: 95"
        Graded = Annotated[MyType, Tag(toTag='Student', name='score', value='grades')]
    """

    _annotation_type = "tag"
    _is_constraint = False

    def __init__(self, *, toTag: str, name: str, value: str, textSize: str = None):
        kwargs = {"toTag": toTag, "name": name, "value": value}
        if textSize is not None:
            kwargs["textSize"] = textSize
        super().__init__(**_coerce_style_blocks("tag", kwargs))


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
    # Rewrite deprecated 2.x style forms and flatten style blocks.
    annotation_type, kwargs = _desugar_legacy_style(
        annotation_type, kwargs, stacklevel=3
    )
    kwargs = _coerce_style_blocks(annotation_type, kwargs)

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
    Reset the global object-level state. Useful for testing or when you need
    deterministic object ID generation across multiple runs.

    Clears both global registries — object IDs and object annotations — for the
    built-in values that can't store that state on themselves.

    Warning: This will clear all existing object ID mappings and any
    annotations recorded for un-attributable objects, so existing selectors
    that depend on previous object IDs may no longer work.
    """
    global _OBJECT_ID_COUNTER
    _OBJECT_ID_COUNTER = 0
    _OBJECT_ID_REGISTRY.clear()
    _OBJECT_ANNOTATION_REGISTRY.clear()

    # Note: object ID / annotation *attributes* stored on attributable objects
    # are left intact; we can't enumerate them, so this clears the global
    # registries only.


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
    existing = _OBJECT_ID_REGISTRY.get(obj)
    if existing is not None:
        return existing

    # Create new unique ID
    _OBJECT_ID_COUNTER += 1
    unique_id = f"obj_{_OBJECT_ID_COUNTER}"

    # Store the ID
    try:
        setattr(obj, OBJECT_ID_ATTR, unique_id)
    except (AttributeError, TypeError):
        # Object doesn't support attribute assignment, use global registry
        _OBJECT_ID_REGISTRY.set(obj, unique_id)

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
        # Rewrite deprecated 2.x style forms once, at the authoring site, so the
        # deprecation warning points at the user's line and fires once even if
        # the returned decorator is applied to many targets.
        effective_type, kwargs = _desugar_legacy_style(
            constraint_type, kwargs, stacklevel=2
        )
        kwargs = _coerce_style_blocks(effective_type, kwargs)

        def unified_decorator(target):
            # Check if target is a class (type) or an object instance
            if isinstance(target, type):
                # Class decoration (original behavior)
                # Check if this CLASS (not inherited) has its own registry
                if "__spytial_registry__" not in target.__dict__:
                    # Create a new registry for this class
                    target.__spytial_registry__ = {"constraints": [], "directives": []}

                # Determine if it's a constraint or directive
                if effective_type in CONSTRAINT_TYPES:
                    # Validate fields for constraints
                    validate_fields(
                        effective_type, kwargs, CONSTRAINT_TYPES[effective_type]
                    )
                    entry = {effective_type: kwargs}
                    target.__spytial_registry__["constraints"].append(entry)
                elif effective_type in DIRECTIVE_TYPES:
                    # Validate fields for directives
                    validate_fields(
                        effective_type, kwargs, DIRECTIVE_TYPES[effective_type]
                    )

                    # Special handling for flag directives - store as scalar
                    if effective_type == "flag" and "name" in kwargs:
                        entry = {effective_type: kwargs["name"]}
                    else:
                        entry = {effective_type: kwargs}

                    target.__spytial_registry__["directives"].append(entry)
                else:
                    raise ValueError(
                        f"Unknown type '{effective_type}' for sPyTial decorator."
                    )

                return target
            else:
                # Object annotation (new ergonomic behavior)
                return _annotate_object(target, effective_type, **kwargs)

        return unified_decorator

    return decorator


# Create individual decorator functions for each constraint and directive type
orientation = _create_decorator("orientation")
cyclic = _create_decorator("cyclic")
align = _create_decorator("align")
group = _create_decorator("group")
atomColor = _create_decorator("atomColor")  # deprecated: rewrites to atomStyle
atomStyle = _create_decorator("atomStyle")
size = _create_decorator("size")
icon = _create_decorator("icon")
edgeColor = _create_decorator("edgeColor")  # deprecated: rewrites to edgeStyle
edgeStyle = _create_decorator("edgeStyle")
projection = _create_decorator("projection")
attribute = _create_decorator("attribute")
hideField = _create_decorator("hideField")
hideAtom = _create_decorator("hideAtom")
inferredEdge = _create_decorator("inferredEdge")
tag = _create_decorator("tag")
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
        # Use the identity-keyed global registry instead.
        return _OBJECT_ANNOTATION_REGISTRY.get_or_create(
            obj, lambda: {"constraints": [], "directives": []}
        )


def _annotate_object(obj, annotation_type, **kwargs):
    """
    Apply an annotation to a specific object instance.
    :param obj: The object to annotate.
    :param annotation_type: The type of annotation (e.g., 'orientation', 'cyclic').
    :param kwargs: The annotation parameters.
    :return: The annotated object (for chaining).
    """
    # Rewrite deprecated 2.x style forms and flatten style blocks. Idempotent,
    # so the decorator path (already desugared) doesn't warn twice.
    annotation_type, kwargs = _desugar_legacy_style(
        annotation_type, kwargs, stacklevel=4
    )
    kwargs = _coerce_style_blocks(annotation_type, kwargs)

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
    """Apply atomColor annotation to a specific object (deprecated; use annotate_atomStyle)."""
    return _annotate_object(obj, "atomColor", **kwargs)


def annotate_atomStyle(obj, **kwargs):
    """Apply atomStyle annotation to a specific object."""
    return _annotate_object(obj, "atomStyle", **kwargs)


def annotate_size(obj, **kwargs):
    """Apply size annotation to a specific object."""
    return _annotate_object(obj, "size", **kwargs)


def annotate_icon(obj, **kwargs):
    """Apply icon annotation to a specific object."""
    return _annotate_object(obj, "icon", **kwargs)


def annotate_edgeColor(obj, **kwargs):
    """Apply edgeColor annotation to a specific object (deprecated; use annotate_edgeStyle)."""
    return _annotate_object(obj, "edgeColor", **kwargs)


def annotate_edgeStyle(obj, **kwargs):
    """Apply edgeStyle annotation to a specific object."""
    return _annotate_object(obj, "edgeStyle", **kwargs)


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


def annotate_tag(obj, **kwargs):
    """Apply tag annotation to a specific object."""
    return _annotate_object(obj, "tag", **kwargs)


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


# Match keys per style directive: two entries with identical match keys style
# the same edges/atoms, so differing leaf values are a guaranteed collision.
_STYLE_MATCH_KEYS = {
    "edgeStyle": ("field", "selector", "filter"),
    "atomStyle": ("selector",),
}


def _iter_style_leaves(payload, prefix=()):
    for key, value in payload.items():
        if isinstance(value, dict):
            yield from _iter_style_leaves(value, prefix + (key,))
        else:
            yield prefix + (key,), value


def _warn_style_conflicts(directives):
    """Advisory for guaranteed spytial-core 3.0 StyleCollisionErrors.

    Core 3.0 hard-errors when two style rules set the same property of the
    same edge/atom to different values (2.x silently first-won). Python can't
    evaluate selectors, so this only flags the syntactically certain case:
    identical match keys, same leaf, different values. Everything else is
    caught by core at render time.
    """
    seen = {}
    for entry in directives:
        if not isinstance(entry, dict):
            continue
        for directive_type, payload in entry.items():
            match_fields = _STYLE_MATCH_KEYS.get(directive_type)
            if match_fields is None or not isinstance(payload, dict):
                continue
            match_key = tuple(payload.get(field) for field in match_fields)
            style_payload = {
                key: value
                for key, value in payload.items()
                if key not in match_fields
            }
            for leaf, value in _iter_style_leaves(style_payload):
                key = (directive_type, match_key, leaf)
                previous = seen.setdefault(key, value)
                if previous != value:
                    where = ", ".join(
                        f"{f}={v!r}" for f, v in zip(match_fields, match_key) if v is not None
                    )
                    warnings.warn(
                        f"Conflicting {directive_type} rules ({where or 'match-all'}): "
                        f"'{'.'.join(leaf)}' is set to both {previous!r} and {value!r}. "
                        "spytial-core 3.0 raises a StyleCollisionError for this at "
                        "render time — set each style property in exactly one rule.",
                        UserWarning,
                        stacklevel=3,
                    )
    return directives


def _deduplicate_entries(entries):
    """
    Remove duplicate entries while preserving order. Entries can be dicts
    (e.g., {"orientation": {...}}) or scalar values (e.g., flag name).
    We use a JSON-stable canonicalization for dicts and fallback to repr.
    """
    seen = set()
    unique = []
    for entry in entries:
        try:
            key = json.dumps(entry, sort_keys=True, default=str)
        except Exception:
            key = repr(entry)
        if key not in seen:
            seen.add(key)
            unique.append(entry)
    return unique


def collect_decorators(obj, type_hint=None):
    """
    Collect all decorators applied to the class of the given object,
    as well as any annotations applied directly to the object instance,
    and any annotations registered for matching type aliases.
    Respects inheritance control flags (dont_inherit_constraints, dont_inherit_directives).
    :param obj: The object whose class decorators and object annotations should be collected.
    :param type_hint: Optional type hint to look up type alias annotations.
    :return: A combined dictionary of constraints and directives (deduplicated).
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
    object_registry = _OBJECT_ANNOTATION_REGISTRY.get(obj)
    if object_registry is not None:
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

    # Deduplicate entries to avoid excessive redundant YAML rules
    combined_registry["constraints"] = _deduplicate_entries(
        combined_registry["constraints"]
    )
    combined_registry["directives"] = _deduplicate_entries(
        combined_registry["directives"]
    )

    # Surface guaranteed 3.0 style collisions early (identical rules already
    # deduped above, so anything flagged here is a genuine disagreement).
    _warn_style_conflicts(combined_registry["directives"])

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
