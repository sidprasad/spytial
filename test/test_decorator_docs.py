"""
Tests for the decorator surface itself, rather than what it serializes.

Every spytial decorator is built by `_create_decorator` and takes `**kwargs`, so
its docstring is the only thing `help()` and IDE hovers can show. These tests
guard that the docstrings exist, name themselves correctly, and stay honest
about what spytial-core actually reads.
"""

import warnings

import pytest
from typing import Annotated

import spytial


ALL_DECORATORS = [
    "orientation", "cyclic", "align", "group",
    "atomStyle", "atomColor", "size", "icon",
    "edgeStyle", "edgeColor", "projection", "attribute",
    "hideField", "hideAtom", "inferredEdge", "tag", "flag",
]


@pytest.mark.parametrize("name", ALL_DECORATORS)
def test_decorator_is_documented(name):
    """`**kwargs` tells help() nothing, so every decorator needs a docstring."""
    fn = getattr(spytial, name)
    assert fn.__doc__, f"@{name} has no docstring; help() would show only (**kwargs)"


@pytest.mark.parametrize("name", ALL_DECORATORS)
def test_decorator_reports_its_own_name(name):
    """help() should say `group(...)`, not the factory's inner `decorator(...)`."""
    assert getattr(spytial, name).__name__ == name


@pytest.mark.parametrize("name", ["atomColor", "edgeColor", "projection"])
def test_deprecated_decorators_say_so(name):
    doc = getattr(spytial, name).__doc__
    assert "Deprecated" in doc


def test_align_documents_axis_not_placement_words():
    """Core's AlignConstraint rejects anything but horizontal/vertical, so the
    docstring must not advertise the orientation vocabulary (it once did)."""
    doc = spytial.align.__doc__
    assert "'horizontal'" in doc and "'vertical'" in doc


def test_orientation_documents_placement_words_not_axes():
    doc = spytial.orientation.__doc__
    for word in ("'above'", "'below'", "'left'", "'right'", "'directlyAbove'"):
        assert word in doc


# --------------------------------------------------------------------------- #
# hold: never — core's negation switch
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name, kwargs",
    [
        ("orientation", {"selector": "e", "directions": ["below"]}),
        ("cyclic", {"selector": "e", "direction": "clockwise"}),
        ("align", {"selector": "a", "direction": "horizontal"}),
        ("group", {"selector": "Team.members", "name": "Team"}),
    ],
)
def test_hold_never_is_accepted_on_every_constraint(name, kwargs, capsys):
    """Core reads `hold: never` off the inner block to negate a constraint, so
    the schema must accept it rather than warn about an unknown field."""
    decorator = getattr(spytial, name)

    @decorator(hold="never", **kwargs)
    class Target:
        pass

    assert "Unknown fields" not in capsys.readouterr().out
    entry = Target.__spytial_registry__["constraints"][0][name]
    assert entry["hold"] == "never"


def test_hold_always_stays_out_of_the_spec():
    """'always' is the default; emitting it would be noise in the YAML."""

    @spytial.group(selector="Team.members", name="Team")
    class Target:
        pass

    assert "hold" not in Target.__spytial_registry__["constraints"][0]["group"]


@pytest.mark.parametrize(
    "name, kwargs",
    [
        ("orientation", {"selector": "e", "directions": ["below"]}),
        ("cyclic", {"selector": "e", "direction": "clockwise"}),
        ("align", {"selector": "a", "direction": "horizontal"}),
        ("group", {"selector": "Team.members", "name": "Team"}),
    ],
)
def test_explicit_hold_always_is_dropped_like_the_class_form(name, kwargs):
    """The Annotated[...] classes omit hold='always'; the kwargs paths must too,
    so the same spec doesn't depend on which form authored it."""
    decorator = getattr(spytial, name)

    @decorator(hold="always", **kwargs)
    class Target:
        pass

    assert "hold" not in Target.__spytial_registry__["constraints"][0][name]


@pytest.mark.parametrize("bad", ["neevr", "", "true", True, None])
@pytest.mark.parametrize(
    "name, kwargs",
    [
        ("orientation", {"selector": "e", "directions": ["below"]}),
        ("cyclic", {"selector": "e", "direction": "clockwise"}),
        ("align", {"selector": "a", "direction": "horizontal"}),
        ("group", {"selector": "Team.members", "name": "Team"}),
    ],
)
def test_unrecognised_hold_is_rejected_not_passed_through(name, kwargs, bad):
    """Core negates on exactly 'never' and reads anything else as 'not negated',
    so a typo would silently leave the constraint positive. Fail at authoring."""
    decorator = getattr(spytial, name)

    with pytest.raises(ValueError, match="hold must be 'always' or 'never'"):

        @decorator(hold=bad, **kwargs)
        class Target:
            pass


def test_unrecognised_hold_is_rejected_on_the_object_path():
    """annotate()/decorator-on-object funnel through _annotate_object, which is a
    separate choke point from the decorator's own."""
    with pytest.raises(ValueError, match="hold must be 'always' or 'never'"):
        spytial.annotate([1, 2], "cyclic", selector="x", direction="clockwise", hold="nope")

    with pytest.raises(ValueError, match="hold must be 'always' or 'never'"):
        spytial.cyclic(selector="x", direction="clockwise", hold="nope")([1, 2])


def test_object_path_drops_hold_always():
    from spytial.annotations import collect_decorators

    obj = spytial.annotate([1, 2], "cyclic", selector="x", direction="clockwise", hold="always")
    assert "hold" not in collect_decorators(obj)["constraints"][0]["cyclic"]


# --------------------------------------------------------------------------- #
# projection — a no-op in spytial-core
# --------------------------------------------------------------------------- #


def test_projection_on_class_warns_once():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        @spytial.projection(sig="Node")
        class Target:
            pass

    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1
    assert "no effect" in str(deprecations[0].message)


def test_projection_on_object_warns_exactly_once():
    """The object path runs through both the decorator and _annotate_object;
    only one of them may warn."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        spytial.projection(sig="Node")([1, 2, 3])

    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1


def test_projection_via_annotate_helper_warns():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        spytial.annotate_projection([1, 2, 3], sig="Node")

    assert [w for w in caught if issubclass(w.category, DeprecationWarning)]


def test_projection_class_form_warns():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        Annotated[list, spytial.Projection(sig="Node")]

    assert [w for w in caught if issubclass(w.category, DeprecationWarning)]


def test_projection_still_serializes_after_deprecation():
    """Deprecated, not removed: existing specs keep working (core ignores it)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        @spytial.projection(sig="Node")
        class Target:
            pass

    assert Target.__spytial_registry__["directives"] == [{"projection": {"sig": "Node"}}]


def test_non_noop_decorators_do_not_warn():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        @spytial.hideAtom(selector="Node")
        class Target:
            pass

    assert not [w for w in caught if issubclass(w.category, DeprecationWarning)]
