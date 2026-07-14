"""
Tests for the spytial-core 3.0 style system: edgeStyle/atomStyle directives,
the LineStyle/TextStyle/BorderStyle/FillStyle/GroupEdge style blocks, and the
Python-side desugaring of the legacy edgeColor/atomColor/inferredEdge-inline
forms.
"""

import warnings

import pytest
from typing import Annotated

import spytial
from spytial import (
    LineStyle,
    TextStyle,
    BorderStyle,
    FillStyle,
    GroupEdge,
    collect_decorators,
    serialize_to_yaml_string,
)


# --------------------------------------------------------------------------- #
# Serialization goldens: the new API through all three entry points
# --------------------------------------------------------------------------- #


def _directives(obj):
    return collect_decorators(obj)["directives"]


EDGE_STYLE_ENTRY = {
    "edgeStyle": {
        "field": "next",
        "lineStyle": {"color": "crimson", "pattern": "dashed", "weight": 2},
        "textStyle": {"size": "small", "color": "gray"},
        "showLabel": True,
    }
}

ATOM_STYLE_ENTRY = {
    "atomStyle": {
        "selector": "Node",
        "fillStyle": {"color": "#eef6ff"},
        "borderStyle": {"color": "steelblue", "width": 2},
        "textStyle": {"size": "large"},
    }
}


def test_edge_style_class_decorator():
    @spytial.edgeStyle(
        field="next",
        lineStyle=LineStyle(color="crimson", pattern="dashed", weight=2),
        textStyle=TextStyle(size="small", color="gray"),
        showLabel=True,
    )
    class T:
        pass

    assert _directives(T()) == [EDGE_STYLE_ENTRY]


def test_atom_style_class_decorator():
    @spytial.atomStyle(
        selector="Node",
        fillStyle=FillStyle(color="#eef6ff"),
        borderStyle=BorderStyle(color="steelblue", width=2),
        textStyle=TextStyle(size="large"),
    )
    class T:
        pass

    assert _directives(T()) == [ATOM_STYLE_ENTRY]


def test_per_object_annotate():
    obj = [1, 2, 3]
    spytial.annotate_edgeStyle(obj, field="items", lineStyle=LineStyle(color="teal"))
    spytial.annotate_atomStyle(obj, borderStyle=BorderStyle(color="plum"))
    assert _directives(obj) == [
        {"edgeStyle": {"field": "items", "lineStyle": {"color": "teal"}}},
        {"atomStyle": {"borderStyle": {"color": "plum"}}},
    ]


def test_annotated_classes():
    X = Annotated[
        list,
        spytial.EdgeStyle(field="next", lineStyle=LineStyle(color="red")),
        spytial.AtomStyle(selector="self", fillStyle=FillStyle(color="mistyrose")),
    ]
    extracted = spytial.extract_spytial_annotations(X)
    assert extracted["directives"] == [
        {"edgeStyle": {"field": "next", "lineStyle": {"color": "red"}}},
        {"atomStyle": {"selector": "self", "fillStyle": {"color": "mistyrose"}}},
    ]


def test_inferred_edge_blocks():
    @spytial.inferredEdge(
        name="ancestor",
        selector="^parent",
        lineStyle=LineStyle(color="gray", pattern="dotted"),
        textStyle=TextStyle(color="gray"),
    )
    class T:
        pass

    assert _directives(T()) == [
        {
            "inferredEdge": {
                "name": "ancestor",
                "selector": "^parent",
                "lineStyle": {"color": "gray", "pattern": "dotted"},
                "textStyle": {"color": "gray"},
            }
        }
    ]


def test_attribute_and_tag_text_size():
    @spytial.attribute(field="weight", textSize="small")
    @spytial.tag(toTag="Person", name="age", value="age", textSize="large")
    class T:
        pass

    assert _directives(T()) == [
        {"tag": {"toTag": "Person", "name": "age", "value": "age", "textSize": "large"}},
        {"attribute": {"field": "weight", "textSize": "small"}},
    ]


