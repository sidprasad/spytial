"""Example-validated selectors for ``spytial.suggest`` (the tier-2 enrichment).

The shape tier (:mod:`spytial.suggest._enrich`) reasons at the schema level — the
model picks a spatial *shape* per field and spytial builds the selector. This tier
goes further: the model **authors the selector expression** itself, and a candidate
is admitted only if it holds up when *evaluated over example instances* — the
relational cases the shape tier can't reach (an edge through a join or closure, an
edge over an index/key relation, a relation the field names don't reveal).

This is selector suggestion **by example**. You supply one or more example instances
(``suggest(obj, enrich=True)`` or ``suggest(Cls, examples=[a, b, ...], enrich=True)``);
the model proposes selectors grounded in those instances' vocabulary, and only the
ones that parse, are non-empty, and have the directive's arity **on every example**
survive. Validating across a *set* of examples is what narrows the gap toward "correct
on all data" — a selector that resolves consistently across several instances is far
more trustworthy than one witnessed once.

This is **LLM-authored, example-validated** — distinct from spytial-core's
deterministic by-example *synthesizer* (``synthesizeSelector``): here the model writes
the selector and the examples only validate it.

Gated on the headless evaluator (:mod:`._eval`). Any missing prerequisite (no
buildable datum, no evaluator) records a note and falls back to the shape-only tier;
this never raises into ``suggest()``.
"""

from __future__ import annotations

import json
import re
from typing import Callable, List, Optional

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
You author spytial SELECTORS for a diagram, validated against {n} example instance(s)
of the same class. A selector is a small relational expression in an Alloy-like
language; spytial evaluates it over an instance to pick atoms (arity 1) or edges/pairs
(arity 2).

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
pairs on EVERY one of the {n} example(s). Prefer a few high-quality selectors; return
an empty list if nothing is worthwhile.

