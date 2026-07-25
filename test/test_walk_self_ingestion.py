"""The walk must not ingest spytial's own machinery (issue #140).

#137 exposed single-underscore attributes, which opened a path from user data
into the recorder that is *currently building the frame*:

    Node ._seq → SequenceRecorder ._builder → CnDDataInstanceBuilder ._atoms

``_atoms`` grows on every walked value, and iterating a list that grows under
its own loop never terminates. Neither existing guard applies: ``_seen`` stops
repeats but every step mints new atoms, and the depth guard never trips
because the loop is flat (depth stays ~5). The fix is refusal — the walker
returns None for spytial infrastructure reached through user data (no atom,
no edge) — plus snapshot iteration in the container relationalizers so a
mid-walk mutation from any other source degrades to stale output, not a hang.
"""

import contextlib
import signal

import pytest

import spytial
from spytial.provider_system import CnDDataInstanceBuilder
from spytial.domain_relationalizers.dict_relationalizer import DictRelationalizer
from spytial.domain_relationalizers.list_relationalizer import ListRelationalizer
from spytial.domain_relationalizers.set_relationalizer import SetRelationalizer


@contextlib.contextmanager
def finishes_within(seconds):
    """Fail fast instead of hanging the suite if the walk regresses."""
    if not hasattr(signal, "SIGALRM"):  # pragma: no cover - non-POSIX
        yield
        return

    def _timed_out(signum, frame):
        raise TimeoutError(f"walk did not finish within {seconds}s")

    previous = signal.signal(signal.SIGALRM, _timed_out)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def relation_names(instance):
    return {rel["name"] for rel in instance["relations"]}


def atom_types(instance):
    return {atom["type"] for atom in instance["atoms"]}


# ---------------------------------------------------------------------------
# The reported shape: an object records itself and keeps the recorder.
# ---------------------------------------------------------------------------


def test_record_with_backref_to_recorder_terminates():
    # Verbatim shape from #140 — record() called from inside __init__, with
    # the recorder kept as an attribute. Used to spin forever.
    class Node:
        def __init__(self, data, seq):
            self.data = list(data)
            self._seq = seq
            seq.record(self, label="frame 0")

    seq = spytial.sequence()
    with finishes_within(30):
        Node([1, 2, 3], seq)

    [frame] = seq._data_instances
    assert "SequenceRecorder" not in atom_types(frame)
    assert "CnDDataInstanceBuilder" not in atom_types(frame)
    # The refused back-reference draws no edge; the real data still does.
    assert "_seq" not in relation_names(frame)
    assert "data" in relation_names(frame)


def test_instrumented_mutation_records_every_frame():
    # The spytial-clrs pattern that silently hung: snap from inside the
    # mutating object on every step.
    class Sorter:
        def __init__(self, values, seq):
            self.values = values
            self._seq = seq

        def sort(self):
            self._seq.record(self, note="start")
            for i in range(len(self.values)):
                for j in range(len(self.values) - 1 - i):
                    if self.values[j] > self.values[j + 1]:
                        self.values[j], self.values[j + 1] = (
                            self.values[j + 1],
                            self.values[j],
                        )
                self._seq.record(self)

    seq = spytial.sequence()
    sorter = Sorter([3, 1, 2], seq)
    with finishes_within(30):
        sorter.sort()

    assert len(seq._data_instances) == 4
    assert all(
        "SequenceRecorder" not in atom_types(frame) for frame in seq._data_instances
    )


# ---------------------------------------------------------------------------
# Refusal is general, not recorder-specific.
# ---------------------------------------------------------------------------


def test_backref_to_the_active_builder_terminates():
    class Holder:
        pass

    builder = CnDDataInstanceBuilder()
    holder = Holder()
    holder.payload = [1, 2]
    holder.builder = builder

    with finishes_within(30):
        instance = builder.build_instance(holder)

    assert "payload" in relation_names(instance)
    assert "builder" not in relation_names(instance)
    assert "CnDDataInstanceBuilder" not in atom_types(instance)


def test_infrastructure_inside_containers_is_skipped():
    seq = spytial.sequence()
    instance = CnDDataInstanceBuilder().build_instance([1, seq, 2])

    assert "SequenceRecorder" not in atom_types(instance)
    idx = next(rel for rel in instance["relations"] if rel["name"] == "idx")
    # Tuples exist only for the two ints; the refused element draws nothing.
    assert len(idx["tuples"]) == 2


def test_building_the_builder_itself_is_an_error():
    builder = CnDDataInstanceBuilder()
    with pytest.raises(ValueError, match="active\\s+CnDDataInstanceBuilder"):
        builder.build_instance(builder)
    with pytest.raises(ValueError, match="internal state"):
        builder.build_instance(builder._atoms)


def test_spytial_object_as_explicit_root_still_walks():
    # Refusal is for machinery reached *through* user data. Handing a spytial
    # object to build_instance directly is an explicit request and stays
    # honored — its own spytial-typed attributes are skipped, so it ends.
    seq = spytial.sequence()
    with finishes_within(30):
        instance = CnDDataInstanceBuilder().build_instance(seq)

    root = next(a for a in instance["atoms"] if a["id"] == instance["rootId"])
    assert root["type"] == "SequenceRecorder"
    assert "CnDDataInstanceBuilder" not in atom_types(instance)


def test_reified_proxy_is_data_not_infrastructure():
    # The reify fallback proxy is defined inside spytial.provider_system, but
    # it stands in for the user's object — re-walking a reified graph must
    # keep it (the __spytial_walk_as_data__ marker).
    class Local:  # <locals> qualname → not importable → proxy on reify
        def __init__(self, x):
            self.x = x

    builder = CnDDataInstanceBuilder()
    reified = builder.reify(builder.build_instance([Local(5)]))
    proxy = reified[0]
    assert type(proxy).__module__.startswith("spytial")  # the hazard is real

    rewalked = CnDDataInstanceBuilder().build_instance([proxy])
    assert "x" in relation_names(rewalked)


# ---------------------------------------------------------------------------
# Containers iterate snapshots: mutation mid-walk must not hang or raise.
# ---------------------------------------------------------------------------


def test_list_relationalizer_iterates_a_snapshot():
    grown = [1, 2, 3]

    class GrowingWalker:
        def _get_id(self, obj):
            return str(obj)

        def __call__(self, obj):
            grown.append(len(grown))  # element walk appends to the list
            return str(obj)

    with finishes_within(30):
        _, relations = ListRelationalizer().relationalize(grown, GrowingWalker())
    assert len(relations) == 3


def test_dict_relationalizer_iterates_a_snapshot():
    grown = {"a": 1}

    class GrowingWalker:
        def _get_id(self, obj):
            return str(obj)

        def _walk(self, obj):
            grown[len(grown)] = None  # key/value walk inserts a new entry
            return str(obj)

    _, relations = DictRelationalizer().relationalize(grown, GrowingWalker())
    assert len(relations) == 1


def test_set_relationalizer_iterates_a_snapshot():
    grown = {1, 2, 3}

    class GrowingWalker:
        def _get_id(self, obj):
            return str(obj)

        def __call__(self, obj):
            grown.add(len(grown) + 10)  # element walk inserts a new member
            return str(obj)

    _, relations = SetRelationalizer().relationalize(grown, GrowingWalker())
    assert len(relations) == 3
