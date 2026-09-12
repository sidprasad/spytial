"""Server-side strings must survive the trip into the page unchanged.

A spec is written by PyYAML and read by js-yaml, with a `<script>` in between.
Everything here is about that gap. The templates used to interpolate the spec
into a JavaScript *template literal*, which is a quoting context that rewrites
what passes through it: a backslash escapes the next character, `${` opens an
interpolation, and a backtick ends the string. PyYAML writes a multi-line
string as a double-quoted scalar containing `\\n`, JavaScript turned those two
characters back into a real newline, and the diagram failed to lay out with a
YAML error pointing at a line nobody wrote.

Nothing in a spec contained a backslash until `source` blocks began carrying
decorators exactly as written, so the tests below are mostly about text that
looks like syntax.
"""

from __future__ import annotations

import json
import re

import pytest

yaml = pytest.importorskip("yaml")
pytest.importorskip("jinja2")

import spytial  # noqa: E402  (after the importorskip guards above)
from spytial._templating import js_literal  # noqa: E402
from spytial.visualizer import _generate_visualizer_html  # noqa: E402

EMPTY_DATUM = {"atoms": [], "relations": [], "types": []}


def _embedded_spec(html):
    """The spec as the browser's JavaScript parser will reconstruct it.

    The literal is JSON, and JSON string syntax is a subset of JavaScript's,
    so `json.loads` reads exactly what the browser will.
    """
    match = re.search(r"const cndSpec = (\".*?\");\n", html, re.S)
    assert match, "the spec is no longer embedded as a JavaScript string literal"
    return json.loads(match.group(1))


def _round_trip(obj):
    spec = spytial.serialize_to_yaml_string(spytial.collect_decorators(obj))
    html = _generate_visualizer_html(EMPTY_DATUM, spec)
    return spec, _embedded_spec(html)


def test_a_multi_line_decorator_reaches_the_browser_intact():
    """The regression: every multi-line decorator broke the whole diagram."""

    @spytial.orientation(
        selector="{x : Node, y : Node | y in x.kids}",
        directions=["below"],
    )
    class Node:
        def __init__(self):
            self.kids = []

    written, received = _round_trip(Node())
    assert received == written
    assert yaml.safe_load(received)["constraints"], "must parse where js-yaml will"


def test_text_that_looks_like_javascript_syntax_is_inert():
    """A backtick ends a template literal and `${` opens an interpolation."""

    @spytial.orientation(
        selector="{x : Node | x.name = `${danger}` }",
        directions=["below"],
    )
    class Node:
        pass

    written, received = _round_trip(Node())
    assert received == written
    parsed = yaml.safe_load(received)
    assert "${danger}" in parsed["constraints"][0]["orientation"]["selector"]


def test_the_literal_cannot_end_the_script_element():
    """`</script>` closes the element whatever the string syntax says."""
    assert "</script>" not in js_literal("a </script> b")
    assert json.loads(js_literal("a </script> b")) == "a </script> b"


@pytest.mark.parametrize(
    "value",
    [
        "plain",
        "with \\ backslash",
        'with "double" quotes',
        "with 'single' quotes",
        "line\nbreak",
        "tab\there",
        "`backtick` and ${interp}",
        "</script><script>alert(1)</script>",
        "unicode:     é 中",
        "",
    ],
)
def test_js_literal_round_trips_anything(value):
    """Whatever a decorator contains, the page must read it back unchanged."""
    assert json.loads(js_literal(value)) == value


def test_js_literal_escapes_the_line_separators_older_engines_break_on():
    """U+2028 and U+2029 are legal in JSON but terminate a line in JavaScript."""
    literal = js_literal("a b c")
    assert " " not in literal and " " not in literal
    assert json.loads(literal) == "a b c"


def test_the_spec_is_not_embedded_in_a_template_literal():
    """The shape of the bug, pinned directly.

    A future edit that puts the interpolation back inside backticks would pass
    every value-level test above while breaking the page again.
    """
    from pathlib import Path

    for name in (
        "visualizer_template.html",
        "sequence_visualizer_template.html",
        "input_template.html",
    ):
        source = (Path(spytial.__file__).parent / name).read_text(encoding="utf-8")
        assert "`{{" not in source, f"{name} interpolates into a template literal"
