"""User-directed translation for ``spytial.suggest`` — the ``ask=`` tier.

The enrichment tiers are *unprompted*: the model proposes shapes
(:mod:`._enrich`) or selectors (:mod:`._enrich_from_examples`) on its own
initiative, quietly, off-by-default or demotable. This tier is the opposite: the
**user hands over a sentence** —

    suggest(tree, ask="all binary tree children should be below their parents",
            enrich=ClaudeCode())

— and the model's only job is to translate that sentence into directive(s). A
candidate must pass the same admission gauntlet before it reaches the draft:

1. **Kind + vocabulary** (schema level): the directive kind is one we support,
   its enum kwargs (directions, colors present) are in the canonical sets.
2. **Selector evaluation** (instance level): the selector parses, is non-empty,
   and has the kind's exact arity on *every* example, via the headless evaluator.
3. **Authoring gate** (parser level): the kwargs go through the same
   ``_prepare_kwargs`` / ``validate_fields`` pipeline the ``@spytial.*``
   decorators run, so an admitted row is guaranteed to author cleanly.

Because the user explicitly asked, the failure contract is **loud** — the
inverse of enrichment's degrade-with-a-note. A missing provider, a dead
evaluator, a "cannot express that" reply, or an ask of which *nothing* validates
raises :class:`AskError` with the reasons, after one counterexample-guided
repair round. A compound request ("children below, and color the leaves") is
admitted per candidate: what validates lands, the failed remainder is what the
repair round retries, and anything still unvalidated is recorded in
``draft.notes`` rather than silently dropped. Admitted rows are enabled by
default (the user asked for them) and tagged ``source="llm"``.

And the ask is **authoritative on the ground it covers**: an admitted geometric
row (orientation/cyclic/align) demotes every enabled geometric row — rule- or
model-proposed — whose selector *overlaps* the ask's, the way the shape tier
demotes the rule it beats. Overlap is decided by the evaluator, not by guessing
at selector syntax: ``(ask_sel) & (rival_sel)`` is itself a selector, and a
non-empty intersection on any example means both constraints claim the same
edges. Demoted rows move to ``draft.alternatives`` — kept, off, one toggle away.

Kinds covered in this first cut: the binary-selector constraints
(``orientation``, ``cyclic``, ``align``), ``inferredEdge``, and the
unary-selector directives ``hideAtom`` and ``atomStyle`` (fill/stroke colors).
``group`` is deliberately left out for now — its selector is legal at either
arity and its two kwarg forms need their own admit rules.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Tuple

from ..annotations import (
    ALIGN_DIRECTIONS,
    CONSTRAINT_TYPES,
    DIRECTIVE_TYPES,
    ORIENTATION_DIRECTIONS,
    ROTATION_DIRECTIONS,
    _prepare_kwargs,
    validate_fields,
)
from ..provider_system import CnDDataInstanceBuilder
from . import _eval
from ._enrich import _demote
from ._enrich_from_examples import (
    _as_str,
    _edge_name,
    _evaluate_per_example,
    _make_resolver,
    _vocabulary,
)
from ._model import ClassInfo, SpecDraft, Suggestion


class AskError(RuntimeError):
    """``ask=`` could not be honored — and the user explicitly asked, so we say so.

    Raised (never swallowed) for: no/unresolvable provider, no buildable example
    datum, no headless evaluator, a failed provider call, a model "cannot express
    that" reply, or a full round of candidates that all failed validation. The
    message carries the reasons — the model's own, or the per-candidate
    diagnostics from evaluation.
    """


# Directive kinds ask may author, with the selector arity each requires
# (docs/selectors.md: orientation/align/inferredEdge — and cyclic — act on edges;
# hideAtom/atomStyle act on atoms).
_KIND_ARITY = {
    "orientation": 2,
    "cyclic": 2,
    "align": 2,
    "inferredEdge": 2,
    "hideAtom": 1,
    "atomStyle": 1,
}

# One initial translation plus at most one counterexample-guided repair, same
# budget and rationale as the tier-2 selector rounds.
_MAX_ROUNDS = 2

# The kinds that fight over geometry: an admitted ask row of one of these demotes
# every enabled row of these kinds whose selector overlaps its own.
_GEOMETRIC = ("orientation", "cyclic", "align")

_ASK_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "directive": {"type": "string", "enum": list(_KIND_ARITY)},
                    "selector": {"type": "string"},
                    "directions": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": list(ORIENTATION_DIRECTIONS),
                        },
                    },
                    "direction": {
                        "type": "string",
                        "enum": list(ROTATION_DIRECTIONS) + list(ALIGN_DIRECTIONS),
                    },
                    "name": {"type": "string"},
                    "fill": {"type": "string"},
                    "stroke": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["directive", "selector", "why"],
            },
        },
        "cannot": {"type": "string"},
    },
    "required": ["candidates"],
}

_ASK_PROMPT = """\
You translate ONE user-written layout request into spytial directive(s) for a
diagram of a data structure, validated against {n} example instance(s).

