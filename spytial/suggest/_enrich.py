"""Optional LLM *shape* enrichment for ``spytial.suggest`` (the ``[suggest-llm]``
extra).

Dormant unless you call ``suggest(..., enrich=...)``. This tier is **schema-level**:
it reasons over the class's structural fields, not a data instance, so it needs no
datum — only the model call.

What it does: suggest the *spatial shape* of a structure — how each structural
field orients in space (``orientation`` directions), whether a self-reference forms
a ring (``cyclic``), and whether a collection's elements should be boxed together
(``group``). This is exactly where the deterministic rules are weakest: they key off
a fixed name vocabulary (left/right/next/prev/parent/children) and fall back to a
flat ``below`` for anything else. A model reads ``escalation`` / ``downstream`` /
``reportsTo`` and proposes a direction that matches the meaning.

What this tier deliberately does **not** do: write a selector. Spytial selectors are
Alloy/Forge relational expressions, and validating one requires a datum the schema
doesn't have. So here the model only chooses the *shape*; spytial supplies the
selector from the field, reusing the same render-verified forms the deterministic
rules emit. That keeps the tier safe by construction at the type level. Authoring
*selectors* — for the relational cases this shape tier can't express — is the
companion tier in :mod:`spytial.suggest._enrich_from_examples`, which activates when
example instances are available and validates every candidate by evaluating it over
each of them.

Enriched rows are tagged ``source="llm"``, stay off by default (you pick), and every
failure path — an unresolvable provider, a malformed model response — degrades to the
static draft with a note. Enrichment can never crash ``suggest()``. The provider (how
to reach a model) is chosen by the caller via ``enrich=`` and resolved in
:mod:`spytial.suggest.providers`; this module just calls ``provider(prompt, schema=)``.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional

from ._model import ClassInfo, SpecDraft, Suggestion
from .rules import _children_selector, _edge_selector

# Render-verified spatial vocabularies the model picks from. Validated in Python
# (not just declared in the schema) so a provider that ignores nested enums can't
# slip an unknown token into a directive.
_ORIENT_DIRS = ("below", "above", "left", "right", "directlyRight", "directlyLeft")
_CYCLIC_DIRS = ("clockwise", "counterclockwise")
_CONTAINERS = ("list", "tuple", "set", "dict")

_SHAPE_SCHEMA = {
    "type": "object",
    "properties": {
        "shapes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "constraint": {
                        "type": "string",
                        "enum": ["orientation", "cyclic", "group", "none"],
                    },
                    "directions": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(_ORIENT_DIRS)},
                    },
                    "direction": {"type": "string", "enum": list(_CYCLIC_DIRS)},
                    "why": {"type": "string"},
                },
                "required": ["field", "constraint", "why"],
            },
        }
    },
    "required": ["shapes"],
}

_SHAPE_PROMPT = """\
You suggest the spatial SHAPE of a data structure for a diagram — how each
structural field lays out. You do NOT write selectors or code; you only pick a shape
per field from a fixed vocabulary, and spytial draws the selector itself.

For each structural field choose exactly one constraint:
- orientation: the field is a directional edge. Give 1-2 directions from
  [below, above, left, right, directlyRight, directlyLeft]. A tree child -> below;
  a forward/"next" link -> right; a parent/back link -> above.
- cyclic: the field forms a ring or cycle (circular list, ring buffer). Give a
  direction (clockwise / counterclockwise). Only for single-pointer fields.
- group: the field is a collection whose elements should be boxed together. Only
  for container fields (list/tuple/set/dict).
- none: no clear spatial meaning. This is the preferred answer when unsure.

Read the field NAME for meaning: reportsTo/manager/escalation -> above;
downstream/child -> below or right; sibling/peer -> right. When in doubt, choose
none — suggest less, not more.

Class: {cls}
Structural fields:
{fields}

