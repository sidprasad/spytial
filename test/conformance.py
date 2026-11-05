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
``spytial/_vendor/spytial-check.js`` from the same spytial-core release everything else
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

import pytest

import spytial
from spytial.core_assets import SPYTIAL_CORE_VERSION
from spytial.suggest import _eval

# Shared with suggest; tests exercise the same published core bridge.
from spytial._conformance import (
    SUPPORTED_FORMAT_VERSION,
    _check_provenance,
    _harness_bin,
    run_cases,
)

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
