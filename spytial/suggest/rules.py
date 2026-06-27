"""Built-in heuristics, pre-registered into the default registry.

Each is an ordinary function registered with :func:`heuristic` — exactly how a
user extends the system. Built-ins live in the 0-99 priority band; a user
heuristic at priority >= 100 supersedes them on a conflicting field.

Governing principle: only suggest a directive that actually changes the default
rendering. (Underscore fields are already non-rendering, so there is no rule for
them.)
"""

from __future__ import annotations

from typing import List

from ._model import ClassInfo, FieldInfo, Suggestion
from .registry import heuristic

# Name vocabularies for the classic structures.
LEFT_RIGHT = {"left", "right"}
NEXT_NAMES = {"next", "nxt", "succ", "successor"}
PREV_NAMES = {"prev", "previous", "pred", "predecessor"}
PARENT_NAMES = {"parent", "par"}
CHILD_CONTAINER_NAMES = {
    "children",
    "kids",
    "child",
    "nodes",
    "items",
    "elements",
    "neighbors",
    "neighbours",
    "adj",
    "edges",
    "successors",
}
_SPECIALIZED = (
    LEFT_RIGHT | NEXT_NAMES | PREV_NAMES | PARENT_NAMES | CHILD_CONTAINER_NAMES
)

# Deterministic default palette for enum coloring. Semantic palettes are the
# job of the (deferred) LLM enrichment layer.
_PALETTE = [
    "steelblue",
    "coral",
    "seagreen",
    "goldenrod",
    "slateblue",
    "firebrick",
    "teal",
    "orchid",
]


def _self_ref_names(ci: ClassInfo) -> set:
    # Private fields are skipped by the relationalizers, so their edges never
    # render — exclude them so no structural rule targets a missing relation.
    return {f.name for f in ci.fields if f.is_self_ref and not f.is_private}


def _edge_selector(ci: ClassInfo, field_name: str) -> str:
    """Selector for a structural edge over a scalar self-reference.

    When the field can be ``None`` (leaves point to nothing), drop the
    ``(source, None)`` tuples with ``left - (univ -> NoneType)`` — so the
    orientation never tries to place the ``NoneType`` atoms that ``hideAtom``
    removes. Subtracting only the ``None`` targets (rather than intersecting with
    a named node type) keeps edges to subtype nodes, which a
    ``& (T -> T)`` intersection would wrongly drop. Otherwise the bare relation
    name is simpler.
    """
    f = ci.get(field_name)
    if f is not None and f.has_none_default:
        return "%s - (univ -> NoneType)" % field_name
    return field_name


# spytial relationalizes a list as a ternary idx(list, index, element); a dict as
# kv(dict, key, value); a set as contains(set, element). So a container field
# reaches the intermediate `list`/`dict` atom, NOT its elements — directives must
# go through these relations. These two are the render-tested CLRS sequence forms.
_LIST_SEQUENCE = (
    "{x,y : idx[object][object] | @num:(x[idx[object]]) < @num:(y[idx[object]])}"
)
_LIST_HIDE = "list + (int - idx[object][object])"


def _children_selector(cls_name: str, field_name: str, container: str) -> str:
    """A (parent, child) edge for a container of child nodes, reaching the actual
    elements through the relationalizer's idx/kv/contains relation rather than
    orienting the intermediate container atom."""
    if container in ("list", "tuple"):
        elems = "%s.idx[int]" % field_name
    elif container == "dict":
        elems = "%s.kv[univ]" % field_name
    else:  # set
        elems = "%s.contains" % field_name
    return "{ p : %s, c : %s | c in p.%s }" % (cls_name, cls_name, elems)


