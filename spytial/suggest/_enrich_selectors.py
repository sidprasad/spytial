"""Tier-2 enrichment: LLM-*authored* selectors, validated by evaluation over a datum.

The shape tier (:mod:`spytial.suggest._enrich`) reasons at the schema level — the
model picks a spatial *shape* per field and spytial builds the selector. This tier
goes further: the model authors the **selector expression** itself, for the cases
the shape tier can't reach — an edge through a join or closure, an edge over an
index/key relation (``list -> idx``, ``dict -> kv``, ``set -> contains``), a
relation the field names don't reveal.

A model-authored selector is an Alloy/Forge expression that can only be trusted once
it has been *evaluated*, so this tier is gated on a datum and the headless evaluator
(:mod:`spytial.suggest._eval`). Every candidate is run over the instance; only those
that parse, are non-empty, and have the arity the directive requires survive. They
enter the draft as off-by-default, ``source="llm"`` candidates — the human still
picks. Validating against real data is exactly what kills hallucinated relation
names, arity errors, and selectors that resolve to nothing.

Activates only when ``enrich=True`` **and** an instance is available **and** the
evaluator bridge is runnable. Any missing prerequisite records a note and falls back
to the shape-only tier; this never raises into ``suggest()``.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional

from . import _eval
from ._enrich import _ORIENT_DIRS, _structural_fields
from ._model import ClassInfo, SpecDraft, Suggestion
from ..provider_system import CnDDataInstanceBuilder

# Directive kinds tier-2 may author, with the selector arity each requires. Both
# shipped kinds take an arity-2 (edge) selector — the relational cases the shape
# tier can't express. (align/group/atomColor are arity-1 and easy to add once their
# kwarg vocabularies are pinned down; left out of this first cut deliberately.)
_DIRECTIVE_ARITY = {"orientation": 2, "inferredEdge": 2}

_SELECTOR_SCHEMA = {
    "type": "object",
    "properties": {
        "selectors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "directive": {"type": "string", "enum": list(_DIRECTIVE_ARITY)},
                    "selector": {"type": "string"},
                    "directions": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(_ORIENT_DIRS)},
                    },
                    "name": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["directive", "selector", "why"],
            },
        }
    },
    "required": ["selectors"],
}

_SELECTOR_PROMPT = """\
You author spytial SELECTORS for a diagram of one specific data instance. A selector
is a small relational expression in an Alloy-like language; spytial evaluates it over
the instance to pick atoms (arity 1) or edges/pairs (arity 2).

Grammar (use ONLY this):
- identifiers: a type or relation name from the vocabulary below
- join:        a.b        (follow relation b from a)
- product:     a -> b     (the pair edge)
- set ops:     a + b (union)   a & b (intersection)   a - b (difference)
- closures:    ^r (transitive)   *r (reflexive-transitive)   ~r (transpose)
- built-ins:   univ, iden, none

