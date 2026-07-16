"""Object-annotation / object-id registries must not leak across `id()` reuse.

Built-in values that can't store attributes (list, dict, tuple, set) keep their
annotations and self-reference ids in process-global maps. Those maps used to be
keyed by raw ``id(obj)``, so once an annotated object was garbage-collected a new
object could reuse its id and silently inherit the dead object's annotations.

The fix keys those maps through ``_IdentityKeyedRegistry``, which retains a
reference to each object (a weakref with an evicting finalizer where possible, a
strong reference that pins the id otherwise) and verifies identity on read.
"""

import gc

import pytest

import spytial.annotations as ann
from spytial.annotations import (
    _IdentityKeyedRegistry,
    annotate_orientation,
    annotate_group,
    collect_decorators,
    reset_object_ids,
)


@pytest.fixture(autouse=True)
def _clean_registries():
    reset_object_ids()
    yield
    reset_object_ids()


# ---------------------------------------------------------------------------
# Unit tests on the registry helper
# ---------------------------------------------------------------------------


def test_weakreffable_entry_is_evicted_on_gc():
    reg = _IdentityKeyedRegistry()

    class Obj:  # weak-referenceable
        pass

    o = Obj()
    reg.set(o, "v")
    assert reg.get(o) == "v"
    assert len(reg._entries) == 1

    del o
    gc.collect()
    # The weakref finalizer drops the entry the moment the object dies, so its
    # id can never be both freed and still mapped.
    assert len(reg._entries) == 0


def test_unweakreffable_entry_is_pinned_by_strong_ref():
    reg = _IdentityKeyedRegistry()
    lst = [1, 2, 3]  # lists support neither setattr nor weakref
    reg.set(lst, "v")
    assert reg.get(lst) == "v"

    del lst
    gc.collect()
    # A list can't be weak-referenced, so the registry holds it strongly: the
    # entry (and the object's id) is pinned, which is what prevents reuse.
    assert len(reg._entries) == 1

    reg.clear()
    assert len(reg._entries) == 0


def test_identity_guard_rejects_foreign_object():
    reg = _IdentityKeyedRegistry()
    a = [1]
    reg.set(a, "A")
    assert a in reg
    # A different object never reads A's value.
    assert reg.get([1]) is None
    assert ([1] in reg) is False


def test_reused_id_does_not_leak():
    # Deterministically emulate id reuse: move an entry so an id slot maps to a
    # value whose stored object is *not* the one we look up under that id.
    reg = _IdentityKeyedRegistry()

    class Box:
        pass

    keeper = Box()
    reg.set(keeper, "keeper-value")
    other = Box()
    reg._entries[id(other)] = reg._entries.pop(id(keeper))

    # id(other) now maps to an entry whose live object is `keeper`, not `other`.
    assert reg.get(other) is None             # identity guard rejects it
    assert id(other) not in reg._entries       # and evicts the stale slot


# ---------------------------------------------------------------------------
# End-to-end through the public annotate_* / collect_decorators API
# ---------------------------------------------------------------------------


def test_fresh_builtins_never_inherit_phantom_annotations():
    a = {"x": 1}
    annotate_orientation(a, selector="k", directions=["left"])
    assert len(collect_decorators(a)["constraints"]) == 1

    # Many fresh, never-annotated builtins must all come back clean — even if
    # one reuses the id of a value created earlier in this loop.
    for _ in range(200):
        assert collect_decorators({"y": 2})["constraints"] == []
        assert collect_decorators([0, 0])["constraints"] == []
        assert collect_decorators((9, 9))["constraints"] == []


def test_set_annotation_evicted_after_gc():
    s = {1, 2, 3}  # set: weak-referenceable, not attribute-storable
    annotate_group(s, field="elements", groupOn=0, addToGroup=1)
    assert len(collect_decorators(s)["constraints"]) == 1

    before = len(ann._OBJECT_ANNOTATION_REGISTRY._entries)
    assert before == 1
    del s
    gc.collect()
    assert len(ann._OBJECT_ANNOTATION_REGISTRY._entries) == before - 1


def test_distinct_builtins_keep_independent_annotations():
    a = [1, 2, 3]
    b = [1, 2, 3]  # equal but distinct object
    annotate_orientation(a, selector="a", directions=["left"])
    annotate_orientation(b, selector="b", directions=["below"])

    a_sel = collect_decorators(a)["constraints"][0]["orientation"]["selector"]
    b_sel = collect_decorators(b)["constraints"][0]["orientation"]["selector"]
    assert a_sel == "a"
    assert b_sel == "b"
    assert len(collect_decorators(a)["constraints"]) == 1
    assert len(collect_decorators(b)["constraints"]) == 1


def test_reset_object_ids_clears_annotation_registry():
    a = [1, 2]
    annotate_orientation(a, selector="items", directions=["left"])
    assert collect_decorators(a)["constraints"]

    reset_object_ids()
    # reset now clears the annotation registry too, not just the id registry.
    assert collect_decorators(a)["constraints"] == []


def test_self_reference_id_resolves_via_global_id_registry():
    # A set can't store the id attribute, so its self-reference id lives in the
    # global id registry — exercising the provider_system get_id path that reads
    # _OBJECT_ID_REGISTRY (previously uncovered).
    from spytial.annotations import orientation
    from spytial.provider_system import CnDDataInstanceBuilder

    s = orientation(selector="self", directions=["below"])({1, 2, 3})
    sel = collect_decorators(s)["constraints"][0]["orientation"]["selector"]
    assert "obj_" in sel  # an id was assigned and stored in the global registry

    # Walking the set resolves its id through _OBJECT_ID_REGISTRY.get(obj)
    # without raising (regression guard for the helper migration).
    di = CnDDataInstanceBuilder().build_instance({"s": s})
    assert di["atoms"]