def test_yaml_emits_nested_blocks():
    @spytial.edgeStyle(field="next", lineStyle=LineStyle(color="red", pattern="dashed"))
    class T:
        pass

    yaml_out = serialize_to_yaml_string(collect_decorators(T()))
    assert "edgeStyle:" in yaml_out
    assert "lineStyle:" in yaml_out
    assert "pattern: dashed" in yaml_out


# --------------------------------------------------------------------------- #
# Style blocks and equivalent plain dicts produce identical entries
# --------------------------------------------------------------------------- #


def test_dict_escape_hatch_equivalent():
    @spytial.edgeStyle(
        field="next",
        lineStyle={"color": "crimson", "pattern": "dashed", "weight": 2},
        textStyle={"size": "small", "color": "gray"},
        showLabel=True,
    )
    class FromDicts:
        pass

    assert _directives(FromDicts()) == [EDGE_STYLE_ENTRY]


# --------------------------------------------------------------------------- #
# Legacy desugaring
# --------------------------------------------------------------------------- #


def test_edge_color_desugars():
    with pytest.deprecated_call():
        deco = spytial.edgeColor(
            field="next", value="red", style=" Dashed ", weight=3, showLabel=False
        )

    @deco
    class T:
        pass

    # style normalizes like core's normalizeEdgeStyle (trim + lowercase)
    assert _directives(T()) == [
        {
            "edgeStyle": {
                "field": "next",
                "lineStyle": {"color": "red", "pattern": "dashed", "weight": 3},
                "showLabel": False,
            }
        }
    ]


def test_atom_color_desugars_to_border():
    with pytest.deprecated_call():
        deco = spytial.atomColor(selector="Node", value="blue")

    @deco
    class T:
        pass

    # Border-preserving mapping: legacy value colored the border, not the fill.
    assert _directives(T()) == [
        {"atomStyle": {"selector": "Node", "borderStyle": {"color": "blue"}}}
    ]


def test_inferred_edge_inline_desugars():
    with pytest.deprecated_call():
        deco = spytial.inferredEdge(
            name="anc", selector="^parent", color="gray", style="dotted", weight=2
        )

    @deco
    class T:
        pass

    assert _directives(T()) == [
        {
            "inferredEdge": {
                "name": "anc",
                "selector": "^parent",
                "lineStyle": {"color": "gray", "pattern": "dotted", "weight": 2},
            }
        }
    ]


def test_inferred_edge_inline_and_block_conflict():
    with pytest.raises(ValueError, match="both"):
        spytial.inferredEdge(
            name="anc", selector="^parent", color="gray", lineStyle=LineStyle(color="red")
        )


