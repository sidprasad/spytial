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
    return {f.name for f in ci.fields if f.is_self_ref}


def _edge_selector(ci: ClassInfo, field_name: str) -> str:
    """Selector for a structural edge over a scalar self-reference.

    When the field can be ``None`` (leaves point to nothing), restrict both
    endpoints to the node type with the documented surgical idiom
    ``left & (T -> T)`` (see docs/selectors.md). The intersection keeps only the
    node→node pairs, excluding the ``(leaf, None)`` tuples the bare relation would
    include — so the orientation never tries to place the ``NoneType`` atoms that
    ``hideAtom`` removes. Otherwise the bare relation name is simpler and names no
    type at all.
    """
    f = ci.get(field_name)
    if f is not None and f.has_none_default:
        cls = ci.cls.__name__
        return "%s & (%s -> %s)" % (field_name, cls, cls)
    return field_name


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
    if field.is_self_ref and field.container in ("list", "tuple", "set", "dict"):
        return [
            Suggestion(
                "orientation",
                {"selector": field.name, "directions": ["below"]},
                "high",
                f"{field.name} holds children of the same type → place below",
                field.name,
            )
        ]
    return []


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
    if field.is_self_ref and field.container is None and field.name not in _SPECIALIZED:
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
    if not field.enum_members:
        return []
    type_name = ci.cls.__name__
    out: List[Suggestion] = []
    for i, member in enumerate(field.enum_members):
        color = _PALETTE[i % len(_PALETTE)]
        selector = "{ x : %s | @:(x.%s) = %s }" % (type_name, field.name, member)
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
    if any(f.is_self_ref and f.has_none_default for f in ci.fields):
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
    if any(f.is_self_ref for f in ci.fields):
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
