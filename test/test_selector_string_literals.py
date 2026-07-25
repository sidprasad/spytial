#!/usr/bin/env python3
"""Regression tests for string literals in selectors.

simple-graph-query 3.0 (vendored with spytial-core 4.1.0) changed what an
unresolved name means. In 2.x an identifier that matched nothing was silently
reinterpreted as a string, which made ``red`` a string only because nothing in the
instance happened to be named ``red``. In 3.0 it is the **empty relation**, and a
string must be written as a ``"..."`` literal.

Nothing throws when this is got wrong, which is the reason these tests exist. An
empty set satisfies a comparison vacuously, so an unquoted right-hand side leaves
a well-formed selector that quietly matches the wrong thing while the diagram
still renders:

* one empty side -> the comparison is false -> the directive stops applying;
* *both* sides empty -> the comparison is true -> the directive applies to
  everything.

The second is how a stale ``@:(x.field.name)`` join went from matching nothing
under 2.x to matching every atom under 3.0. See ``spytial/suggest/_vendor/README.md``.

Two layers here. :func:`test_no_unquoted_string_comparison_in_repo` is a lint over
the checked-in queries and needs no ``node``. The rest evaluate real selectors
through the headless bridge, and skip cleanly when ``node`` is absent.
"""

from __future__ import annotations

import enum
import pathlib
import re
from dataclasses import dataclass
from typing import Optional

import pytest

from spytial.provider_system import CnDDataInstanceBuilder
from spytial.suggest import _eval
from spytial.suggest.rules import enum_member_selector

requires_bridge = pytest.mark.skipif(
    not _eval.is_available(),
    reason="headless evaluator bridge unavailable (need a node runtime on PATH)",
)


# --------------------------------------------------------------------------- #
# Lint over the checked-in queries — always runs (no node required).
# --------------------------------------------------------------------------- #

# A `@:` label expression, a comparison, then a lone bare identifier. The trailing
# guard is what keeps legitimate right-hand sides out: a builtin call
# (`multiply[i, j]`), a join (`x.color`), or another label expression all continue
# past the identifier, and only a *lone* name can have been meant as a string.
#
# Deliberately not exhaustive — it is a lint, not a parser. It does not see a
# comparison written the other way round (`red = @:(x.color)`), one split across
# source lines, or a bare name that is really a bound comprehension variable
# (`{x : T, y : str | @:(x.c) = y}`, which would be a false positive). It catches
# the shape every site in this repo actually used, which is what stops the
# regression; the semantics below are what pin the behaviour.
_UNQUOTED_RHS = re.compile(
    r"@\w*:\s*(?:\([^)]*\)|[A-Za-z_][\w.]*)"  # @:(x.color) / @:s / @num:i2
    # `in` is a comparison too, and fails identically; it needs spaces around it
    # where the symbolic operators do not.
    r"(?:\s*(?:=|<=|>=|<|>)\s*|\s+in\s+)"
    r"([A-Za-z_]\w*)"  # a bare identifier...
    r"(?![\w\[.(])"  # ...that is not indexed, joined, or called
)

_SCANNED_ROOTS = ("demos", "docs", "spytial", "test")
_SCANNED_SUFFIXES = {".ipynb", ".md", ".py"}
# This file holds the 2.x spelling on purpose, as the lint's positive controls.
_EXEMPT = {pathlib.Path(__file__).name}


def _scanned_files():
    repo = pathlib.Path(__file__).resolve().parent.parent
    for root in _SCANNED_ROOTS:
        for path in sorted((repo / root).rglob("*")):
            # `site/` is built mkdocs output — a copy of docs/, not a source.
            if path.suffix not in _SCANNED_SUFFIXES or "site" in path.parts:
                continue
            if path.name in _EXEMPT:
                continue
            yield path.relative_to(repo), path


def test_no_unquoted_string_comparison_in_repo():
    """No checked-in query compares a label against a bare name.

    Covers the notebooks, the docs, the package, and the tests in one sweep, so a
    new demo cannot reintroduce the 2.x spelling. A *legitimate* bare right-hand
    side is possible in principle (a relation really named ``red``); if one ever
    lands, add it to an allowlist here with the reason rather than loosening the
    pattern.
    """
    offenders = [
        f"{rel}:{n}: {line.strip()[:90]}"
        for rel, path in _scanned_files()
        for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1)
        if _UNQUOTED_RHS.search(line)
    ]
    assert not offenders, "unquoted string comparison(s):\n" + "\n".join(offenders)


