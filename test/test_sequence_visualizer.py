from pathlib import Path

import pytest

from spytial import (
    annotate_orientation,
    sequence,
    reset_object_ids,
    SEQUENCE_POLICY_NAMES,
    LABEL_STRATEGY_NAMES,
)
from spytial.provider_system import CnDDataInstanceBuilder
from spytial.visualizer import _back_construct_labels


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
    assert "let sequencePolicyName = `stability`;" in html
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


@pytest.mark.parametrize("policy", sorted(SEQUENCE_POLICY_NAMES))
def test_sequence_recorder_accepts_all_valid_policies(tmp_path, monkeypatch, policy):
    monkeypatch.chdir(tmp_path)
    seq = sequence(sequence_policy=policy, method="file", auto_open=False)
    seq.record({"v": 1})
    result = seq.diagram()
    html = Path(result).read_text(encoding="utf-8")
    assert f"let sequencePolicyName = `{policy}`" in html


def test_sequence_recorder_rejects_invalid_policy_at_construction():
    with pytest.raises(ValueError, match="Unknown sequence_policy"):
        sequence(sequence_policy="nonexistent")


def test_sequence_recorder_rejects_invalid_policy_override_at_diagram(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seq = sequence(sequence_policy="stability", method="file", auto_open=False)
    seq.record({"v": 1})
    with pytest.raises(ValueError, match="Unknown sequence_policy"):
        seq.diagram(sequence_policy="nonexistent")


def test_sequence_recorder_policy_can_be_overridden_at_diagram(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seq = sequence(sequence_policy="stability", method="file", auto_open=False)
    seq.record({"v": 1})
    result = seq.diagram(sequence_policy="change_emphasis")
    html = Path(result).read_text(encoding="utf-8")
    assert "let sequencePolicyName = `change_emphasis`" in html


def test_sequence_recorder_renders_policy_select_in_html(tmp_path, monkeypatch):
    """The viewer header includes a <select> dropdown listing all four policies."""
    monkeypatch.chdir(tmp_path)
    seq = sequence(method="file", auto_open=False)
    seq.record({"v": 1})
    html = Path(seq.diagram()).read_text(encoding="utf-8")
    assert 'id="policy-select"' in html
    for policy in SEQUENCE_POLICY_NAMES:
        assert f'value="{policy}"' in html


def test_sequence_recorder_initial_policy_matches_python_arg(tmp_path, monkeypatch):
    """The Python-supplied sequence_policy is the initial value of the dropdown."""
    monkeypatch.chdir(tmp_path)
    seq = sequence(sequence_policy="change_emphasis", method="file", auto_open=False)
    seq.record({"v": 1})
    html = Path(seq.diagram()).read_text(encoding="utf-8")
    assert "let sequencePolicyName = `change_emphasis`;" in html


def test_sequence_recorder_accepts_label_and_embeds_in_html(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seq = sequence(method="file", auto_open=False)
    seq.record({"value": 1}, label="rotate left at node 5")
    seq.record({"value": 2}, label="recolor uncle")
    html = Path(seq.diagram()).read_text(encoding="utf-8")
    assert "rotate left at node 5" in html
    assert "recolor uncle" in html
    assert "const frameLabels = " in html


def test_sequence_recorder_accepts_note_and_embeds_in_html(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seq = sequence(method="file", auto_open=False)
    seq.record({"v": 1}, note="This step rebalances the left subtree.")
    html = Path(seq.diagram()).read_text(encoding="utf-8")
    assert "rebalances the left subtree" in html
    assert "const frameNotes = " in html


def test_sequence_recorder_label_and_note_are_independent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seq = sequence(method="file", auto_open=False)
    seq.record({"v": 1}, label="step one")
    seq.record({"v": 2}, note="just a note")
    seq.record({"v": 3})
    html = Path(seq.diagram()).read_text(encoding="utf-8")
    assert "step one" in html
    assert "just a note" in html
    assert seq._frame_labels == ["step one", None, None]
    assert seq._frame_notes == [None, "just a note", None]


def test_sequence_recorder_label_too_long_is_truncated():
    seq = sequence(method="file", auto_open=False)
    long = "x" * 500
    seq.record({"v": 1}, label=long)
    assert seq._frame_labels[0] is not None
    assert len(seq._frame_labels[0]) == 200


def test_sequence_recorder_empty_label_normalized_to_none():
    seq = sequence(method="file", auto_open=False)
    seq.record({"v": 1}, label="   ")
    seq.record({"v": 2}, note="\n\t  ")
    assert seq._frame_labels[0] is None
    assert seq._frame_notes[1] is None


def test_sequence_recorder_label_special_chars_safely_escaped(tmp_path, monkeypatch):
    """Labels go through json.dumps so backticks, quotes, and </script> can't
    break out of the embedded JS array."""
    monkeypatch.chdir(tmp_path)
    seq = sequence(method="file", auto_open=False)
    seq.record({"v": 1}, label='backtick `inj` "quote" </script>')
    html = Path(seq.diagram()).read_text(encoding="utf-8")
    label_block = html.split("const frameLabels = ")[1].split(";")[0]
    assert "</script>" not in label_block


# --- label strategy tests (issue #94) ---------------------------------------


def _make_dsu_frame(atoms):
    """Build a minimal data instance with both top-level atoms and types
    sub-atoms, matching the shape produced by ``build_instance``."""
    return {
        "atoms": [dict(a) for a in atoms],
        "types": [
            {
                "id": "DSUNode",
                "atoms": [dict(a) for a in atoms],
            }
        ],
    }


def test_apply_label_persistence_locks_first_observation_across_builds():
    """Fix B: once an atom's label is recorded, subsequent builds inherit it
    even if the relationalizer would have produced a different label."""
    builder = CnDDataInstanceBuilder(preserve_object_ids=True)

    frame1 = _make_dsu_frame(
        [{"id": "n1", "type": "DSUNode", "label": "DSUNode0"}]
    )
    builder.apply_label_persistence(frame1)
    assert frame1["atoms"][0]["label"] == "DSUNode0"

    frame2 = _make_dsu_frame(
        [
            {"id": "n1", "type": "DSUNode", "label": "a"},
            {"id": "n2", "type": "DSUNode", "label": "DSUNode0"},
        ]
    )
    builder.apply_label_persistence(frame2)

    # n1 had a prior cached label → keep it.
    assert frame2["atoms"][0]["label"] == "DSUNode0"
    assert frame2["types"][0]["atoms"][0]["label"] == "DSUNode0"
    # n2 is new → cache its label as-is.
    assert frame2["atoms"][1]["label"] == "DSUNode0"


def test_persist_strategy_assigns_distinct_placeholders_to_distinct_atoms(
    tmp_path, monkeypatch
):
    """Issue #94 regression: when several atoms appear across frames and none
    has a resolvable variable name, each must get its own ``TypeN`` index
    instead of all collapsing to ``Type0``.  This is what makes the persisted
    placeholders useful as a stable identifier."""
    monkeypatch.chdir(tmp_path)

    class _Box:
        def __init__(self, value):
            self.value = value

    class _Recorder:
        def __init__(self, seq):
            self._seq = seq
            self._items = []

        def add(self, value):
            # Use ``node`` (in the internal-names skip list) so var-name
            # lookup *fails* and we exercise the placeholder-counter path.
            node = _Box(value)
            self._items.append(node)
            self._seq.record(self._items)
            return node

    seq = sequence(method="file", auto_open=False)
    rec = _Recorder(seq)
    rec.add(1)
    rec.add(2)
    rec.add(3)

    final_frame = seq._data_instances[-1]
    boxes = [a for a in final_frame["atoms"] if a["type"] == "_Box"]
    labels = [a["label"] for a in boxes]
    assert len(labels) == 3
    assert len(set(labels)) == 3, (
        f"Each atom should have a unique placeholder, got {labels!r}"
    )

    # And those labels must match what was recorded for that atom in earlier
    # frames — locking, not regenerating.
    for frame in seq._data_instances:
        for atom in frame["atoms"]:
            if atom["type"] != "_Box":
                continue
            expected = next(b["label"] for b in boxes if b["id"] == atom["id"])
            assert atom["label"] == expected


def test_apply_label_persistence_isolated_per_builder():
    """Two recorders must not share a label cache."""
    a = CnDDataInstanceBuilder(preserve_object_ids=True)
    b = CnDDataInstanceBuilder(preserve_object_ids=True)

    a.apply_label_persistence(
        _make_dsu_frame([{"id": "n1", "type": "DSUNode", "label": "left"}])
    )
    target = _make_dsu_frame(
        [{"id": "n1", "type": "DSUNode", "label": "right"}]
    )
    b.apply_label_persistence(target)
    assert target["atoms"][0]["label"] == "right"


def test_back_construct_labels_promotes_real_label_to_earlier_frames():
    """Fix D: a real label discovered in frame 2 propagates back to frame 1
    where the same atom only had a placeholder."""
    instances = [
        _make_dsu_frame(
            [{"id": "n1", "type": "DSUNode", "label": "DSUNode0"}]
        ),
        _make_dsu_frame(
            [
                {"id": "n1", "type": "DSUNode", "label": "a"},
                {"id": "n2", "type": "DSUNode", "label": "DSUNode0"},
            ]
        ),
        _make_dsu_frame(
            [
                {"id": "n1", "type": "DSUNode", "label": "a"},
                {"id": "n2", "type": "DSUNode", "label": "b"},
                {"id": "n3", "type": "DSUNode", "label": "DSUNode0"},
            ]
        ),
    ]

    _back_construct_labels(instances)

    assert instances[0]["atoms"][0]["label"] == "a"
    assert instances[0]["types"][0]["atoms"][0]["label"] == "a"
    assert [a["label"] for a in instances[1]["atoms"]] == ["a", "b"]
    assert [a["label"] for a in instances[1]["types"][0]["atoms"]] == ["a", "b"]
    # n3 only ever had the placeholder; it stays placeholder but stably so.
    assert instances[2]["atoms"][2]["label"] == "DSUNode0"


def test_back_construct_keeps_placeholder_when_no_real_label_seen():
    instances = [
        _make_dsu_frame(
            [{"id": "n1", "type": "DSUNode", "label": "DSUNode0"}]
        ),
        _make_dsu_frame(
            [{"id": "n1", "type": "DSUNode", "label": "DSUNode1"}]
        ),
    ]
    _back_construct_labels(instances)
    # Both labels were placeholders; picking either is fine, but it must be
    # the same in every frame.
    chosen = instances[0]["atoms"][0]["label"]
    assert chosen in {"DSUNode0", "DSUNode1"}
    assert instances[1]["atoms"][0]["label"] == chosen


def test_sequence_recorder_default_label_strategy_is_persist():
    seq = sequence(method="file", auto_open=False)
    assert seq._label_strategy == "persist"


def test_sequence_recorder_rejects_invalid_label_strategy():
    with pytest.raises(ValueError, match="Unknown label_strategy"):
        sequence(label_strategy="nonexistent")


@pytest.mark.parametrize("strategy", sorted(LABEL_STRATEGY_NAMES))
def test_sequence_recorder_accepts_all_valid_label_strategies(
    tmp_path, monkeypatch, strategy
):
    monkeypatch.chdir(tmp_path)
    seq = sequence(method="file", auto_open=False, label_strategy=strategy)
    seq.record({"v": 1})
    seq.record({"v": 2})
    # Should produce HTML without raising.
    Path(seq.diagram()).read_text(encoding="utf-8")


def test_persist_strategy_freezes_labels_on_record(tmp_path, monkeypatch):
    """End-to-end: with the default persist strategy, the *recorded* data
    instances must use the first-observed label for each atom."""
    monkeypatch.chdir(tmp_path)
    seq = sequence(method="file", auto_open=False)
    seq.record({"v": 1})

    # Reach into the recorder and pretend a later frame produced a different
    # label for the same atom (mirrors what would happen if the var-name
    # lookup resolved to something different on a later snapshot).
    snapshot_atom_ids = [a["id"] for a in seq._data_instances[0]["atoms"]]

    forged = {
        "atoms": [
            {"id": aid, "type": "object", "label": "different-label"}
            for aid in snapshot_atom_ids
        ],
        "types": [
            {
                "id": "object",
                "atoms": [
                    {"id": aid, "type": "object", "label": "different-label"}
                    for aid in snapshot_atom_ids
                ],
            }
        ],
    }
    seq._builder.apply_label_persistence(forged)

    # Persistence locked in the original label; the forged one was overridden.
    for atom in forged["atoms"]:
        assert atom["label"] != "different-label"


def test_back_construct_strategy_runs_post_pass_at_diagram(tmp_path, monkeypatch):
    """End-to-end: back_construct mode must defer rewriting until diagram(),
    and rewrite all frames in place."""
    monkeypatch.chdir(tmp_path)
    seq = sequence(
        method="file", auto_open=False, label_strategy="back_construct"
    )
    seq.record({"v": 1})
    seq.record({"v": 2})

    # Manually inject a placeholder/real-label conflict to exercise the
    # post-processing pass — the recorder doesn't pass through the
    # snap-during-construction path in unit-test scope.
    seq._data_instances[:] = [
        _make_dsu_frame(
            [{"id": "n1", "type": "DSUNode", "label": "DSUNode0"}]
        ),
        _make_dsu_frame(
            [{"id": "n1", "type": "DSUNode", "label": "a"}]
        ),
    ]

    seq.diagram()

    # diagram() must have promoted "a" to frame 1 in place.
    assert seq._data_instances[0]["atoms"][0]["label"] == "a"
    assert seq._data_instances[0]["types"][0]["atoms"][0]["label"] == "a"
