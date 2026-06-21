"""The input side accepts ANY value, not just dataclasses.

Covers the generalization tracked in sidprasad/spytial#113:

* ``spytial.reify`` / ``spytial.replit`` are exported and invert
  ``build_instance`` for builtins, arbitrary classes, and dataclasses.
* ``_generate_cnd_spec`` no longer requires a dataclass.
* the HTML path (``edit_html``) and the live ``Editor`` / ``edit`` verb accept
  any value.
"""

import os
from dataclasses import dataclass
from typing import Optional

import pytest

import spytial
from spytial.provider_system import CnDDataInstanceBuilder
from spytial.structured_input import _generate_cnd_spec


# ---------------------------------------------------------------------------
# Top-level reify / replit exports (the inverse of diagram)
# ---------------------------------------------------------------------------


def test_reify_replit_are_exported():
    for name in ("reify", "replit", "edit", "edit_html", "Editor", "EditCancelled"):
        assert hasattr(spytial, name), f"spytial.{name} should be exported"
        assert name in spytial.__all__


def test_legacy_names_are_gone():
    # Clean break: the dataclass-only names were removed, not aliased.
    for name in ("dataclass_builder", "DataClassBuilder"):
        assert not hasattr(spytial, name), f"spytial.{name} should be removed"
        assert name not in spytial.__all__


@pytest.mark.parametrize(
    "value",
    [
        {"nums": [1, 2, 3], "meta": {"k": "v"}},
        [1, 2, [3, 4]],
        (1, "x", None),
        "plain string",
        42,
    ],
)
def test_toplevel_reify_round_trips_builtins(value):
    di = CnDDataInstanceBuilder().build_instance(value)
    assert spytial.reify(di) == value


def test_toplevel_replit_matches_repr_for_builtins():
    value = {"nums": [1, 2, 3], "tag": "hi"}
    di = CnDDataInstanceBuilder().build_instance(value)
    assert spytial.replit(di) == repr(value)


@dataclass
class Point:
    x: int = 0
    y: int = 0


def test_toplevel_reify_round_trips_dataclass():
    di = CnDDataInstanceBuilder().build_instance(Point(3, 4))
    out = spytial.reify(di)
    assert isinstance(out, Point) and out == Point(3, 4)


class Vec:
    """Plain (non-dataclass) class — reify rebuilds the real type."""

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Vec<{self.x},{self.y}>"


def test_toplevel_reify_rebuilds_arbitrary_class():
    di = CnDDataInstanceBuilder().build_instance(Vec(1, 2))
    out = spytial.reify(di)
    assert type(out) is Vec
    assert repr(out) == "Vec<1,2>"


# ---------------------------------------------------------------------------
# The spec generator and the editors accept any value (no dataclass gate)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [{"a": 1}, [1, 2], Vec(1, 2), Point(1, 2), 5, "s"])
def test_generate_cnd_spec_accepts_any_value(value):
    # Must not raise; unannotated values yield an (empty) constraints/directives spec.
    spec = _generate_cnd_spec(value)
    assert "constraints" in spec and "directives" in spec


@pytest.mark.parametrize(
    "value",
    [{"a": 1, "b": [1, 2]}, [1, 2, 3], Vec(7, 8), Point(1, 2)],
)
def test_html_edit_accepts_any_value(value):
    # The pyodide/HTML path used to raise on non-dataclasses; now it renders.
    path = spytial.edit_html(value, method="browser", auto_open=False)
    try:
        assert path and os.path.exists(path)
        html = open(path, encoding="utf-8").read()
        assert "structured-input-graph" in html
    finally:
        if path and os.path.exists(path):
            os.remove(path)


# The server-based edit() verb (blocks on a browser interaction) is covered in
# test_edit_server.py, which exercises its pieces without opening a browser.
