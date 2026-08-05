"""Bridge to spytial-core's conformance harness -- what a decorator's spec *entails*.

A spytial spec does not describe a picture. It describes a set of spatial
relationships, and infinitely many drawings satisfy any one of them: shift
everything 40px, change the spacing, let the force simulation settle differently
on another machine, all still correct. So a test that compares images or asserts
on coordinates is testing the renderer, not this library -- it fails when nothing
is wrong, passes when something is, and needs a browser to do either.

What spytial is answerable for is narrower, and neither half needs rendering:

1. does ``build_instance`` turn a Python value into a well-formed graph?
2. do the decorators emit a spec that **entails** what their author meant?

The solver has already worked out what a spec entails by the time layout
generation finishes. The harness just asks it. That is why an assertion is
written over ``must.leftOf(n0)`` -- true in *every* layout the spec permits --
rather than over where a node happened to land.

Running it
----------
``spytial-check`` reads case documents on stdin and writes a JSON verdict to
stdout; engine chatter goes to stderr. It is vendored at
``_vendor/spytial-check.js`` from the same spytial-core release everything else
here pins, since a harness from one release checking specs written against
another is the drift the vendoring exists to prevent, arriving through the thing
meant to catch it. :func:`run_cases` refuses a result that disagrees with the
pin, or one whose ``formatVersion`` it does not recognize.

``node`` is resolved through :mod:`spytial.suggest._eval`, the bridge that
already does this for tier-2 selector validation, so there is one chain and not
two. ``SPYTIAL_CORE_NODE_PATH`` points both halves at the same install. Absent
``node``, :data:`NODE` is ``None`` and :data:`requires_harness` skips -- a plain
``pip install`` still tests clean.

What it catches that a format test cannot
-----------------------------------------
The datum check runs on the raw dict, *before* ``JSONDataInstance`` sees it. The
data instance normalizes as it loads: it dedupes atoms and treats reference
validation as a repair step. So a duplicated id lays out fine and quietly loses
a value, and a dangling tuple surfaces much later as ``Atom with ID 'ghost' not
found``, naming no tuple. Checked first, the same bug reports as
``relations[0].tuples[0].atoms[1]``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

import spytial
from spytial.core_assets import SPYTIAL_CORE_VERSION
from spytial.suggest import _eval

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


NODE = _eval._node_bin()
CHECK_BIN = _harness_bin()

requires_harness = pytest.mark.skipif(
    not NODE or not CHECK_BIN,
    reason="conformance harness needs a node runtime on PATH "
    "(set SPYTIAL_NODE to override)",
)


def case(name, obj, assertions=None, *, note=None, skip_datum_check=False):
    """A conformance case for ``obj``: datum, the spec its decorators emit, the facts.

    Both halves are ordinary public API -- this only puts them in the shape the
    harness reads. Pass ``assertions=None`` to check the datum alone.
    """
    doc = {
        "name": name,
        "datum": spytial.CnDDataInstanceBuilder().build_instance(obj),
        "spec": spytial.serialize_to_yaml_string(spytial.collect_decorators(obj)),
        "assertions": list(assertions or []),
    }
    if note is not None:
        doc["note"] = note
    if skip_datum_check:
        doc["skipDatumCheck"] = True
    return doc


def run_cases(cases):
    """Run ``cases`` through the harness and return its ``RunResult``.

    Raises :class:`RuntimeError` when the harness never reached a verdict, which
    is a different thing from cases that failed and must not be reported as one.
    """
    if not NODE or not CHECK_BIN:
        raise RuntimeError("conformance harness unavailable (no node runtime)")

    payload = json.dumps({"cases": list(cases)})
    try:
        proc = subprocess.run(
            [NODE, CHECK_BIN, "--timeout", str(_TIMEOUT_S), "-"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S + 30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"spytial-check failed to run: {exc}") from exc

    # 0 and 1 mean the harness has an answer; 2 (bad usage or unreadable input)
    # and 3 (timed out) mean it does not, and stdout is empty. The split to
    # branch on is 0/1 versus 2/3, not zero versus non-zero: treating every
    # non-zero code as "cases failed" reports a mistyped path as a spec that
    # does not hold.
    if proc.returncode >= 2:
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

    _check_provenance(result)
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


def run_case(name, obj, assertions=None, **kwargs):
    """Run one case and return its ``CaseResult``, passing or failing."""
    return run_cases([case(name, obj, assertions, **kwargs)])["cases"][0]


def check(name, obj, assertions=None, **kwargs):
    """Assert that ``obj``'s decorators entail ``assertions``. Returns the result.

    A failure names the diagnostics and the assertions that did not hold, with
    each assertion's ``because`` carried through, so a red test says what claim
    about the decorators stopped being true.
    """
    result = run_case(name, obj, assertions, **kwargs)
    if not result["ok"]:
        pytest.fail(explain(result), pytrace=False)
    return result


def explain(result):
    """A readable account of why a case failed."""
    lines = [f"conformance case {result['name']!r} failed"]
    for diagnostic in result.get("errors", []):
        where = f" at {diagnostic['where']}" if diagnostic.get("where") else ""
        lines.append(f"  [{diagnostic['code']}]{where}: {diagnostic['message']}")
    for assertion in result.get("assertions", []):
        if assertion.get("ok"):
            continue
        lines.append(f"  {assertion['query']}: {assertion.get('message', 'failed')}")
        lines.append(f"    got: {', '.join(assertion['actual']) or '(empty)'}")
        if assertion.get("because"):
            lines.append(f"    expected because: {assertion['because']}")
    return "\n".join(lines)


def codes(result):
    """The error diagnostic codes on a result, as a set -- stable across releases."""
    return {diagnostic["code"] for diagnostic in result.get("errors", [])}
