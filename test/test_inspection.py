"""Pin down what the round-trip oracle may and may not ignore."""

import pytest

from inspection import inspection

pytestmark = pytest.mark.reify


def test_nested_dictionary_order_is_ignored():
    first = [{"b": {"y": 2, "x": 1}, "a": (3, 4)}]
    second = [{"a": (3, 4), "b": {"x": 1, "y": 2}}]
    assert repr(first) != repr(second)
    assert inspection(first) == inspection(second)


@pytest.mark.parametrize("first,second", [
    ([1, 2], [2, 1]),
    ((1, 2), (2, 1)),
    ([1, 1], [1]),
    ([1], (1,)),
    ({1}, frozenset({1})),
    (True, 1),
    (1, 1.0),
    (0.0, -0.0),
    ({"a": 1, "b": 2}, {"a": 2, "b": 1}),
    ({1: "v"}, {True: "v"}),
    ("{'a': 1, 'b': 2}", "{'b': 2, 'a': 1}"),
])
def test_visible_distinctions_are_preserved(first, second):
    assert inspection(first) != inspection(second)


def test_set_member_order_is_ignored():
    first, second = set(), set()
    for item in ["z", 1, (2, 3)]:
        first.add(item)
    for item in [(2, 3), 1, "z"]:
        second.add(item)
    assert inspection(first) == inspection(second)
    assert inspection(frozenset(first)) == inspection(frozenset(second))


def test_nan_uses_printed_value_and_preserves_multiplicity():
    assert inspection(float("nan")) == inspection(float("nan"))
    assert inspection({float("nan"), float("nan")}) != inspection({float("nan")})


def test_cycles_are_finite_and_independent_of_dictionary_order():
    first = {"value": 1}
    first["self"] = first
    second = {}
    second["self"] = second
    second["value"] = 1
    assert inspection(first) == inspection(second)
    assert inspection(first) != inspection({"value": 1, "self": {}})


def test_sharing_is_not_mistaken_for_a_cycle():
    inner = [1]
    assert inspection([inner, inner]) == inspection([[1], [1]])
    inner.append(inner)
    assert inspection(inner) != inspection([1, [1]])


def test_custom_repr_remains_the_oracle():
    class Printed:
        def __init__(self, text):
            self.text = text

        def __repr__(self):
            return self.text

    assert inspection(Printed("left")) != inspection(Printed("right"))
    assert inspection(Printed("{'a': 1, 'b': 2}")) != inspection(
        Printed("{'b': 2, 'a': 1}")
    )