# --------------------------------------------------------------------------- #
# R1 — binary tree (left + right together)
# --------------------------------------------------------------------------- #
@heuristic(scope="class", priority=20)
def binary_tree(ci: ClassInfo) -> List[Suggestion]:
    names = _self_ref_names(ci)
    if not (LEFT_RIGHT <= names):
        return []
    return [
        Suggestion(
            "orientation",
            {"selector": _edge_selector(ci, "left"), "directions": ["below", "left"]},
            "high",
            "left child of the same type → tree edge below-left",
            "left",
        ),
        Suggestion(
            "orientation",
            {"selector": _edge_selector(ci, "right"), "directions": ["below", "right"]},
            "high",
            "right child of the same type → tree edge below-right",
            "right",
        ),
    ]


# --------------------------------------------------------------------------- #
# R3 — container of children (n-ary)
# --------------------------------------------------------------------------- #
@heuristic(scope="field", priority=20)
def child_container(field: FieldInfo, ci: ClassInfo) -> List[Suggestion]:
    if field.is_private or field.is_nested_container:
        return []  # underscore: not relationalized; nested: handled as a matrix note
    if field.is_self_ref and field.container in ("list", "tuple", "set", "dict"):
        selector = _children_selector(ci.cls.__name__, field.name, field.container)
        return [
            Suggestion(
                "orientation",
                {"selector": selector, "directions": ["below"]},
                "high",
                f"{field.name} holds children of the same type → place below",
                field.name,
            )
        ]
    return []


# --------------------------------------------------------------------------- #
# R3b — plain list/tuple of non-node elements (a sequence: stack, queue, array)
# --------------------------------------------------------------------------- #
@heuristic(scope="field", priority=15)
def list_sequence(field: FieldInfo, ci: ClassInfo) -> List[Suggestion]:
    # Order the elements left-to-right by their list index, via the idx relation.
    # Render-tested against the CLRS stacks/queues spec.
    if field.is_private or field.is_self_ref or field.is_nested_container:
        return []
    if field.container not in ("list", "tuple"):
        return []
    return [
        Suggestion(
            "orientation",
            {"selector": _LIST_SEQUENCE, "directions": ["directlyRight"]},
            "high",
            f"{field.name} is a sequence → lay elements out left-to-right by index",
            field.name,
        ),
        Suggestion(
            "hideAtom",
            {"selector": _LIST_HIDE},
            "medium",
            "hide the list scaffold and index integers (keeps the element values)",
            field.name,
            enabled_by_default=False,
        ),
    ]


# --------------------------------------------------------------------------- #
# R4 — linked list (next / prev)
# --------------------------------------------------------------------------- #
@heuristic(scope="class", priority=20)
def linked_list(ci: ClassInfo) -> List[Suggestion]:
    names = _self_ref_names(ci)
    nexts = names & NEXT_NAMES
    prevs = names & PREV_NAMES
    out: List[Suggestion] = []
    for n in sorted(nexts):
        out.append(
            Suggestion(
                "orientation",
                {"selector": _edge_selector(ci, n), "directions": ["right"]},
                "high",
                f"{n} links to the next node → place to the right",
                n,
            )
        )
    for p in sorted(prevs):
        if nexts:
            out.append(
                Suggestion(
                    "hideField",
                    {"field": p},
                    "medium",
                    f"{p} is the reverse of {'/'.join(sorted(nexts))} → hide the back-link",
                    p,
                )
            )
        else:
            out.append(
                Suggestion(
                    "orientation",
                    {"selector": _edge_selector(ci, p), "directions": ["left"]},
                    "high",
                    f"{p} links to the previous node → place to the left",
                    p,
                )
            )
    return out


