"""Exact repr recovery for bounded, generated class declarations.

Each example defines 1-3 instance classes with 0-4 fields each, plus optional
base classes. The final class kind is parametrized so ordinary, slotted,
mutable-dataclass, and frozen-dataclass
families each receive their own Hypothesis budget. Earlier classes can occur
in later fields, directly or through acyclic lists, tuples, and dictionaries.

Names, fields, optional single inheritance, ordinary repr field order, and
dataclass defaults/repr flags vary. Printers depend only on declared fields.
Class names avoid built-in dispatch names; dunders, name-mangled private
state, descriptors, custom allocation, arbitrary printers, and cycles are
outside this generator. NaN dictionary keys remain excluded.

Capture returns only JSON and the expected string. Its temporary module is
then removed. Recovery installs newly created class definitions and invokes
the public decoder with a fresh builder. Definitions contain field metadata
and scalar defaults, never original instances or per-instance field values.
"""

import json
import string
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field, make_dataclass
from types import ModuleType

import pytest
from hypothesis import given, note, settings, strategies as st

from spytial.provider_system import CnDDataInstanceBuilder, reify
from test_reify_pbt import atoms, hashable_atoms


MODULE_NAME = "_spytial_generated_reify_types"
KINDS = ("ordinary", "slots", "dataclass", "frozen_dataclass")


@dataclass(frozen=True)
class FieldSpec:
    name: str
    shown: bool
    has_default: bool
    default: object


@dataclass(frozen=True)
class ClassSpec:
    name: str
    kind: str
    fields: tuple
    inherited: bool
    base_count: int
    print_order: tuple


@dataclass(frozen=True)
class InstanceRef:
    index: int


@dataclass(frozen=True)
class UseDefault:
    pass


field_names = st.one_of(
    st.sampled_from(
        [
            "value",
            "left",
            "right",
            "_state",
            "idx",
            "kv",
            "contains",
            "t0",
            "start",
            "stop",
            "step",
            "name",
        ]
    ),
    st.text(string.ascii_lowercase, min_size=1, max_size=6).map(
        lambda name: "f_" + name
    ),
)
scalar_defaults = st.one_of(
    st.none(), st.booleans(), st.integers(-10, 10), st.text(max_size=8)
)
class_names = st.text(string.ascii_uppercase, min_size=1, max_size=5).map(
    lambda name: "Generated" + name
)


def field_values(index):
    leaves = atoms
    if index:
        leaves = st.one_of(leaves, st.integers(0, index - 1).map(InstanceRef))
    return st.recursive(
        leaves,
        lambda children: st.one_of(
            st.lists(children, max_size=3),
            st.lists(children, max_size=3).map(tuple),
            st.dictionaries(hashable_atoms, children, max_size=3),
        ),
        max_leaves=8,
    )


@st.composite
def class_families(draw, root_kind):
    names = draw(st.lists(class_names, min_size=1, max_size=3, unique=True))
    definitions = []
    values = []
    for index, name in enumerate(names):
        kind = root_kind if index == len(names) - 1 else draw(st.sampled_from(KINDS))
        names_for_fields = draw(st.lists(field_names, max_size=4, unique=True))
        is_dataclass = kind in ("dataclass", "frozen_dataclass")
        # Required fields precede defaulted fields across the entire MRO.
        first_default = (
            draw(st.integers(0, len(names_for_fields)))
            if is_dataclass
            else len(names_for_fields)
        )
        fields = tuple(
            FieldSpec(
                field_name,
                draw(st.booleans()) if is_dataclass else True,
                field_index >= first_default,
                draw(scalar_defaults) if field_index >= first_default else None,
            )
            for field_index, field_name in enumerate(names_for_fields)
        )
        inherited = draw(st.booleans())
        base_count = draw(st.integers(0, len(fields))) if inherited else 0
        print_order = tuple(draw(st.permutations(names_for_fields)))
        definitions.append(
            ClassSpec(name, kind, fields, inherited, base_count, print_order)
        )
        strategy = field_values(index)
        values.append(
            tuple(
                (
                    draw(st.one_of(st.just(UseDefault()), strategy))
                    if item.has_default
                    else draw(strategy)
                )
                for item in fields
            )
        )
    return tuple(definitions), tuple(values)


