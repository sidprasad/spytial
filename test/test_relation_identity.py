"""Stored relation IDs survive Python export and core 6 normalization."""

import json
import os
import subprocess

import pytest

from spytial import Atom, CnDDataInstanceBuilder, Relation, RelationalizerBase, reify
from spytial.provider_system import RelationalizerRegistry
from spytial.suggest import _eval


@pytest.fixture
def build(monkeypatch):
    class Example:
        pass

    class ExampleRelationalizer(RelationalizerBase):
        def can_handle(self, obj):
            return isinstance(obj, Example)

        def declared_relations(self, obj):
            return obj.declared

        def relationalize(self, obj, walker):
            source = walker._get_id(obj)
            return [Atom(source, "Example", "example")], [
                Relation(name, [source, *[walker(v) for v in values]], id=rid)
                for rid, name, values in obj.records
            ]

    monkeypatch.setattr(
        RelationalizerRegistry, "_instances",
        [ExampleRelationalizer(), *RelationalizerRegistry._instances],
    )
    builder = CnDDataInstanceBuilder()

    def build_records(records, declared=()):
        obj = Example()
        obj.records, obj.declared = records, declared
        return builder.build_instance(obj)

    return build_records


def test_same_name_different_ids_survive(build):
    datum = build([("left:edge", "edge", [1]), ("right:edge", "edge", [2])])
    assert [(r["id"], r["name"]) for r in datum["relations"]] == [
        ("left:edge", "edge"), ("right:edge", "edge"),
    ]
    assert [r["tuples"][0]["atoms"][1] for r in datum["relations"]] == ["1", "2"]


def test_same_id_merges_and_deduplicates_tuples(build):
    datum = build([
        ("owner:edge", "edge", [1]),
        ("owner:edge", "edge", [2]),
        ("owner:edge", "edge", [1]),
    ])
    assert len(datum["relations"]) == 1
    assert len(datum["relations"][0]["tuples"]) == 2


def test_same_id_conflicting_names_rejected_and_builder_recovers(build):
    with pytest.raises(ValueError, match="conflicting names"):
        build([("shared", "first", [1]), ("shared", "second", [2])])
    assert build([("shared", "second", [2])])["relations"][0]["name"] == "second"


def test_omitted_id_retains_name_grouping(build):
    datum = build([(None, "edge", [1]), (None, "edge", [2])])
    assert len(datum["relations"]) == 1
    assert datum["relations"][0]["id"] == "edge"
    assert Relation("edge", ["a", "b"], id="owner:edge").to_tuple() == (
        "edge", "a", "b",
    )


def test_declared_name_populated_by_qualified_id_has_no_phantom_record(build):
    datum = build([("owner:edge", "edge", [1])], declared=["edge", "empty"])
    assert [(r["id"], r["name"]) for r in datum["relations"]] == [
        ("owner:edge", "edge"), ("empty", "empty"),
    ]


def test_declared_name_cannot_collide_with_another_records_id(build):
    with pytest.raises(ValueError, match="conflicts with declared relation"):
        build([("empty", "edge", [1])], declared=["empty"])


def test_ragged_relation_has_no_column_signature(build):
    datum = build([("owner:edge", "edge", [1]), ("owner:edge", "edge", [1, 2])])
    relation = datum["relations"][0]
    assert relation["types"] == []
    assert [len(t["atoms"]) for t in relation["tuples"]] == [2, 3]


def test_reify_same_named_fields_from_distinct_records():
    class Cell:
        def __init__(self, value):
            self.value = value

    datum = CnDDataInstanceBuilder().build_instance([Cell(1), Cell(2)])
    value = next(r for r in datum["relations"] if r["name"] == "value")
    datum["relations"].remove(value)
    for i, tup in enumerate(value["tuples"]):
        datum["relations"].append({**value, "id": f"cell:{i}:value", "tuples": [tup]})
    assert [cell.value for cell in reify(datum)] == [1, 2]


@pytest.mark.skipif(not _eval.is_available(), reason="requires Node evaluator")
def test_core_preserves_records_but_selectors_union_by_name(build):
    datum = build([
        ("left:edge", "edge", [1]),
        ("right:edge", "edge", [1]),
        ("right:edge", "edge", [2]),
    ])
    # Exercise normalization/reification as well as query evaluation: a query
    # alone would still pass if core had collapsed the stored identities.
    script = """
const fs = require('fs');
const {JSONDataInstance, SGraphQueryEvaluator} = require(process.argv[1]);
const datum = new JSONDataInstance(JSON.parse(fs.readFileSync(0, 'utf8')));
const evaluator = new SGraphQueryEvaluator();
evaluator.initialize({sourceData: datum});
process.stdout.write(JSON.stringify({
    relations: datum.reify().relations,
    count: evaluator.evaluate('#edge').singleResult(),
}));
"""
    proc = subprocess.run(
        [_eval._node_bin(), "-e", script, str(_eval._VENDORED_EVALUATOR)],
        input=json.dumps(datum), text=True, capture_output=True, check=True,
    )
    result = json.loads(proc.stdout)
    assert result["relations"] == datum["relations"]
    assert result["count"] == 2


def test_suggestion_vocabulary_covers_every_same_named_record(build):
    from spytial.suggest._enrich_from_examples import _vocabulary

    datum = build([("a", "edge", [1]), ("b", "edge", [1, 2])])
    assert _vocabulary([datum])["relations"] == [("edge", 3)]
    datum["relations"].reverse()
    assert _vocabulary([datum])["relations"] == [("edge", 3)]
    ragged = build([("a", "edge", [1]), ("a", "edge", [1, 2])])
    assert _vocabulary([ragged])["relations"] == [("edge", 3)]


@pytest.mark.skipif(not _eval.is_available(), reason="requires Node evaluator")
def test_shim_vocabulary_unions_tuples_and_uses_tuple_arities(build):
    datum = build([
        ("a", "edge", [1]), ("b", "edge", [1]), ("b", "edge", [1, 2]),
    ])
    proc = subprocess.run(
        [_eval._node_bin(), str(_eval._SHIM)],
        input=json.dumps({"datum": datum, "selectors": ["edge"]}),
        env={**os.environ, "SPYTIAL_EVALUATOR_MODULE": str(_eval._VENDORED_EVALUATOR)},
        text=True, capture_output=True, check=True,
    )
    result = json.loads(proc.stdout)
    assert result["vocabulary"]["relations"] == [
        {"name": "edge", "arity": 3, "tuples": 2},
    ]
    assert result["results"][0]["arity"] == 3