# --------------------------------------------------------------------------- #
# R5 — parent / back-pointer (context-aware)
# --------------------------------------------------------------------------- #
@heuristic(scope="class", priority=20)
def parent_pointer(ci: ClassInfo) -> List[Suggestion]:
    names = _self_ref_names(ci)
    parents = names & PARENT_NAMES
    if not parents:
        return []
    has_down = bool(names & (LEFT_RIGHT | CHILD_CONTAINER_NAMES | NEXT_NAMES))
    out: List[Suggestion] = []
    for p in sorted(parents):
        hide = Suggestion(
            "hideField",
            {"field": p},
            "medium",
            f"{p} duplicates the child edges → hide the back-pointer",
            p,
        )
        up = Suggestion(
            "orientation",
            {"selector": _edge_selector(ci, p), "directions": ["above"]},
            "medium",
            f"{p} points to the enclosing node → place above",
            p,
        )
        if has_down:
            hide.confidence, hide.enabled_by_default = "high", True
            up.confidence, up.enabled_by_default = "low", False
        else:
            up.confidence, up.enabled_by_default = "high", True
            hide.confidence, hide.enabled_by_default = "low", False
        out.extend([hide, up])
    return out


# --------------------------------------------------------------------------- #
# R2 — generic single self-reference (fallback for un-named patterns)
# --------------------------------------------------------------------------- #
@heuristic(scope="field", priority=10)
def generic_self_ref(field: FieldInfo, ci: ClassInfo) -> List[Suggestion]:
    if (
        field.is_self_ref
        and not field.is_private
        and field.container is None
        and field.name not in _SPECIALIZED
    ):
        return [
            Suggestion(
                "orientation",
                {"selector": _edge_selector(ci, field.name), "directions": ["below"]},
                "high",
                f"{field.name} references the same type → structural edge below",
                field.name,
            )
        ]
    return []


# --------------------------------------------------------------------------- #
# R6 — scalar field → attribute
# --------------------------------------------------------------------------- #
@heuristic(scope="field", priority=10)
def scalar_attribute(field: FieldInfo, ci: ClassInfo) -> List[Suggestion]:
    if field.is_scalar and not field.is_private:
        return [
            Suggestion(
                "attribute",
                {"field": field.name},
                "high",
                f"{field.name} is scalar data → fold into the node",
                field.name,
            )
        ]
    return []


# --------------------------------------------------------------------------- #
# R7 — enum field → atomColor per member
# --------------------------------------------------------------------------- #
@heuristic(scope="field", priority=10)
def enum_color(field: FieldInfo, ci: ClassInfo) -> List[Suggestion]:
    if not field.enum_members or field.is_private:
        return []
    type_name = ci.cls.__name__
    out: List[Suggestion] = []
    for i, member in enumerate(field.enum_members):
        color = _PALETTE[i % len(_PALETTE)]
        # An Enum member relationalizes to an atom whose display label is not the
        # member name, so @:(x.field) won't match it — join through the member's
        # `name` relation: @:(x.field.name) reads the 'RED'/'BLACK' string atom.
        selector = "{ x : %s | @:(x.%s.name) = %s }" % (type_name, field.name, member)
        out.append(
            Suggestion(
                "atomColor",
                {"selector": selector, "value": color},
                "medium",
                f"{field.name} = {member} → {color} (palette is a guess; edit to taste)",
                field.name,
                enabled_by_default=False,
            )
        )
    return out


# --------------------------------------------------------------------------- #
# R8 — hide NoneType atoms when children can be empty
# --------------------------------------------------------------------------- #
@heuristic(scope="class", priority=5)
def hide_none(ci: ClassInfo) -> List[Suggestion]:
    if any(
        f.is_self_ref and not f.is_private and f.has_none_default for f in ci.fields
    ):
        return [
            Suggestion(
                "hideAtom",
                {"selector": "NoneType"},
                "medium",
                "empty children are None → hide NoneType atoms",
                None,
                enabled_by_default=True,
            )
        ]
    return []


# --------------------------------------------------------------------------- #
# R9 — hideDisconnected flag once a structure exists
# --------------------------------------------------------------------------- #
@heuristic(scope="class", priority=1)
def hide_disconnected(ci: ClassInfo) -> List[Suggestion]:
    if any(f.is_self_ref and not f.is_private for f in ci.fields):
        return [
            Suggestion(
                "flag",
                {"name": "hideDisconnected"},
                "low",
                "drop disconnected atoms for a cleaner layout",
                None,
            )
        ]
    return []
