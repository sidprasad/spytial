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
``node`` is found on ``PATH`` (override with ``SPYTIAL_NODE``). ``spytial-core``
is resolved via ``NODE_PATH``: set ``SPYTIAL_CORE_NODE_PATH`` to a directory that
contains ``node_modules/spytial-core`` (e.g. ``npm install spytial-core`` in a
cache dir). Shipping a vendored copy in the wheel so this Just Works for a plain
``pip install`` is a deliberate follow-up, not a blocker for the feature.
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


def _node_bin() -> Optional[str]:
    return os.environ.get("SPYTIAL_NODE") or shutil.which("node")


def _node_path() -> Optional[str]:
    """A directory containing ``node_modules/spytial-core``, or None."""
    candidate = os.environ.get("SPYTIAL_CORE_NODE_PATH")
    if candidate and (Path(candidate) / "node_modules" / "spytial-core").is_dir():
        return str(Path(candidate) / "node_modules")
    return None


def is_available() -> bool:
    """Whether the bridge can run right now (node present and core resolvable)."""
    return bool(_node_bin()) and _node_path() is not None and _SHIM.is_file()


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
    node_path = _node_path()
    if not node or node_path is None or not _SHIM.is_file():
        raise EvaluatorUnavailable(
            "headless selector evaluation needs node and a resolvable spytial-core; "
            "set SPYTIAL_CORE_NODE_PATH to a dir containing node_modules/spytial-core "
            "(npm install spytial-core)."
        )

    env = {**os.environ, "NODE_PATH": node_path}
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
    return SelectorVerdict(
        selector=r.get("selector", ""),
        ok=not is_error,
        empty=bool(r.get("empty")),
        arity=int(r.get("arity", 0)),
        error=error,
        pretty=r.get("pretty") if r.get("pretty") is not None else r.get("value"),
    )
