#!/usr/bin/env python3
"""Declared-but-unpopulated fields reach the data instance as empty relations.

The relationalizers are extensional — they emit a tuple only where an instance
holds a value. Without a schema channel, a field that no walked instance
populates leaves no trace, and a selector naming it resolves to an arity-0 atom
literal, indistinguishable from a misspelling. ``declared_relations`` carries
the type's shape across so the field appears as a relation holding nothing.
"""

import dataclasses
from typing import Optional

import pytest

from spytial import CnDDataInstanceBuilder, reify


def _relations(obj):
    """Map relation name -> list of atom-id tuples for a freshly built instance."""
    instance = CnDDataInstanceBuilder().build_instance(obj)
    return {r["name"]: [t["atoms"] for t in r["tuples"]] for r in instance["relations"]}


# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #


@dataclasses.dataclass
class OptionalField:
    a: int
    b: Optional[int] = None


@dataclasses.dataclass
class UnsetInitFalse:
    a: int
    b: int = dataclasses.field(init=False)


def test_dataclass_none_valued_field_is_populated_not_empty():
    """A field holding None is populated — it points at the NoneType atom."""
    rels = _relations(OptionalField(a=1))
    assert rels["b"] == [["n0", "None"]]


def test_dataclass_unassigned_init_false_field_is_declared_but_empty():
    """field(init=False) the owner never assigned: no tuple, but the name survives."""
    rels = _relations(UnsetInitFalse(a=1))
    assert rels["b"] == []
    assert rels["a"] == [["n0", "1"]]


def test_dataclass_unassigned_init_false_field_does_not_raise():
    """Reading such a field raises AttributeError; the build must not propagate it."""
    CnDDataInstanceBuilder().build_instance(UnsetInitFalse(a=1))


# --------------------------------------------------------------------------- #
# Plain classes
# --------------------------------------------------------------------------- #


class AnnotatedOnly:
    """`b` is annotated at class level but only assigned on one branch."""

    b: int

    def __init__(self, a, set_b=False):
        self.a = a
        if set_b:
            self.b = 99


class Slotted:
    __slots__ = ("a", "b")

    def __init__(self, a):
        self.a = a


class SingleSlot:
    __slots__ = "only"


class Base:
    inherited: int


class Derived(Base):
    own: int

    def __init__(self):
        self.own = 1


def test_plain_class_annotation_only_field_is_declared_but_empty():
    rels = _relations(AnnotatedOnly(1))
    assert rels["b"] == []


def test_plain_class_assigned_field_is_unaffected():
    rels = _relations(AnnotatedOnly(1, set_b=True))
    assert rels["b"] == [["n0", "99"]]


def test_unassigned_slot_is_declared_but_empty():
    rels = _relations(Slotted(1))
    assert rels["b"] == []


def test_slots_accepts_a_bare_string():
    """__slots__ = "only" is the legal single-slot spelling, not an iterable of chars."""
    rels = _relations(SingleSlot())
    assert rels["only"] == []
    assert "o" not in rels


def test_inherited_annotations_are_declared():
    rels = _relations(Derived())
    assert rels["inherited"] == []
    assert rels["own"] == [["n0", "1"]]


def test_annotation_names_are_read_per_class_not_inherited():
    """The MRO walk needs each class's own annotations.

    Reading them off the class attribute would re-attribute a base's fields at
    every level, because `klass.__annotations__` falls back to an inherited
    dict on a class that declares none of its own.
    """
    from spytial.domain_relationalizers.generic_object_relationalizer import (
        _own_annotation_names,
    )

    class NoOwnAnnotations(Base):
        pass

    assert _own_annotation_names(Base) == ["inherited"]
    assert _own_annotation_names(Derived) == ["own"]
    assert _own_annotation_names(NoOwnAnnotations) == []


def test_annotation_names_survive_an_unresolvable_forward_reference():
    """Python 3.14 evaluates annotations on access; only the names are wanted."""
    from spytial.domain_relationalizers.generic_object_relationalizer import (
        _own_annotation_names,
    )

    class Forward:
        later: "NeverDefinedAnywhere"  # noqa: F821

    assert _own_annotation_names(Forward) == ["later"]


def test_single_underscore_names_are_structure_not_privacy():
    """`_next` is state like any other — the rule dataclasses already follow."""

    class Underscored:
        _next: object
        shown: int

        def __init__(self):
            self.shown = 1

    rels = _relations(Underscored())
    assert rels["_next"] == []
    assert rels["shown"] == [["n0", "1"]]


