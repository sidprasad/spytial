"""Python reconstruction does not depend on core's removed IAtom.metadata."""

import enum
import json
import math
import subprocess
from dataclasses import dataclass

import pytest

from spytial import CnDDataInstanceBuilder, reify
from spytial.suggest import _eval


@dataclass
class Cell:
    value: int
    next: object = None


class Color(enum.Enum):
    RED = 1


def _assert_no_atom_metadata(datum):
    assert all("metadata" not in atom for atom in datum["atoms"])
    for typ in datum.get("types", []):
        assert all("metadata" not in atom for atom in typ["atoms"])


@pytest.mark.parametrize("value", [Cell(4), Color.RED, math, len, Cell, [1, 2], {"x": 3}])
def test_export_and_reify_do_not_need_atom_metadata(value):
    datum = CnDDataInstanceBuilder().build_instance(value)
    _assert_no_atom_metadata(datum)
    restored = reify(json.loads(json.dumps(datum)))
    if value is math or value is len or value is Cell or value is Color.RED:
        assert restored is value
    else:
        assert restored == value


def test_user_field_named_metadata_is_an_ordinary_relation():
    @dataclass
    class WithMetadata:
        metadata: str

    datum = CnDDataInstanceBuilder().build_instance(WithMetadata("user data"))
    _assert_no_atom_metadata(datum)
    assert any(r["name"] == "metadata" for r in datum["relations"])
    assert reify(datum).metadata == "user data"


def test_reify_ignores_atom_metadata_in_external_data():
    datum = CnDDataInstanceBuilder().build_instance(Cell(4))
    for atom in datum["atoms"]:
        atom["metadata"] = {"__module__": "builtins", "__qualname__": "dict"}
    restored = reify(datum)
    assert type(restored) is Cell
    assert restored == Cell(4)


@pytest.mark.skipif(not _eval.is_available(), reason="requires Node evaluator")
def test_core_json_round_trip_preserves_python_reconstruction_without_metadata():
    cell = Cell(4)
    cell.next = cell
    datum = CnDDataInstanceBuilder().build_instance([cell, cell, Color.RED, math, len])
    _assert_no_atom_metadata(datum)
    script = """
const fs = require('fs');
const {JSONDataInstance} = require(process.argv[1]);
const datum = new JSONDataInstance(JSON.parse(fs.readFileSync(0, 'utf8')));
process.stdout.write(JSON.stringify(datum.reify()));
"""
    proc = subprocess.run(
        [_eval._node_bin(), "-e", script, str(_eval._VENDORED_EVALUATOR)],
        input=json.dumps(datum), text=True, capture_output=True, check=True,
    )
    normalized = json.loads(proc.stdout)
    _assert_no_atom_metadata(normalized)
    # rootId is Python's envelope field, not part of core's reify() output.
    restored = reify(normalized, root_id=datum["rootId"])
    assert type(restored[0]) is Cell
    assert restored[0].value == 4
    assert restored[0] is restored[1]
    assert restored[0].next is restored[0]
    assert restored[2] is Color.RED
    assert restored[3] is math
    assert restored[4] is len
