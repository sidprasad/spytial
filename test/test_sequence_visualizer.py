from pathlib import Path

import pytest

from spytial import annotate_orientation, diagramSequence, reset_object_ids
from spytial.provider_system import CnDDataInstanceBuilder


class CounterState:
    def __init__(self, value):
        self.value = value


class KeyedState:
    def __init__(self, key, value):
        self.key = key
        self.value = value


class Snapshot:
    def __init__(self, tracked, untracked):
        self.tracked = tracked
        self.untracked = untracked


def _find_primary_atom(data_instance, type_name):
    for atom in data_instance["atoms"]:
        if atom["type"] == type_name:
            return atom
    raise AssertionError(f"Atom with type {type_name!r} not found")


def test_builder_can_preserve_object_ids_across_sequence_steps():
    state = CounterState(1)
    builder = CnDDataInstanceBuilder(preserve_object_ids=True)

    first = builder.build_instance(state)
    state.value = 2
    second = builder.build_instance(state)

    assert _find_primary_atom(first, "CounterState")["id"] == _find_primary_atom(
        second, "CounterState"
    )["id"]


def test_builder_uses_distinct_ids_for_rebuilt_snapshots_without_identity():
    builder = CnDDataInstanceBuilder(preserve_object_ids=True)

    first = builder.build_instance(CounterState(1))
    second = builder.build_instance(CounterState(2))

    assert _find_primary_atom(first, "CounterState")["id"] != _find_primary_atom(
        second, "CounterState"
    )["id"]


def test_builder_uses_explicit_identity_for_rebuilt_snapshots():
    builder = CnDDataInstanceBuilder(
        preserve_object_ids=True,
        identity_resolver=lambda obj: obj.key if isinstance(obj, KeyedState) else None,
    )

    first = builder.build_instance(KeyedState("shared", 1))
    second = builder.build_instance(KeyedState("shared", 2))

    assert _find_primary_atom(first, "KeyedState")["id"] == "identity:shared"
    assert _find_primary_atom(second, "KeyedState")["id"] == "identity:shared"


def test_builder_supports_partial_identity_with_fallback_behavior():
    builder = CnDDataInstanceBuilder(
        preserve_object_ids=True,
        identity_resolver=lambda obj: obj.key if isinstance(obj, KeyedState) else None,
    )

    first = builder.build_instance(
        Snapshot(KeyedState("shared", 1), CounterState(1))
    )
    second = builder.build_instance(
        Snapshot(KeyedState("shared", 2), CounterState(2))
    )

    assert _find_primary_atom(first, "KeyedState")["id"] == _find_primary_atom(
        second, "KeyedState"
    )["id"]
    assert _find_primary_atom(first, "CounterState")["id"] != _find_primary_atom(
        second, "CounterState"
    )["id"]


def test_builder_rejects_duplicate_identity_keys_in_one_snapshot():
    builder = CnDDataInstanceBuilder(
        identity_resolver=lambda obj: obj.key if isinstance(obj, KeyedState) else None
    )

    with pytest.raises(ValueError, match="Duplicate explicit identity"):
        builder.build_instance(
            Snapshot(KeyedState("dup", 1), KeyedState("dup", 2))
        )


def test_builder_rejects_invalid_identity_hook_return_type():
    builder = CnDDataInstanceBuilder(identity_resolver=lambda obj: 123)

    with pytest.raises(TypeError, match="must return a string or None"):
        builder.build_instance(CounterState(1))


def test_annotation_self_reference_ids_take_precedence_over_identity_hook():
    reset_object_ids()
    state = CounterState(1)
    annotate_orientation(state, selector="self", directions=["below"])
    builder = CnDDataInstanceBuilder(
        identity_resolver=lambda obj: "explicit-counter"
        if isinstance(obj, CounterState)
        else None
    )

    data_instance = builder.build_instance(state)

    assert _find_primary_atom(data_instance, "CounterState")["id"].startswith("obj_")


def test_diagram_sequence_writes_navigation_html(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = diagramSequence(
        [{"value": 1}, {"value": 2}],
        sequence_policy="stability",
        method="file",
        auto_open=False,
        title="Counter states",
    )

    html_path = Path(result)
    html = html_path.read_text(encoding="utf-8")

    assert html_path.exists()
    assert result.endswith("spytial_sequence_visualization.html")
    assert 'id="prev-step"' in html
    assert 'id="next-step"' in html
    assert "const sequencePolicyName = `stability`;" in html
    assert "prevInstance" in html
    assert "currInstance" in html


def test_diagram_sequence_accepts_identity_hook_and_embeds_stable_ids(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    result = diagramSequence(
        [KeyedState("shared", 1), KeyedState("shared", 2)],
        sequence_policy="stability",
        method="file",
        auto_open=False,
        identity=lambda obj: obj.key if isinstance(obj, KeyedState) else None,
    )

    html = Path(result).read_text(encoding="utf-8")

    assert "identity:shared" in html


def test_diagram_sequence_requires_at_least_one_object():
    with pytest.raises(ValueError, match="requires at least one object"):
        diagramSequence([], method="file", auto_open=False)
