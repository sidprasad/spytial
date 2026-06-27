"""Optional LLM *enrichment* for ``spytial.suggest`` (the ``[suggest-llm]`` extra).

Dormant unless you call ``suggest(..., enrich=True)``. The deterministic analyzer
needs none of this.

The cardinal rule here: **the model never writes a relational selector.** Spytial
selectors are Alloy/Forge relational expressions (``{ p : T, c : T | c in p.left }``,
``left - (univ -> NoneType)``, ``@:(x.color.name) = RED``) — easy for a model to get
subtly wrong, and there is no in-Python validator to catch it (spytial-core runs in
the browser). So enrichment only fills *values* into directives whose selectors the
deterministic rules already generated and render-verified. Today that is one thing:
semantic colors for enum members, replacing the arbitrary built-in palette. The
worst a bad model response can do is propose an ugly color — never an illegal
selector.

Everything degrades to the static draft. No ``llm`` installed, no model/key
configured, or a malformed response each append a note and return the draft
unchanged — enrichment can never crash ``suggest()``. And because enriched rows are
tagged ``source="llm"`` and stay off by default, they are *candidates you pick*, not
directives applied behind your back.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from ._model import ClassInfo, SpecDraft, Suggestion
from .rules import enum_member_selector

_INSTALL_HINT = (
    "enrich=True needs the optional 'llm' library. Install it with "
    'pip install "spytial_diagramming[suggest-llm]" and configure a model '
    "(e.g. `llm install llm-anthropic && llm keys set anthropic`, or any other "
    "llm provider plugin). Returning the static draft unchanged."
)

# A fixed-shape schema (a flat list, not an open-ended map) so it round-trips
# across llm provider plugins whose structured-output support rejects
# ``additionalProperties``.
_PALETTE_SCHEMA = {
    "type": "object",
    "properties": {
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "member": {"type": "string"},
                    "color": {
                        "type": "string",
                        "description": (
                            "A CSS color name or #hex. Empty string if no "
                            "conventional color fits."
                        ),
                    },
                },
                "required": ["field", "member", "color"],
            },
        }
    },
    "required": ["assignments"],
}

_PALETTE_PROMPT = """\
You choose display colors for enum members in a structure diagram. You ONLY choose \
colors — never write code, selectors, or any other text. Prefer conventional \
associations: RED->red, BLACK->#222, GREEN->seagreen, BLUE->steelblue, \
ACTIVE/OK/SUCCESS->seagreen, ERROR/FAIL->crimson, WARNING/PENDING->goldenrod, \
INACTIVE/DISABLED->#999. If a member has no conventional color, return an empty \
string for it and it will keep the default palette.

Class: {cls}
Enum fields and their members:
{fields}

Return exactly one assignment per (field, member) pair listed above."""


def _import_llm():
    """Return the ``llm`` module, or ``None`` if the extra isn't installed."""
    try:
        import llm  # type: ignore

        return llm
    except ImportError:
        return None


def enrich_draft(
    draft: SpecDraft, class_info: ClassInfo, *, model: Optional[str] = None
) -> SpecDraft:
    """Augment a :class:`SpecDraft` with model-chosen values; returns the draft.

    Any failure — missing dependency, no configured model, malformed output —
    leaves the deterministic suggestions untouched and records a note in
    ``draft.notes``. The draft is mutated in place and also returned.
    """
    llm = _import_llm()
    if llm is None:
        draft.notes.append(_INSTALL_HINT)
        return draft

    try:
        m = llm.get_model(model) if model else llm.get_model()
    except Exception as exc:  # noqa: BLE001 — any provider/config error degrades
        draft.notes.append(
            f"enrich=True: no usable llm model ({exc}); returning the static draft."
        )
        return draft

    try:
        _enrich_palette(draft, class_info, m)
    except Exception as exc:  # noqa: BLE001 — never crash suggest() on enrichment
        draft.notes.append(f"enrich=True: color enrichment skipped ({exc}).")
    return draft


def _enrich_palette(draft: SpecDraft, ci: ClassInfo, model) -> None:
    """Replace the built-in palette guesses for enum fields with semantic colors."""
    enum_fields: Dict[str, List[str]] = {
        f.name: list(f.enum_members)
        for f in ci.fields
        if f.enum_members and not f.is_private
    }
    if not enum_fields:
        return  # nothing to color; don't spend a model call

    colors = _ask_palette(model, ci.cls.__name__, enum_fields)
    if not colors:
        return

    type_name = ci.cls.__name__
    draft.suggestions = [
        s
        for s in draft.suggestions
        if not (s.directive == "atomColor" and s.source_field in enum_fields)
    ]
    for field_name, members in enum_fields.items():
        chosen = colors.get(field_name, {})
        for member in members:
            color = chosen.get(member)
            if not color:
                continue  # no conventional color — keep the default (drop the row)
            draft.suggestions.append(
                Suggestion(
                    "atomColor",
                    {
                        "selector": enum_member_selector(type_name, field_name, member),
                        "value": color,
                    },
                    "medium",
                    f"{field_name} = {member} -> {color} (semantic, model-chosen)",
                    field_name,
                    enabled_by_default=False,
                    source="llm",
                )
            )


def _ask_palette(
    model, cls_name: str, enum_fields: Dict[str, List[str]]
) -> Dict[str, Dict[str, str]]:
    """Prompt the model for one color per (field, member); validate the response.

    Returns ``{field: {member: color}}``, keeping only non-empty colors for
    (field, member) pairs we actually asked about — so a model can't smuggle in a
    field/member (and therefore a selector) we never offered.
    """
    field_lines = "\n".join(
        f"- {field}: {', '.join(members)}" for field, members in enum_fields.items()
    )
    prompt = _PALETTE_PROMPT.format(cls=cls_name, fields=field_lines)
    response = model.prompt(prompt, schema=_PALETTE_SCHEMA)
    data = json.loads(response.text())

    out: Dict[str, Dict[str, str]] = {}
    for assignment in data.get("assignments", []):
        if not isinstance(assignment, dict):
            continue
        field = assignment.get("field")
        member = assignment.get("member")
        color = str(assignment.get("color") or "").strip()
        if color and field in enum_fields and member in enum_fields[field]:
            out.setdefault(field, {})[member] = color
    return out