@pytest.mark.parametrize(
    "selector",
    [
        '{ x : RBNode | @:(x.color) = red }',
        '{ x : RBNode | @:(x.color) = RED }',
        '{s : str | @:s = red or @:s = black}',
        '@:(x.status) = active }}',  # inside an f-string, as docs/suggest.md had it
        '{ x : RBNode | @:(x.color)=red }',  # no whitespace
        '{ x : RBNode | @:(x.status) in active }',  # `in` fails the same way
        '{ x : RBNode | not @:(x.color) = red }',
    ],
)
def test_lint_catches_the_2x_spelling(selector):
    """Positive controls: the exact forms migrated out of this repo must still trip."""
    assert _UNQUOTED_RHS.search(selector)


@pytest.mark.parametrize(
    "selector",
    [
        '{ x : RBNode | @:(x.color) = "red" }',  # the migrated form
        '{s : str | @:s = "red" or @:s = "black"}',
        "@num:i2 = multiply[i0, i1]",  # a builtin still resolves
        "{ x : T, y : T | @:(x.a) = @:(y.b) }",  # label against label
        "{ x : T | @:x = x.color }",  # a join, not a bareword
        "{ x : T | @:(x.key) = 10 }",  # a number
        '{ x : %s | @:(x.%s) = "%s" }',  # the rules.py template
    ],
)
def test_lint_passes_legitimate_right_hand_sides(selector):
    """Negative controls, so the lint cannot start failing honest queries."""
    assert not _UNQUOTED_RHS.search(selector)


# --------------------------------------------------------------------------- #
# Real evaluation — runs only when the bridge is present.
# --------------------------------------------------------------------------- #


@dataclass
class Task:
    """Three tasks whose labels exercise a space, punctuation, and separators."""

    label: str = "todo"
    nxt: Optional["Task"] = None


def _task_datum():
    a, b, c = Task("in progress"), Task("done!"), Task("a-b_c")
    a.nxt, b.nxt = b, c
    return CnDDataInstanceBuilder().build_instance(a)


def _verdicts(datum, selectors):
    return {v.selector: v for v in _eval.evaluate_selectors(datum, selectors)}


@requires_bridge
def test_double_quoted_string_matches_the_right_atoms():
    """The migrated spelling resolves, and to one specific atom rather than all of them."""
    datum = _task_datum()
    by = _verdicts(
        datum,
        [
            '{ x : Task | @:(x.label) = "in progress" }',
            '{ x : Task | @:(x.label) = "done!" }',
            '{ x : Task | @:(x.label) = "a-b_c" }',
        ],
    )
    assert all(v.resolves for v in by.values())
    # Each literal picks out exactly one of the three tasks -- a selector that
    # matched every atom would also be "non-empty", so check the results differ.
    assert len({v.pretty for v in by.values()}) == 3
    assert all(v.arity == 1 for v in by.values())


@requires_bridge
def test_unquoted_string_is_the_empty_relation():
    """The 2.x spelling now matches nothing -- and does so without erroring.

    This is the whole failure mode the migration exists to fix: `ok` stays True, so
    only `empty`/`resolves` reveal it.
    """
    (v,) = _eval.evaluate_selectors(
        _task_datum(), ["{ x : Task | @:(x.label) = todo }"]
    )
    assert v.ok is True  # parses and evaluates -- fails quietly
    assert v.empty is True and v.resolves is False


@requires_bridge
def test_single_quoted_string_is_a_parse_error():
    """Only double quotes make a string literal.

    Worth pinning because ``'...'`` is the tempting way to dodge escaping when the
    selector already sits inside a Python double-quoted string. It does not parse,
    so unlike the unquoted case it fails loudly.
    """
    (v,) = _eval.evaluate_selectors(
        _task_datum(), ["{ x : Task | @:(x.label) = 'done!' }"]
    )
    assert v.ok is False and v.resolves is False
    assert v.error


