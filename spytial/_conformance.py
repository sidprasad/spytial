"""Run the released core conformance checker without reimplementing its semantics.

Shared by suggest's datum-specific comparison strategy and integration tests.
The bundled CLI is copied unchanged from the same release as the renderer.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .core_assets import SPYTIAL_CORE_VERSION
from .suggest import _eval

# The case/result JSON contract this file is written against. spytial-core
# moves it when an incompatible change lands, and a host that guesses at an
# unfamiliar shape reports nonsense, so refuse instead.
SUPPORTED_FORMAT_VERSION = 1

_VENDORED_CHECK = Path(__file__).parent / "_vendor" / "spytial-check.js"

# Generous: a case is a few milliseconds of layout generation. This exists so a
# pathological spec fails the suite instead of hanging it.
_TIMEOUT_S = 120


def _harness_bin():
    """The ``spytial-check`` bin, or ``None``.

    Mirrors :func:`spytial.suggest._eval._resolve_core`: an explicit
    ``SPYTIAL_CORE_NODE_PATH`` install wins, so a power user running against
    their own spytial-core gets that build's harness too, and the vendored copy
    is the default that needs no npm install.
    """
    override = os.environ.get("SPYTIAL_CORE_NODE_PATH")
    if override:
        installed = (
            Path(override)
            / "node_modules"
            / "spytial-core"
            / "dist"
            / "cli"
            / "spytial-check.js"
        )
        if installed.is_file():
            return str(installed)
    return str(_VENDORED_CHECK) if _VENDORED_CHECK.is_file() else None


def run_cases(cases, *, timeout=_TIMEOUT_S):
    """Run ``cases`` through the harness and return its ``RunResult``.

    Raises :class:`RuntimeError` when the harness never reached a verdict, which
    is a different thing from cases that failed and must not be reported as one.
    """
    node, check_bin = _eval._node_bin(), _harness_bin()
    if not node or not check_bin:
        raise RuntimeError("conformance harness unavailable (no node runtime)")

    documents = list(cases)
    payload = json.dumps({"cases": documents})
    try:
        proc = subprocess.run(
            [node, check_bin, "--timeout", str(timeout), "-"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"spytial-check failed to run: {exc}") from exc

    # 0 and 1 mean the harness has an answer; 2 (bad usage or unreadable input)
    # and 3 (timed out) mean it does not, and stdout is empty. The split to
    # branch on is 0/1 versus 2/3, not zero versus non-zero: treating every
    # non-zero code as "cases failed" reports a mistyped path as a spec that
    # does not hold.
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"spytial-check did not reach a verdict (exit {proc.returncode}): "
            f"{proc.stderr.strip()[:1000]}"
        )
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"spytial-check emitted non-JSON output (exit {proc.returncode}): "
            f"{proc.stdout.strip()[:500]}"
        ) from exc

    return _validate_result(documents, result)


def _validate_result(documents, result):
    """Validate the same result contract for one-shot and persistent transports."""
    if not isinstance(result, dict):
        raise RuntimeError("spytial-check returned an invalid result.")
    _check_provenance(result)
    results = result.get("cases")
    if not isinstance(results, list) or len(results) != len(documents):
        raise RuntimeError("spytial-check returned the wrong number of cases.")
    for document, verdict in zip(documents, results):
        if not isinstance(verdict, dict) or verdict.get("name") != document["name"]:
            raise RuntimeError("spytial-check returned mismatched cases.")
        if not isinstance(verdict.get("ok"), bool) or any(
            not isinstance(verdict.get(key), list)
            for key in ("errors", "warnings", "assertions")
        ):
            raise RuntimeError("spytial-check returned an invalid verdict.")
    return result


def _check_provenance(result):
    """Refuse a verdict from an unfamiliar contract or a stale harness."""
    got_format = result.get("formatVersion")
    if got_format != SUPPORTED_FORMAT_VERSION:
        raise RuntimeError(
            f"spytial-check speaks conformance format {got_format}, this bridge "
            f"reads {SUPPORTED_FORMAT_VERSION}. Re-read the case/result contract "
            f"before trusting these results."
        )
    got_version = result.get("spytialCoreVersion")
    if got_version != SPYTIAL_CORE_VERSION:
        raise RuntimeError(
            f"the conformance harness is spytial-core {got_version} but this repo "
            f"pins {SPYTIAL_CORE_VERSION}. A harness from one release checking "
            f"specs written against another proves nothing. Run "
            f"./update-spytial-core.sh."
        )