Return one entry per field listed above."""


def _structural_fields(ci: ClassInfo) -> List:
    """Non-private self-referential fields — the structural edges shape applies to."""
    return [f for f in ci.fields if f.is_self_ref and not f.is_private]


def enrich_draft(
    draft: SpecDraft,
    class_info: ClassInfo,
    *,
    provider: Any,
    examples: Optional[List[Any]] = None,
) -> SpecDraft:
    """Augment a :class:`SpecDraft` with model-suggested spatial shape and selectors.

    ``provider`` is an :class:`~spytial.suggest.EnrichProvider` (already resolved from
    the caller's ``enrich=`` spec). The schema-level *shape* tier always runs. When
    ``examples`` (a list of instances) is provided, the *selector* tier
    (:mod:`._enrich_from_examples`) also runs — the model authors selectors that are
    validated by evaluation over every example. Returns the same draft, mutated in
    place. Any failure leaves the deterministic suggestions untouched and records a
    note in ``draft.notes`` — enrichment never raises.
    """
    try:
        _enrich_shape(draft, class_info, provider)
    except Exception as exc:  # noqa: BLE001 — never crash suggest() on enrichment
        draft.notes.append(f"enrich: shape enrichment skipped ({exc}).")

    # Tier-2: model-authored selectors, validated by evaluation over example
    # instances. Runs only with examples to evaluate against; otherwise note (when
    # there's structure it could have helped) and stay shape-only.
    if examples:
        try:
            from . import _enrich_from_examples

            _enrich_from_examples.enrich_from_examples(
                draft, class_info, provider, examples
            )
        except Exception as exc:  # noqa: BLE001 — never crash suggest() on enrichment
            draft.notes.append(f"enrich: selector tier skipped ({exc}).")
    elif _structural_fields(class_info):
        draft.notes.append(
            "enrich: pass examples — suggest(obj, enrich=...) or "
            "suggest(Cls, examples=[obj], enrich=...) — to also get model-authored "
            "selectors validated against your data."
        )
    return draft


def _enrich_shape(draft: SpecDraft, ci: ClassInfo, provider) -> None:
    fields = _structural_fields(ci)
    if not fields:
        return  # nothing structural to shape; don't spend a model call

    shapes = _ask_shapes(provider, ci, fields)
    _apply_shapes(draft, ci, fields, shapes)


def _ask_shapes(provider, ci: ClassInfo, fields: List) -> List[dict]:
    """Prompt the provider for a shape per structural field; return the raw list."""
    lines = []
    for f in fields:
        kind = f.container if f.container else "single pointer"
        nullable = "yes" if f.has_none_default else "no"
        lines.append(
            f"- {f.name}: type={f.type_repr or '?'}, kind={kind}, nullable={nullable}"
        )
    prompt = _SHAPE_PROMPT.format(cls=ci.cls.__name__, fields="\n".join(lines))
    data = provider(prompt, schema=_SHAPE_SCHEMA)
    shapes = data.get("shapes", [])
    return [s for s in shapes if isinstance(s, dict)]


def _apply_shapes(draft: SpecDraft, ci: ClassInfo, fields: List, shapes: List) -> None:
    """Turn validated shape choices into off-by-default, model-tagged suggestions.

    Every selector is built by spytial from the field (the render-verified form the
    deterministic rules use), never by the model. Choices that name an unknown field,
    an out-of-vocabulary direction, or a constraint that doesn't fit the field's kind
    are dropped — schema-level validation, no datum required.
    """
    by_name = {f.name: f for f in fields}
    cls = ci.cls.__name__
    seen = {_key(s) for s in draft.suggestions}

    for sh in shapes:
        f = by_name.get(sh.get("field"))
        if f is None:
            continue  # model named a field we didn't analyze — drop it
        sug = _shape_to_suggestion(ci, cls, f, sh)
        if sug is None:
            continue
        key = _key(sug)
        if key in seen:
            continue  # don't duplicate a directive the deterministic rules emitted
        seen.add(key)
        draft.suggestions.append(sug)


def _shape_to_suggestion(ci: ClassInfo, cls: str, f, sh: dict) -> Optional[Suggestion]:
    kind = sh.get("constraint")
    why = (sh.get("why") or "").strip()
    rationale = f"{f.name}: {why}" if why else f"{f.name}: model-suggested shape"
    # Directives over the original field relation carry source_field=f.name; a
    # derived (parent, child) edge over a container carries None, matching
    # rules.child_container — so identical suggestions de-dup and same-field
    # exclusivity grouping stays correct.
    source_field = f.name

    if kind == "orientation":
        dirs = [d for d in (sh.get("directions") or []) if d in _ORIENT_DIRS][:2]
        if not dirs:
            return None
        if f.container in _CONTAINERS:
            selector = _children_selector(cls, f.name, f.container)
            source_field = None  # derived edge, not the container relation itself
        else:
            selector = _edge_selector(ci, f.name)
        kwargs = {"selector": selector, "directions": dirs}
    elif kind == "cyclic":
        if f.container is not None:
            return None  # a ring is over a single pointer, not a collection
        direction = sh.get("direction")
        if direction not in _CYCLIC_DIRS:
            return None
        kwargs = {"selector": _edge_selector(ci, f.name), "direction": direction}
    elif kind == "group":
        if f.container not in _CONTAINERS:
            return None  # group boxes the elements of a collection
        kwargs = {"field": f.name, "groupOn": 0, "addToGroup": 1}
    else:
        return None  # 'none' or anything unrecognized — abstain

    return Suggestion(
        kind,
        kwargs,
        "low",
        rationale,
        source_field,
        enabled_by_default=False,
        source="llm",
    )


def _key(s: Suggestion):
    return (
        s.directive,
        s.source_field,
        json.dumps(s.kwargs, sort_keys=True, default=str),
    )