@requires_bridge
def test_quoted_literal_that_matches_nothing_is_empty_not_an_error():
    """A well-formed literal with no match is data-dependent emptiness, not a syntax fault.

    Keeps the two empties distinguishable: this one means "no such value in the
    instance", which is legitimate, while a parse error means the query is wrong.
    """
    (v,) = _eval.evaluate_selectors(
        _task_datum(), ['{ x : Task | @:(x.label) = "no-such-label" }']
    )
    assert v.ok is True and v.empty is True
    assert v.error is None


@requires_bridge
def test_disjunction_of_literals_matches_every_named_value():
    """The `hideAtom` shape the demo notebooks use, over the `str` atoms themselves."""
    (v,) = _eval.evaluate_selectors(
        _task_datum(), ['{s : str | @:s = "in progress" or @:s = "done!"}']
    )
    assert v.resolves and v.arity == 1
    assert "in progress" in v.pretty and "done!" in v.pretty
    assert "a-b_c" not in v.pretty  # the third label is not named, so not matched


# --------------------------------------------------------------------------- #
# The selector `suggest` generates for an enum member.
# --------------------------------------------------------------------------- #


class Color(enum.Enum):
    RED = "red"
    BLACK = "black"


class Level(enum.IntEnum):
    LOW = 1
    HIGH = 2


@dataclass
class Node:
    color: Color = Color.BLACK
    level: Level = Level.LOW


@requires_bridge
@pytest.mark.parametrize(
    "field, member, other",
    [("color", "RED", "BLACK"), ("level", "HIGH", "LOW")],
)
def test_enum_selector_matches_a_real_enum_instance(field, member, other):
    """What :func:`enum_member_selector` returns must actually match, on real data.

    The form encodes two claims that a string-equality test cannot check -- that the
    member name is readable off the field, and that quoting it is right -- so this
    evaluates the generated selector instead of comparing it to a literal. Both
    enum flavours are covered because the relationalizer treats them alike.
    """
    datum = CnDDataInstanceBuilder().build_instance(
        [Node(Color.RED, Level.HIGH), Node(Color.BLACK, Level.LOW)]
    )
    hit = _eval.evaluate_selectors(datum, [enum_member_selector("Node", field, member)])[0]
    miss = _eval.evaluate_selectors(datum, [enum_member_selector("Node", field, other)])[0]

    assert hit.resolves and hit.arity == 1
    assert miss.resolves and miss.arity == 1
    # One node each -- not both, which is what a vacuously-true comparison yields.
    assert hit.pretty != miss.pretty


@requires_bridge
def test_stale_name_join_would_match_everything():
    """Why the ``.name`` join had to go, pinned as an executable fact.

    ``x.color.name`` is empty (no such relation is emitted), so comparing it to a
    bare name compares two empty sides, which is *true* for every atom. That is a
    directive silently applied to the whole diagram, and it is strictly worse than
    the not-applying case -- so this documents the trap rather than leaving the next
    reader to rediscover it.
    """
    datum = CnDDataInstanceBuilder().build_instance(
        [Node(Color.RED, Level.HIGH), Node(Color.BLACK, Level.LOW)]
    )
    by = _verdicts(
        datum,
        [
            "{ x : Node | @:(x.color.name) = RED }",  # two empty sides -> matches all
            '{ x : Node | @:(x.color.name) = "RED" }',  # one empty side -> matches none
            '{ x : Node | @:(x.color) = "RED" }',  # the form actually shipped
        ],
    )
    everything = by["{ x : Node | @:(x.color.name) = RED }"]
    nothing = by['{ x : Node | @:(x.color.name) = "RED" }']
    correct = by['{ x : Node | @:(x.color) = "RED" }']

    def matched(v):
        return len(v.pretty.split(",")) if v.pretty else 0

    # All three are unary comprehensions, so `arity` cannot tell them apart -- only
    # how many atoms came back does. Two empty sides match both nodes; one empty
    # side matches neither; the shipped form matches the one red node.
    assert everything.ok and not everything.empty and matched(everything) == 2
    assert nothing.ok and nothing.empty
    assert correct.resolves and matched(correct) == 1
