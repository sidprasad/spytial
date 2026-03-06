from pathlib import Path

import pytest

from spytial import annotate_orientation, sequence, reset_object_ids
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


def test_builder_deduplicates_identity_keys_in_one_snapshot():
    """When two distinct Python objects share the same identity key within one
    frame, the identity resolver is authoritative: both objects are aliased to
    the same conceptual atom rather than raising an error.  This is the correct
    semantic for trees/graphs where back-pointers or shared sentinels can
    surface the 'same' node via multiple traversal paths in one snapshot."""
    builder = CnDDataInstanceBuilder(
        identity_resolver=lambda obj: obj.key if isinstance(obj, KeyedState) else None
    )

    # Should NOT raise — second object is silently aliased to the first atom
    data_instance = builder.build_instance(
        Snapshot(KeyedState("dup", 1), KeyedState("dup", 2))
    )

    # Both objects must map to the same canonical atom ID
    dup_atoms = [a for a in data_instance["atoms"] if a["id"].endswith("dup")]
    assert len(dup_atoms) >= 1
    assert len({a["id"] for a in dup_atoms}) == 1, (
        "Both Python objects with identity key 'dup' should resolve to one atom ID"
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


def test_sequence_recorder_writes_navigation_html(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    seq = sequence(sequence_policy="stability", method="file", auto_open=False, title="Counter states")
    seq.record({"value": 1})
    seq.record({"value": 2})
    result = seq.diagram()

    html_path = Path(result)
    html = html_path.read_text(encoding="utf-8")

    assert html_path.exists()
    assert result.endswith("spytial_sequence_visualization.html")
    assert 'id="prev-step"' in html
    assert 'id="next-step"' in html
    assert "const sequencePolicyName = `stability`;" in html
    assert "prevInstance" in html
    assert "currInstance" in html


def test_sequence_recorder_accepts_identity_hook_and_embeds_stable_ids(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    seq = sequence(
        identity=lambda obj: obj.key if isinstance(obj, KeyedState) else None,
        sequence_policy="stability",
        method="file",
        auto_open=False,
    )
    seq.record(KeyedState("shared", 1))
    seq.record(KeyedState("shared", 2))
    html = Path(seq.diagram()).read_text(encoding="utf-8")

    assert "identity:shared" in html


def test_sequence_recorder_requires_at_least_one_record():
    seq = sequence(method="file", auto_open=False)
    with pytest.raises(ValueError, match="No frames recorded"):
        seq.diagram()