def field_repr(names):
    # The closure retains only declaration metadata, never instance values.
    def __repr__(self):
        entries = ", ".join(
            "{}={!r}".format(name, getattr(self, name)) for name in names
        )
        return "{}[{}]".format(type(self).__name__, entries)

    return __repr__


def define_class(spec, module):
    def make(name, fields, bases):
        if spec.kind in ("dataclass", "frozen_dataclass"):
            return make_dataclass(
                name,
                [
                    (
                        item.name,
                        object,
                        (
                            field(default=item.default, repr=item.shown)
                            if item.has_default
                            else field(repr=item.shown)
                        ),
                    )
                    for item in fields
                ],
                bases=bases,
                namespace={"__module__": MODULE_NAME},
                frozen=spec.kind == "frozen_dataclass",
            )
        print_order = spec.print_order
        if name != spec.name:
            own_fields = {item.name for item in fields}
            print_order = tuple(name for name in print_order if name in own_fields)
        namespace = {
            "__module__": MODULE_NAME,
            "__repr__": field_repr(print_order),
        }
        if spec.kind == "slots":
            namespace["__slots__"] = tuple(item.name for item in fields)
        return type(name, bases, namespace)

    bases = (object,)
    if spec.inherited:
        base = make(spec.name + "_Base", spec.fields[: spec.base_count], bases)
        setattr(module, base.__name__, base)
        bases = (base,)
    cls = make(spec.name, spec.fields[spec.base_count :], bases)
    setattr(module, spec.name, cls)
    return cls


@contextmanager
def installed_definitions(definitions):
    module = ModuleType(MODULE_NAME)
    absent = object()
    previous = sys.modules.get(MODULE_NAME, absent)
    sys.modules[MODULE_NAME] = module
    try:
        yield [define_class(spec, module) for spec in definitions]
    finally:
        if previous is absent:
            del sys.modules[MODULE_NAME]
        else:
            sys.modules[MODULE_NAME] = previous


def materialize(recipe, instances):
    if isinstance(recipe, InstanceRef):
        return instances[recipe.index]
    if isinstance(recipe, list):
        return [materialize(value, instances) for value in recipe]
    if isinstance(recipe, tuple):
        return tuple(materialize(value, instances) for value in recipe)
    if isinstance(recipe, dict):
        return {key: materialize(value, instances) for key, value in recipe.items()}
    return recipe


def capture_family(definitions, recipes):
    with installed_definitions(definitions) as classes:
        instances = []
        for spec, cls, values in zip(definitions, classes, recipes):
            attrs = {
                item.name: materialize(value, instances)
                for item, value in zip(spec.fields, values)
                if not isinstance(value, UseDefault)
            }
            if spec.kind in ("dataclass", "frozen_dataclass"):
                instance = cls(**attrs)
            else:
                instance = cls()
                for name, value in attrs.items():
                    setattr(instance, name, value)
            instances.append(instance)
        expected = repr(instances)
        payload = json.dumps(CnDDataInstanceBuilder().build_instance(instances))
    # No original instance, class, module, or builder is passed to recovery.
    return payload, expected


@pytest.mark.parametrize("root_kind", KINDS)
@settings(max_examples=200, deadline=None)
@given(data=st.data())
def test_generated_class_family_repr_roundtrip(root_kind, data):
    definitions, recipes = data.draw(class_families(root_kind), label="family")
    note("Class definitions: {!r}".format(definitions))
    payload, expected = capture_family(definitions, recipes)
    with installed_definitions(definitions) as classes:
        rebuilt = reify(json.loads(payload))
        assert type(rebuilt) is list
        assert [type(value) for value in rebuilt] == classes
        assert repr(rebuilt) == expected