The user's request:
  "{statement}"

A selector is a small relational expression in an Alloy-like language; spytial
evaluates it over an instance to pick atoms (arity 1) or edges/pairs (arity 2).

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

Express the request with these directive kinds:
- orientation: place edge targets in a direction. selector (arity 2) plus 1-2
  `directions` from [{orient_dirs}].
- cyclic: lay a ring of atoms around a circle. selector (arity 2) plus
  `direction` (clockwise / counterclockwise).
- align: align edge endpoints on an axis. selector (arity 2) plus `direction`
  (horizontal / vertical).
- inferredEdge: draw a NEW named edge the structure implies. selector (arity 2)
  plus a short identifier `name`.
- hideAtom: hide atoms from the diagram. selector (arity 1).
- atomStyle: recolor atoms. selector (arity 1) plus `fill` and/or `stroke`
  (CSS colors).

Prefer the simplest selector that means the request — a bare relation name when
the request is about a single field. Each selector MUST evaluate to a non-empty
result at the required arity on EVERY example. Translate ONLY what the request
says (1-3 candidates); do not add extras. If the request has no expressible
reading — it is not spatial, or the vocabulary has no relation for it — return
an empty candidates list and explain in `cannot`.

Class: {cls}
Fields: {fields}
"""


def ask_draft(
    draft: SpecDraft,
    ci: ClassInfo,
    statement: str,
    *,
    provider: Any,
    examples: List[Any],
) -> None:
    """Translate ``statement`` into validated directive(s) appended to ``draft``.

    Mutates ``draft`` in place. Every failure raises :class:`AskError` — the
    caller asked for this translation, so nothing degrades quietly.
    """
    datums = []
    for obj in examples:
        try:
            datums.append(CnDDataInstanceBuilder().build_instance(obj))
        except Exception:  # noqa: BLE001 — skip an example we can't build a datum from
            continue
    if not datums:
        raise AskError(
            "ask: needs at least one example instance to validate against — "
            "pass an instance as the target, or examples=[...]."
        )
    if not _eval.is_available():
        raise AskError(
            "ask: headless selector evaluation is unavailable — it needs a node "
            "runtime on PATH (or SPYTIAL_NODE pointing at one)."
        )

    vocab = _vocabulary(datums)
    reserved = {n for n, _ in vocab["relations"]} | {t for t, _ in vocab["types"]}

    feedback: Optional[str] = None
    cannot: Optional[str] = None
    rejects: List[str] = []
    installed: List[Suggestion] = []
    seen_rows: set = set()
    for round_i in range(_MAX_ROUNDS):
        data = _call_provider(provider, ci, vocab, statement, len(datums), feedback)
        raw_candidates = data.get("candidates", [])
        candidates = (
            [c for c in raw_candidates if isinstance(c, dict)]
            if isinstance(raw_candidates, list)
            else []
        )
        cannot = _as_str(data.get("cannot")) or None
        if not candidates:
            break  # the model declined (or had nothing left to repair)

        selectors = list(
            dict.fromkeys(
                s for s in (_as_str(c.get("selector")) for c in candidates) if s
            )
        )
        per_example, last_exc = _evaluate_per_example(datums, selectors)
        if not per_example:
            raise AskError(f"ask: no example could be evaluated ({last_exc}).")

        round_installed, rejects = _admit_round(
            draft, candidates, _make_resolver(per_example), per_example, reserved,
            statement,
        )
        # A multi-part ask admits per candidate; identity-dedup so a repair round
        # re-sending an accepted candidate doesn't double-count it.
        for row in round_installed:
            if id(row) not in seen_rows:
                seen_rows.add(id(row))
                installed.append(row)
        if not rejects or round_i == _MAX_ROUNDS - 1:
            break
        # Repair targets the failures — even after a partial success, so a
        # compound request doesn't silently lose the half that slipped.
        feedback = "\n".join(rejects)
        if installed:
            feedback += (
                "\n(The other candidate(s) were already accepted — do NOT re-send "
                "them. Return corrected versions of ONLY the failed ones, or drop "
                "any you cannot fix.)"
            )

    if installed:
        demoted = _demote_competitors(draft, installed, datums)
        n = len(datums)
        across = "the example instance" if n == 1 else f"all {n} example instances"
        note = (
            f'ask: "{statement}" -> {len(installed)} directive(s), '
            f"each validated over {across}"
        )
        if demoted:
            note += f"; {demoted} overlapping row(s) demoted to alternatives"
        draft.notes.append(note + ".")
        if rejects:
            # Partial honesty: what was admitted stands, but the unvalidated
            # remainder of the request must not vanish without a trace.
            draft.notes.append(
                "ask: part of the request could not be validated — "
                + "; ".join(r.lstrip("- ") for r in rejects)
            )
        return
    raise AskError(_failure_message(statement, cannot, rejects))


def _call_provider(
    provider, ci: ClassInfo, vocab: dict, statement: str, n: int,
    feedback: Optional[str],
) -> dict:
    types_line = ", ".join(f"{t} (#{c})" for t, c in vocab["types"]) or "(none)"
    rels_line = (
        ", ".join(f"{name}/{arity}" for name, arity in vocab["relations"]) or "(none)"
    )
    fields = ", ".join(f.name for f in ci.fields if not f.is_private) or "(none)"
    prompt = _ASK_PROMPT.format(
        statement=statement,
        cls=ci.cls.__name__,
        types=types_line,
        relations=rels_line,
        fields=fields,
        orient_dirs=", ".join(ORIENTATION_DIRECTIONS),
        n=n,
    )
    if feedback:
        prompt += (
            "\n\nYour previous translation did NOT hold up when evaluated on the "
            f"{n} example(s). Here is what went wrong, per candidate:\n{feedback}\n"
            "Return corrected candidates that avoid these problems, using ONLY the "
            "vocabulary above. If the request truly cannot be expressed, return an "
            "empty candidates list and explain in `cannot`."
        )
    try:
        data = provider(prompt, schema=_ASK_SCHEMA)
    except Exception as exc:  # noqa: BLE001 — surface, don't swallow: the user asked
        raise AskError(f'ask: provider call failed for "{statement}": {exc}') from exc
    if not isinstance(data, dict):
        raise AskError(
            f"ask: provider returned {type(data).__name__}, expected a JSON object."
        )
    return data


def _admit_round(
    draft: SpecDraft,
    candidates: List[dict],
    resolves: Callable[[str, int], bool],
    per_example: List[dict],
    reserved: set,
    statement: str,
) -> Tuple[List[Suggestion], List[str]]:
    """Admit every candidate that survives the full gauntlet; explain the rest.

    Returns ``(installed_rows, reject_lines)`` — the rows now carrying the ask
    (so the competitor demotion can exempt them). A candidate that duplicates an
    existing row *satisfies* the ask by enabling that row (the user explicitly
    asked for it) rather than appending a twin.
    """
    installed: List[Suggestion] = []
    rejects: List[str] = []
    for cand in candidates:
        kwargs, reason = _candidate_kwargs(cand, reserved)
        if kwargs is None:
            rejects.append(_reject_line(cand, reason))
            continue
        expected = _KIND_ARITY[cand["directive"]]
        if not resolves(kwargs["selector"], expected):
            rejects.append(
                _reject_line(
                    cand, _selector_reason(kwargs["selector"], expected, per_example)
                )
            )
            continue
        try:
            kind, prepared = _authoring_gate(cand["directive"], kwargs)
        except ValueError as exc:
            rejects.append(_reject_line(cand, str(exc)))
            continue

        why = _as_str(cand.get("why"))
        rationale = f"ask: {why}" if why else f'ask: "{statement}"'
        installed.append(
            _install(
                draft,
                Suggestion(
                    kind,
                    prepared,
                    "high",
                    rationale,
                    None,
                    enabled_by_default=True,
                    source="llm",
                ),
            )
        )
    return installed, rejects


def _candidate_kwargs(cand: dict, reserved: set):
    """Kind-level admission: ``(kwargs, None)`` or ``(None, reason)``.

    Checks what the evaluator can't: the kind is known, its enum kwargs are in
    the canonical vocabularies, an inferredEdge name is safe and non-shadowing.
    """
    kind = cand.get("directive")
    selector = _as_str(cand.get("selector"))
    if kind not in _KIND_ARITY:
        return None, f"unknown directive {kind!r}; use one of {list(_KIND_ARITY)}"
    if not selector:
        return None, "no selector expression was given"

    if kind == "orientation":
        raw = cand.get("directions")
        dirs = (
            [d for d in raw if d in ORIENTATION_DIRECTIONS][:2]
            if isinstance(raw, list)
            else []
        )
        if not dirs:
            return None, (
                "orientation needs 1-2 directions from "
                f"[{', '.join(ORIENTATION_DIRECTIONS)}]"
            )
        return {"selector": selector, "directions": dirs}, None
    if kind == "cyclic":
        direction = cand.get("direction")
        if direction not in ROTATION_DIRECTIONS:
            return None, "cyclic needs direction clockwise or counterclockwise"
        return {"selector": selector, "direction": direction}, None
    if kind == "align":
        direction = cand.get("direction")
        if direction not in ALIGN_DIRECTIONS:
            return None, "align needs direction horizontal or vertical"
        return {"selector": selector, "direction": direction}, None
    if kind == "inferredEdge":
        return {"name": _edge_name(cand.get("name"), reserved), "selector": selector}, None
    if kind == "hideAtom":
        return {"selector": selector}, None
    # atomStyle
    fill, stroke = _as_str(cand.get("fill")), _as_str(cand.get("stroke"))
    if not fill and not stroke:
        return None, "atomStyle needs fill and/or stroke (CSS colors)"
    kwargs: dict = {"selector": selector}
    if fill:
        kwargs["fillStyle"] = {"color": fill}
    if stroke:
        kwargs["borderStyle"] = {"color": stroke}
    return kwargs, None


def _authoring_gate(kind: str, kwargs: dict):
    """Run the same pipeline the ``@spytial.*`` decorators run; return its output.

    ``_prepare_kwargs`` desugars legacy forms, coerces style blocks, and rejects
    out-of-vocabulary values; ``validate_fields`` rejects a missing required
    kwarg. What comes back is the canonical authoring form, so it is what the
    Suggestion stores — an admitted row can't fail later in ``apply()``.
    """
    effective, prepared = _prepare_kwargs(kind, dict(kwargs), stacklevel=2)
    spec = CONSTRAINT_TYPES.get(effective) or DIRECTIVE_TYPES.get(effective)
    if spec is None:
        raise ValueError(f"unknown annotation type {effective!r}")
    validate_fields(effective, prepared, spec)
    return effective, prepared


def _install(draft: SpecDraft, sug: Suggestion) -> Suggestion:
    """Add ``sug``, or enable the identical row that already exists.

    An ask that lands on a row the rules already proposed (enabled or demoted to
    an alternative) is agreement, not a duplicate — the user's sentence just
    turned it on. Returns the row that now carries the ask, so competitor
    demotion can exempt it.
    """
    key = sug.dedup_key()
    for s in draft.suggestions:
        if s.dedup_key() == key:
            s.enabled_by_default = True
            return s
    for s in draft.alternatives:
        if s.dedup_key() == key:
            draft.alternatives.remove(s)
            s.enabled_by_default = True
            draft.suggestions.append(s)
            return s
    draft.suggestions.append(sug)
    return sug


def _demote_competitors(
    draft: SpecDraft, installed: List[Suggestion], datums: List
) -> int:
    """The ask wins its ground: demote enabled geometric rows the ask overlaps.

    "Competing" is decided by the evaluator, not by inspecting selector syntax:
    ``(ask_sel) & (rival_sel)`` is itself a selector, and a non-empty result on
    *any* example means both constraints claim the same edge — so the rival
    (rule- or model-proposed alike) steps down to ``draft.alternatives``, the
    same one-toggle-away demotion the shape tier uses. An intersection that
    fails to evaluate is treated as no overlap: when in doubt, don't demote.
    Non-geometric kinds (styling, hiding, inferred edges) don't fight the layout
    solver over positions, so they are left alone.
    """
    ask_selectors = [
        s.kwargs.get("selector")
        for s in installed
        if s.directive in _GEOMETRIC and s.kwargs.get("selector")
    ]
    if not ask_selectors:
        return 0
    installed_ids = {id(s) for s in installed}
    rivals = [
        s
        for s in draft.suggestions
        if s.directive in _GEOMETRIC
        and s.enabled_by_default
        and id(s) not in installed_ids
        and s.kwargs.get("selector")
    ]
    if not rivals:
        return 0

    pairs = [
        (f"({a}) & ({r.kwargs['selector']})", r) for r in rivals for a in ask_selectors
    ]
    selectors = list(dict.fromkeys(sel for sel, _ in pairs))
    per_example, _exc = _evaluate_per_example(datums, selectors)
    if not per_example:
        return 0  # couldn't check — leave everything standing

    overlapping = set()
    for sel, rival in pairs:
        if id(rival) in overlapping:
            continue
        for verdicts in per_example:
            v = verdicts.get(sel)
            if v is not None and v.ok and not v.empty:
                overlapping.add(id(rival))
                break

    to_demote = [r for r in rivals if id(r) in overlapping]
    _demote(draft, to_demote)
    return len(to_demote)


def _selector_reason(selector: str, expected: int, per_example: List[dict]) -> str:
    """Why a selector failed evaluation, phrased for repair feedback."""
    for verdicts in per_example:
        v = verdicts.get(selector)
        if v is None:
            continue
        if v.resolves and v.arity != expected:
            return (
                f"resolved at arity {v.arity}, but this directive needs "
                f"arity {expected}"
            )
        diag = v.diagnostic
        if diag:
            return diag
    return "did not resolve on every example"


def _reject_line(cand: dict, reason: Optional[str]) -> str:
    sel = _as_str(cand.get("selector")) or "(no selector)"
    return f"- {cand.get('directive')} `{sel}`: {reason}"


def _failure_message(
    statement: str, cannot: Optional[str], rejects: List[str]
) -> str:
    msg = f'ask: could not translate "{statement}" into a validated directive.'
    if cannot:
        msg += f" The model reported: {cannot}"
    if rejects:
        msg += " Candidates were rejected:\n" + "\n".join(rejects)
    return msg + (
        "\nRephrase the request, name a field/relation that exists in the "
        "examples, or author the directive by hand."
    )