def test_legacy_invalid_style_drops_with_warning():
    """A 2.10-era spec with a bad style must keep rendering, not start raising."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        @spytial.edgeColor(field="x", value="red", style="wavy")
        class T:
            pass

    assert any(
        issubclass(w.category, UserWarning) and "wavy" in str(w.message) for w in caught
    )
    assert _directives(T()) == [
        {"edgeStyle": {"field": "x", "lineStyle": {"color": "red"}}}
    ]


def test_legacy_missing_value_still_raises_legacy_message():
    with pytest.raises(ValueError, match="edgeColor.*value"):
        spytial.edgeColor(field="x")


def test_deprecation_warns_once_per_authoring_site():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        deco = spytial.edgeColor(field="next", value="red")

        @deco
        class A:
            pass

        @deco
        class B:
            pass

    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1


def test_deprecation_per_entry_point():
    with pytest.deprecated_call():
        spytial.annotate_edgeColor([1], field="items", value="red")
    with pytest.deprecated_call():
        spytial.annotate_atomColor([1], selector="items", value="red")
    with pytest.deprecated_call():
        spytial.EdgeColor(field="n", value="red")
    with pytest.deprecated_call():
        spytial.AtomColor(selector="n", value="red")
    with pytest.deprecated_call():
        IntPair = tuple[int, int]
        spytial.annotate_type_alias(IntPair, "edgeColor", field="items", value="red")
    spytial.clear_type_alias_annotations()


def test_deprecated_classes_emit_new_entries():
    with pytest.deprecated_call():
        entry = spytial.EdgeColor(field="n", value="red", style="dashed").to_entry()
    assert entry == {
        "edgeStyle": {"field": "n", "lineStyle": {"color": "red", "pattern": "dashed"}}
    }
    with pytest.deprecated_call():
        entry = spytial.AtomColor(selector="s", value="blue").to_entry()
    assert entry == {"atomStyle": {"selector": "s", "borderStyle": {"color": "blue"}}}


# --------------------------------------------------------------------------- #
# Dedup across authoring forms
# --------------------------------------------------------------------------- #


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_cross_form_dedup():
    """Legacy, dict, and dataclass forms of the same rule collapse to one entry."""

    @spytial.edgeColor(field="n", value="red")
    class Parent:
        pass

    @spytial.edgeStyle(field="n", lineStyle=LineStyle(color="red"))
    class Child(Parent):
        pass

    obj = Child()
    spytial.annotate_edgeStyle(obj, field="n", lineStyle={"color": "red"})
    assert _directives(obj) == [
        {"edgeStyle": {"field": "n", "lineStyle": {"color": "red"}}}
    ]


# --------------------------------------------------------------------------- #
# Strict validation at construction
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad_call",
    [
        lambda: LineStyle(pattern="wavy"),
        lambda: LineStyle(weight=0),
        lambda: LineStyle(weight=-1),
        lambda: TextStyle(size="huge"),
        lambda: BorderStyle(width=0),
        lambda: GroupEdge(points="both"),
        lambda: spytial.edgeStyle(field="x", lineStyle={"colour": "red"}),
        lambda: spytial.edgeStyle(field="x", lineStyle="red"),
        lambda: spytial.atomStyle(borderStyle={"width": -2}),
        lambda: spytial.attribute(field="x", textSize="mega"),
        lambda: spytial.tag(toTag="T", name="n", value="v", textSize="mega"),
        lambda: spytial.group(selector="s", name="g", addEdge="sideways"),
    ],
)
def test_invalid_style_input_raises(bad_call):
    with pytest.raises(ValueError):
        bad_call()


# --------------------------------------------------------------------------- #
# Mutation safety
# --------------------------------------------------------------------------- #


def test_registry_does_not_alias_caller_dicts():
    style = {"color": "red"}

    @spytial.edgeStyle(field="n", lineStyle=style)
    class T:
        pass

    style["color"] = "green"
    assert _directives(T())[0]["edgeStyle"]["lineStyle"]["color"] == "red"


# --------------------------------------------------------------------------- #
# Collision advisory (core 3.0 StyleCollisionError pre-warning)
# --------------------------------------------------------------------------- #


def test_conflicting_rules_warn():
    @spytial.edgeStyle(field="n", lineStyle=LineStyle(color="red"))
    @spytial.edgeStyle(field="n", lineStyle=LineStyle(color="blue"))
    class T:
        pass

    with pytest.warns(UserWarning, match="StyleCollisionError"):
        collect_decorators(T())


def test_non_conflicting_rules_do_not_warn():
    @spytial.edgeStyle(field="a", lineStyle=LineStyle(color="red"))
    @spytial.edgeStyle(field="b", lineStyle=LineStyle(color="blue"))
    @spytial.edgeStyle(field="a", selector="Node", lineStyle=LineStyle(color="blue"))
    @spytial.atomStyle(selector="Node", borderStyle=BorderStyle(color="red"))
    @spytial.atomStyle(selector="Leaf", borderStyle=BorderStyle(color="blue"))
    class T:
        pass

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        collect_decorators(T())