You may reference ONLY these names — anything else resolves to nothing:
  Types (with #atoms): {types}
  Relations (name/arity): {relations}

Author selectors for these directives. EACH needs an ARITY-2 selector returning PAIRS:
- orientation: a directional edge. Give `selector` (arity 2) and 1-2 `directions`
  from [below, above, left, right, directlyRight, directlyLeft].
- inferredEdge: a NEW named edge the structure implies but no single field names.
  Give `selector` (arity 2) and a short identifier `name`.

Only propose a selector that shows something a plain single-field edge does NOT —
e.g. an edge through a join/closure, or over an index/key relation. Skip anything a
bare field relation already covers. Each selector MUST evaluate to a non-empty set of
pairs over THIS data. Prefer a few high-quality selectors; return an empty list if
nothing is worthwhile.

Class: {cls}
Self-referential / structural fields: {fields}
"""


def enrich_selectors(draft: SpecDraft, ci: ClassInfo, model, instance) -> None:
    """Author selectors with the model, validate each over a datum, append survivors.

    Mutates ``draft`` in place. Every failure path records a note and returns; the
    caller also guards, but the no-raise contract is kept locally too.
    """
    try:
        datum = CnDDataInstanceBuilder().build_instance(instance)
    except Exception as exc:  # noqa: BLE001 — no datum, no tier
        draft.notes.append(
            f"enrich=True: selector tier skipped (couldn't build a datum from the instance: {exc})."
        )
        return

    if not _eval.is_available():
        draft.notes.append(
            "enrich=True: selector tier skipped (headless evaluator unavailable — needs node and a "
            "resolvable spytial-core, e.g. SPYTIAL_CORE_NODE_PATH)."
        )
        return

    vocab = _vocabulary(datum)
    if not vocab["relations"]:
        return  # no relations to author edges over — nothing for this tier to do

    try:
        candidates = _ask_selectors(model, ci, vocab)
    except Exception as exc:  # noqa: BLE001 — bad model call/parse: disable tier
        draft.notes.append(
            f"enrich=True: selector tier skipped (model call or response parse failed: {exc})."
        )
        return
    if not candidates:
        return

    selectors = [s for s in (_as_str(c.get("selector")) for c in candidates) if s]
    try:
        verdicts = {v.selector: v for v in _eval.evaluate_selectors(datum, selectors)}
    except _eval.EvaluatorUnavailable as exc:
        draft.notes.append(f"enrich=True: selector tier skipped ({exc}).")
        return

    seen = {s.dedup_key() for s in draft.suggestions}
    kept = 0
    for cand in candidates:
        try:
            sug = _admit(cand, verdicts)
        except Exception:  # noqa: BLE001 — drop one bad candidate, keep batch
            continue
        if sug is None or sug.dedup_key() in seen:
            continue
        seen.add(sug.dedup_key())
        draft.suggestions.append(sug)
        kept += 1
    if kept:
        draft.notes.append(
            f"enrich=True: added {kept} model-authored selector candidate(s), each validated over "
            "the provided instance (off by default — review before enabling)."
        )


def _admit(cand: dict, verdicts: dict) -> Optional[Suggestion]:
    """Return a Suggestion iff the candidate's selector resolves at the right arity.

    The arity gate is what makes validation trustworthy: ``resolves`` already means
    parsed + non-empty + arity >= 1 (so a hallucinated bareword, which echoes itself
    as an arity-0 singleton, is rejected), and the exact-arity check pins the result
    to what the directive consumes (an edge, arity 2).
    """
    directive = cand.get("directive")
    selector = _as_str(cand.get("selector"))
    expected = _DIRECTIVE_ARITY.get(directive)
    if expected is None or not selector:
        return None
    v = verdicts.get(selector)
    if v is None or not v.resolves or v.arity != expected:
        return None

    rationale = _as_str(cand.get("why")) or f"model-authored {directive} selector"
    if directive == "orientation":
        raw = cand.get("directions")
        dirs = (
            [d for d in raw if d in _ORIENT_DIRS][:2] if isinstance(raw, list) else []
        )
        if not dirs:
            return None  # an orientation with no valid direction is meaningless
        kwargs = {"selector": selector, "directions": dirs}
    elif directive == "inferredEdge":
        kwargs = {"name": _sanitize_name(cand.get("name")), "selector": selector}
    else:  # pragma: no cover — guarded by _DIRECTIVE_ARITY above
        return None

    return Suggestion(
        directive,
        kwargs,
        "low",
        rationale,
        None,
        enabled_by_default=False,
        source="llm",
    )


def _ask_selectors(model, ci: ClassInfo, vocab: dict) -> List[dict]:
    """Prompt the model for selectors grounded in the datum vocabulary; return the list."""
    types_line = ", ".join(f"{t} (#{n})" for t, n in vocab["types"]) or "(none)"
    rels_line = ", ".join(f"{name}/{arity}" for name, arity in vocab["relations"])
    fields = ", ".join(f.name for f in _structural_fields(ci)) or "(none detected)"
    prompt = _SELECTOR_PROMPT.format(
        cls=ci.cls.__name__, types=types_line, relations=rels_line, fields=fields
    )
    response = model.prompt(prompt, schema=_SELECTOR_SCHEMA)
    data = json.loads(response.text())
    out = data.get("selectors", [])
    return [c for c in out if isinstance(c, dict)]


def _vocabulary(datum: dict) -> dict:
    """The closed vocabulary a selector may reference: populated types + relations.

    Only *populated* types are listed — a selector over a zero-atom type triggers
    spytial-core's absent-type arity error, so feeding only non-empty types keeps the
    model inside the safe set. Relations carry arity so the model can match the
    directive's arity requirement.
    """
    pop: dict = {}
    for atom in datum.get("atoms", []):
        t = atom.get("type")
        if t:
            pop[t] = pop.get(t, 0) + 1
    types = sorted(pop.items())  # (type, #atoms) for populated types only

    relations = []
    seen = set()
    for rel in datum.get("relations", []):
        name = rel.get("name")
        if name and name not in seen:
            seen.add(name)
            relations.append((name, len(rel.get("types", []))))
    return {"types": types, "relations": relations}


def _as_str(value) -> str:
    """A model-supplied field as a clean string, or ``""`` for any non-string.

    The model's output is advisory — a candidate whose ``selector``/``why``/``name``
    comes back as a number or list must drop quietly, not crash the batch. An empty
    string then fails the truthiness checks downstream, so the candidate is rejected.
    """
    return value.strip() if isinstance(value, str) else ""


def _sanitize_name(raw) -> str:
    """Coerce a model-supplied edge name into a safe selector identifier."""
    name = re.sub(r"[^0-9A-Za-z_]", "", _as_str(raw))
    if not name:
        return "edge"
    if name[0].isdigit():
        name = "e" + name
    return name