Class: {cls}
Self-referential / structural fields: {fields}
"""


def enrich_from_examples(
    draft: SpecDraft, ci: ClassInfo, model, examples: List
) -> None:
    """Author selectors, validate each across the ``examples``, append survivors.

    ``examples`` is a non-empty list of instances of ``ci.cls``. A selector is
    admitted only if it resolves at the directive's arity on *every* example — the
    instance-set form. Mutates ``draft`` in place; every failure path records a note
    and returns, so this never raises into ``suggest()``.
    """
    datums = []
    for obj in examples:
        try:
            datums.append(CnDDataInstanceBuilder().build_instance(obj))
        except Exception:  # noqa: BLE001 — skip an example we can't build a datum from
            continue
    if not datums:
        draft.notes.append(
            "enrich=True: selector tier skipped "
            "(couldn't build a datum from any example)."
        )
        return

    if not _eval.is_available():
        draft.notes.append(
            "enrich=True: selector tier skipped (headless evaluator unavailable "
            "— needs a node runtime on PATH, or set SPYTIAL_NODE to a node binary)."
        )
        return

    vocab = _vocabulary(datums)
    if not vocab["relations"]:
        return  # no relations to author edges over — nothing for this tier to do

    try:
        candidates = _ask_selectors(model, ci, vocab, len(datums))
    except Exception as exc:  # noqa: BLE001 — bad model call/parse: disable tier
        draft.notes.append(
            "enrich=True: selector tier skipped "
            f"(model call or response parse failed: {exc})."
        )
        return
    if not candidates:
        return

    # De-dup selector strings so the bridge doesn't evaluate the same expression
    # twice when two directives propose it.
    selectors = list(
        dict.fromkeys(s for s in (_as_str(c.get("selector")) for c in candidates) if s)
    )
    # Evaluate per example, tolerating an example whose datum the evaluator rejects —
    # consistent with the build loop above. Degrade only if none can be evaluated.
    per_example = []
    last_exc = None
    for d in datums:
        try:
            per_example.append(
                {v.selector: v for v in _eval.evaluate_selectors(d, selectors)}
            )
        except _eval.EvaluatorUnavailable as exc:
            last_exc = exc
    if not per_example:
        draft.notes.append(
            "enrich=True: selector tier skipped "
            f"(no example could be evaluated: {last_exc})."
        )
        return

    def resolves_on_all(selector: str, expected: int) -> bool:
        """True iff the selector resolves at ``expected`` arity on every example."""
        for verdicts in per_example:
            v = verdicts.get(selector)
            if v is None or not v.resolves or v.arity != expected:
                return False
        return True

    # Names already taken by a type/relation — an inferredEdge must not shadow one.
    reserved = {n for n, _ in vocab["relations"]} | {t for t, _ in vocab["types"]}
    seen = {s.dedup_key() for s in draft.suggestions}
    kept = 0
    for cand in candidates:
        try:
            sug = _admit(cand, resolves_on_all, reserved)
        except Exception:  # noqa: BLE001 — drop one bad candidate, keep batch
            continue
        if sug is None or sug.dedup_key() in seen:
            continue
        seen.add(sug.dedup_key())
        draft.suggestions.append(sug)
        kept += 1
    if kept:
        n = len(datums)
        across = "the example instance" if n == 1 else f"all {n} example instances"
        draft.notes.append(
            f"enrich=True: added {kept} model-authored selector "
            f"candidate(s), each validated over {across} "
            "(off by default — review before enabling)."
        )


def _admit(
    cand: dict, resolves: Callable[[str, int], bool], reserved: set
) -> Optional[Suggestion]:
    """Return a Suggestion iff the candidate's selector resolves at the right arity.

    The arity gate is what makes validation trustworthy: ``resolves`` already means
    parsed + non-empty + arity >= 1 on every example (so a hallucinated bareword,
    which echoes itself as an arity-0 singleton, is rejected), and the exact-arity
    check pins the result to what the directive consumes (an edge, arity 2).
    """
    directive = cand.get("directive")
    selector = _as_str(cand.get("selector"))
    expected = _DIRECTIVE_ARITY.get(directive)
    if expected is None or not selector:
        return None
    if not resolves(selector, expected):
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
        kwargs = {"name": _edge_name(cand.get("name"), reserved), "selector": selector}
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


def _ask_selectors(model, ci: ClassInfo, vocab: dict, n_examples: int) -> List[dict]:
    """Prompt the model for selectors grounded in the vocabulary; return the list."""
    types_line = ", ".join(f"{t} (#{n})" for t, n in vocab["types"]) or "(none)"
    rels_line = ", ".join(f"{name}/{arity}" for name, arity in vocab["relations"])
    fields = ", ".join(f.name for f in _structural_fields(ci)) or "(none detected)"
    prompt = _SELECTOR_PROMPT.format(
        cls=ci.cls.__name__,
        types=types_line,
        relations=rels_line,
        fields=fields,
        n=n_examples,
    )
    response = model.prompt(prompt, schema=_SELECTOR_SCHEMA)
    data = json.loads(response.text())
    out = data.get("selectors", [])
    return [c for c in out if isinstance(c, dict)]


def _vocabulary(datums: List[dict]) -> dict:
    """The closed vocabulary a selector may reference: populated types + relations.

    Unions across all example datums, so the model sees every name that appears in
    any example; validation then requires a selector to resolve on *every* example, so
    a name present in only some examples is offered but won't survive. Only *populated*
    types are listed — a selector over a zero-atom type triggers spytial-core's
    absent-type arity error, so feeding only non-empty types keeps the model inside the
    safe set.
    """
    pop: dict = {}
    relations: dict = {}
    for datum in datums:
        for atom in datum.get("atoms", []):
            t = atom.get("type")
            if t:
                pop[t] = pop.get(t, 0) + 1
        for rel in datum.get("relations", []):
            name = rel.get("name")
            if name and name not in relations:
                relations[name] = len(rel.get("types", []))
    return {"types": sorted(pop.items()), "relations": sorted(relations.items())}


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


def _edge_name(raw, reserved) -> str:
    """A safe, non-colliding identifier for an inferredEdge.

    Sanitizes the model's name, then mangles it if it would shadow a real type or
    relation already in the datum — an inferredEdge named ``next`` over data that has a
    ``next`` relation renders confusingly.
    """
    name = _sanitize_name(raw)
    while name in reserved:
        name += "_"
    return name