def test_language_hidden_names_are_skipped():
    """Dunders and name-mangled attributes are hidden by the language itself."""

    class Hidden:
        _visible: int

        def __init__(self):
            self._visible = 1
            self.__mangled = 2  # stored as _Hidden__mangled

    rels = _relations(Hidden())
    assert rels["_visible"] == [["n0", "1"]]
    assert "_Hidden__mangled" not in rels
    assert not [name for name in rels if name.startswith("__")]


def test_mangled_names_are_skipped_for_the_declaring_base():
    """Mangling uses the class that wrote the name, not the instance's class."""

    class MangledBase:
        def __init__(self):
            self.__owned = 1  # stored as _MangledBase__owned

    class MangledChild(MangledBase):
        pass

    assert "_MangledBase__owned" not in _relations(MangledChild())


def test_underscored_pointer_draws_an_edge_like_its_dataclass_twin():
    """The asymmetry this closes: same shape, same relations, either spelling."""

    @dataclasses.dataclass
    class DcNode:
        value: int
        _next: object = None

    class PlainNode:
        def __init__(self):
            self.value = 1
            self._next = None

    assert set(_relations(DcNode(1))) == set(_relations(PlainNode()))


# --------------------------------------------------------------------------- #
# Interaction with populated instances
# --------------------------------------------------------------------------- #


def test_partial_population_across_instances_keeps_the_tuples():
    """One instance populating `b` means `b` is not empty — the other adds no tuple."""
    rels = _relations([AnnotatedOnly(1), AnnotatedOnly(2, set_b=True)])
    assert rels["b"] == [["n2", "99"]]


def test_declared_relation_is_not_duplicated_when_populated():
    instance = CnDDataInstanceBuilder().build_instance(AnnotatedOnly(1, set_b=True))
    names = [r["name"] for r in instance["relations"]]
    assert names.count("b") == 1


def test_empty_relation_declares_binary_arity():
    """Arity is unmeasurable without a tuple; empties default to binary."""
    instance = CnDDataInstanceBuilder().build_instance(AnnotatedOnly(1))
    empty = next(r for r in instance["relations"] if r["name"] == "b")
    assert empty["types"] == ["object", "object"]
    assert empty["id"] == "b"


# --------------------------------------------------------------------------- #
# Containers declare nothing
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("value", [[1, 2], {"k": 1}, {1, 2}, (1, 2), 42, "s", None])
def test_containers_and_primitives_declare_no_relations(value):
    """Only the tuples they actually emit — no phantom schema names."""
    instance = CnDDataInstanceBuilder().build_instance(value)
    assert all(r["tuples"] for r in instance["relations"])


# --------------------------------------------------------------------------- #
# Builder state and round-trip
# --------------------------------------------------------------------------- #


def test_declared_names_do_not_leak_across_builds():
    """A reused builder must not carry a prior object's schema into the next."""
    builder = CnDDataInstanceBuilder()
    builder.build_instance(AnnotatedOnly(1))
    second = builder.build_instance([1, 2])
    assert "b" not in [r["name"] for r in second["relations"]]


def test_empty_relation_does_not_disturb_reify():
    """An empty relation contributes no tuple, so reconstruction is unchanged."""
    instance = CnDDataInstanceBuilder().build_instance(AnnotatedOnly(1))
    restored = reify(instance)
    assert restored.a == 1
    # Extensionally faithful: the instance never had `b`, so neither does the copy.
    assert not hasattr(restored, "b")


def test_none_valued_field_still_round_trips():
    restored = reify(CnDDataInstanceBuilder().build_instance(OptionalField(a=1)))
    assert restored.a == 1
    assert restored.b is None


# --------------------------------------------------------------------------- #
# Extension point
# --------------------------------------------------------------------------- #


def test_custom_relationalizer_schema_hook_failure_does_not_fail_the_build():
    """A third-party declared_relations that raises must not take down a build."""
    from spytial.domain_relationalizers import GenericObjectRelationalizer

    class Exploding(GenericObjectRelationalizer):
        def declared_relations(self, obj):
            raise RuntimeError("boom")

    builder = CnDDataInstanceBuilder()
    atoms, relations = Exploding().relationalize(AnnotatedOnly(1), builder)
    assert atoms  # relationalize itself is unaffected

    # And through the builder, where the hook is called defensively.
    import spytial.provider_system as ps

    original = ps.RelationalizerRegistry.find_relationalizer
    ps.RelationalizerRegistry.find_relationalizer = staticmethod(
        lambda obj: Exploding() if isinstance(obj, AnnotatedOnly) else original(obj)
    )
    try:
        instance = CnDDataInstanceBuilder().build_instance(AnnotatedOnly(1))
    finally:
        ps.RelationalizerRegistry.find_relationalizer = original
    assert [r["name"] for r in instance["relations"]] == ["a"]
