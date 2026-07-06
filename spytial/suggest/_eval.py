"""Headless selector evaluation for ``spytial.suggest`` (tier-2 dynamic validation).

This bridges Python to the **windowless** spytial-core evaluator (the
``spytial-core/evaluator`` entry, shipped in spytial-core>=2.9.2 via
sidprasad/spytial-core#485) through a short-lived ``node`` subprocess, so a
candidate selector can be validated against a *datum* outside a browser.

It is the dynamic counterpart to the schema-level *shape* tier in
:mod:`spytial.suggest._enrich`. The shape tier reasons over a class's fields and
needs no instance; this tier runs a selector over representative data and reports
whether it parses, errors, or resolves to nothing / the wrong arity. Together
they let the LLM tier author actual selectors and admit only those that hold up.

Degrades like the rest of suggest's optional machinery. If ``node`` or a
resolvable ``spytial-core`` install is missing, :func:`is_available` returns
``False`` and :func:`evaluate_selectors` raises :class:`EvaluatorUnavailable`;
callers catch it, note it, and fall back to schema-level validation. It never
crashes ``suggest()``.

Resolving the JS side
---------------------
``node`` is found on ``PATH`` (override with ``SPYTIAL_NODE``). The evaluator
itself is resolved in priority order:

1. ``SPYTIAL_CORE_NODE_PATH`` -- a directory containing ``node_modules/spytial-core``
   (e.g. ``npm install spytial-core`` in a cache dir). For power users who want to
   run against their own spytial-core; resolved via ``NODE_PATH``.
2. The **vendored** self-contained evaluator shipped in the wheel
   (``_vendor/spytial-core-evaluator.js``). This is the default, so a plain
   ``pip install`` needs no npm install and no env var -- only a ``node`` binary.
   It is a single bundled file (spytial-core>=2.10.1's ``./evaluator`` build), so
   it loads by absolute path with no sibling ``node_modules``.

So the only hard requirement is a ``node`` runtime; everything else degrades.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_SHIM = Path(__file__).parent / "_eval_selectors.js"
# The self-contained evaluator vendored from spytial-core (see _vendor/README.md).
# Absent only in an unusual install that stripped package data.
_VENDORED_EVALUATOR = Path(__file__).parent / "_vendor" / "spytial-core-evaluator.js"

# How long node may take before we give up on a batch. Generous; evaluation of a
# handful of selectors over a small witness is milliseconds.
_TIMEOUT_S = 30


class EvaluatorUnavailable(RuntimeError):
    """Raised when the headless evaluator bridge can't run (no node / no core).

    Callers in the suggest pipeline catch this and degrade to schema-level
    validation rather than failing.
    """


@dataclass
class SelectorVerdict:
    """Outcome of evaluating one selector over a datum.

    Attributes mirror the structured signals the evaluator emits, so a caller can
    decide *why* a candidate was admitted or dropped.
    """

    selector: str
    ok: bool  # parsed and evaluated without an error or a thrown exception
    empty: bool  # evaluated to nothing (the empty set)
    arity: int  # max arity of the result; 0 means a singleton / scalar / none
    error: Optional[str] = None  # message when ok is False
    pretty: Optional[str] = None  # human-readable rendering of the result
    # Static-analyzer verdict (present only when the evaluator build exposes it):
    # the fold status (unsat/tautology/empty/ill-typed/unknown) and its reason. It's
    # the *why* behind a rejection -- a provable empty, an arity/type mismatch -- which
    # plain evaluation can't articulate. Used to give the model repair feedback.
    static_status: Optional[str] = None
    static_reason: Optional[str] = None

    @property
    def resolves(self) -> bool:
        """True for a selector worth keeping: clean, non-empty, and *relational*.

        The ``arity >= 1`` guard is load-bearing. An unknown bareword (a
        hallucinated relation name) does **not** error and is **not** empty -- the
        evaluator parses it as an atom literal that resolves to itself, an
        arity-0 singleton. So "non-empty" alone admits hallucinations; requiring
        arity >= 1 rejects them. (Confirming the name against the datum vocabulary
        is the complementary static check.)
        """
        return self.ok and not self.empty and self.arity >= 1

    @property
    def diagnostic(self) -> Optional[str]:
        """A short, human reason this selector isn't usable -- for repair feedback.

        Prefers the static analyzer's reason (it explains *why*: a provable empty, an
        arity or type mismatch), then falls back to what evaluation alone revealed.
        Returns ``None`` when the selector resolves cleanly -- nothing to repair.
        """
        if self.resolves:
            return None
        if self.static_reason:
            return self.static_reason
        if not self.ok:
            return f"did not evaluate ({self.error})" if self.error else "did not parse"
        if self.empty:
            return "resolved to the empty set on this example"
        if self.arity < 1:
            return (
                "resolved to an atom literal (arity 0), not a relation -- most likely "
                "an unknown or misspelled name"
            )
        return None


def _node_bin() -> Optional[str]:
    return os.environ.get("SPYTIAL_NODE") or shutil.which("node")


def _node_modules_dir() -> Optional[str]:
    """A ``node_modules`` dir containing ``spytial-core``, from the env override."""
    candidate = os.environ.get("SPYTIAL_CORE_NODE_PATH")
    if candidate and (Path(candidate) / "node_modules" / "spytial-core").is_dir():
        return str(Path(candidate) / "node_modules")
    return None


def _vendored_evaluator() -> Optional[str]:
    """The vendored self-contained evaluator shipped in the wheel, or None."""
    return str(_VENDORED_EVALUATOR) if _VENDORED_EVALUATOR.is_file() else None


def _resolve_core() -> Optional[dict]:
    """How the shim should load the evaluator, as env vars for the subprocess.

    Prefers an explicit ``SPYTIAL_CORE_NODE_PATH`` install (bare specifier resolved
    via ``NODE_PATH``) over the vendored file (required by absolute path). Returns
    ``None`` when neither is resolvable.
    """
    node_modules = _node_modules_dir()
    if node_modules is not None:
        return {"NODE_PATH": node_modules}
    vendored = _vendored_evaluator()
    if vendored is not None:
        return {"SPYTIAL_EVALUATOR_MODULE": vendored}
    return None


def is_available() -> bool:
    """Whether the bridge can run right now (node present and evaluator resolvable)."""
    return bool(_node_bin()) and _resolve_core() is not None and _SHIM.is_file()


def evaluate_selectors(datum, selectors: List[str]) -> List[SelectorVerdict]:
    """Evaluate ``selectors`` over ``datum`` headlessly; return one verdict each.

    ``datum`` is the object emitted by
    :meth:`spytial.provider_system.CnDDataInstanceBuilder.build_instance` (the
    ``{atoms, relations, types, rootId}`` shape). Raises
    :class:`EvaluatorUnavailable` if the bridge isn't runnable.
    """
    if not selectors:
        return []  # nothing to evaluate -- no bridge needed
    node = _node_bin()
    core_env = _resolve_core()
    if not node or core_env is None or not _SHIM.is_file():
        raise EvaluatorUnavailable(
            "headless selector evaluation needs a node runtime and a spytial-core "
            "evaluator. spytial ships a vendored evaluator, so normally only node is "
            "required (install it, or set SPYTIAL_NODE); to use your own spytial-core, "
            "set SPYTIAL_CORE_NODE_PATH to a dir containing node_modules/spytial-core."
        )

    env = {**os.environ, **core_env}
    payload = json.dumps({"datum": datum, "selectors": list(selectors)})
    try:
        proc = subprocess.run(
            [node, str(_SHIM)],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvaluatorUnavailable(f"node bridge failed to run: {exc}") from exc

    if not proc.stdout.strip():
        raise EvaluatorUnavailable(
            f"node bridge produced no output (exit {proc.returncode}): "
            f"{proc.stderr.strip()[:500]}"
        )
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise EvaluatorUnavailable(
            f"node bridge emitted non-JSON output (exit {proc.returncode}): "
            f"{proc.stdout.strip()[:500]}"
        ) from exc
    if not out.get("ok"):
        # The datum itself was rejected (e.g. failed to initialize) -- a bridge
        # failure, not a per-selector verdict.
        raise EvaluatorUnavailable(f"evaluator init failed: {out.get('error')}")

    return [_to_verdict(r) for r in out.get("results", [])]


def _to_verdict(r: dict) -> SelectorVerdict:
    threw = r.get("threw")
    is_error = bool(r.get("isError")) or threw is not None
    error = r.get("error") or threw
    static = r.get("static") or {}
    return SelectorVerdict(
        selector=r.get("selector", ""),
        ok=not is_error,
        empty=bool(r.get("empty")),
        arity=int(r.get("arity", 0)),
        error=error,
        pretty=r.get("pretty") if r.get("pretty") is not None else r.get("value"),
        static_status=static.get("status"),
        static_reason=static.get("reason"),
    )
