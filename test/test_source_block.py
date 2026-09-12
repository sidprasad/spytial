"""The `source` block: the rule as its author wrote it, carried into the spec.

Spec language 2026-08-25 (spytial-core 5.4.3) lets every block-bodied item
carry a `source` block, and conflict reports cite it in place of the engine's
own rendering of the rule. The value of that is entirely in the text being the
author's own, so what these tests hold is that what comes back is what is on
the page -- not a plausible reconstruction of it, and not the normalized form
the spec ended up carrying.

The two halves that are easy to get wrong, and are checked hardest here, are
the ones where the block interacts with machinery that reads whole payloads:
de-duplication, which would stop collapsing identical rules the moment they
started carrying where they were written, and the style-collision advisory,
which would start reporting rules as disagreeing about their own source text.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import spytial
from spytial import _source
from spytial._spec_tables import SOURCE_SUPPORTED_BY, SCALAR_ITEMS
from spytial.annotations import _strip_source

REPO_ROOT = Path(__file__).resolve().parent.parent


def _source_of(entry, item):
    """The source block on a registry entry, or None."""
    payload = entry[item]
    return payload.get("source") if isinstance(payload, dict) else None


# --------------------------------------------------------------------------- #
# What the author wrote
# --------------------------------------------------------------------------- #

A_SELECTOR = "{x : Node, y : Node | x.left = y}"


@spytial.orientation(selector=A_SELECTOR, directions=["below"])
class WrittenWithAName:
    pass


@spytial.cyclic(
    selector="ring",
    direction="clockwise",
)
class WrittenAcrossLines:
    pass


def test_the_text_is_the_decorator_as_written():
    entry = WrittenWithAName.__spytial_registry__["constraints"][0]
    block = _source_of(entry, "orientation")
    assert block["text"] == (
        '@spytial.orientation(selector=A_SELECTOR, directions=["below"])'
    )


def test_a_name_is_not_expanded_into_its_value():
    """The point of reading the file rather than rebuilding the call.

    The reader follows `location` to a line that says `A_SELECTOR`. Handing
    them the expanded selector would describe a line that is not there.
    """
    block = _source_of(
        WrittenWithAName.__spytial_registry__["constraints"][0], "orientation"
    )
    assert "A_SELECTOR" in block["text"]
    assert A_SELECTOR not in block["text"]
    # The spec itself still carries the real selector.
    assert (
        WrittenWithAName.__spytial_registry__["constraints"][0]["orientation"][
            "selector"
        ]
        == A_SELECTOR
    )


def test_a_decorator_written_across_lines_comes_back_whole():
    """A frame reports one line; the rule occupies four."""
    entry = WrittenAcrossLines.__spytial_registry__["constraints"][0]
    block = _source_of(entry, "cyclic")
    assert block["text"] == (
        "@spytial.cyclic(\n"
        '    selector="ring",\n'
        '    direction="clockwise",\n'
        ")"
    )


def test_location_is_a_basename_and_the_decorator_line():
    """A basename, not a path: the spec ships inside an HTML file people mail around."""
    block = _source_of(
        WrittenWithAName.__spytial_registry__["constraints"][0], "orientation"
    )
    name, _, line = block["location"].rpartition(":")
    assert name == "test_source_block.py"
    written = Path(__file__).read_text(encoding="utf-8").splitlines()[int(line) - 1]
    assert written.strip().startswith("@spytial.orientation(selector=A_SELECTOR")


# --------------------------------------------------------------------------- #
# Which forms carry one
# --------------------------------------------------------------------------- #


def test_every_block_bodied_form_carries_one_and_the_scalar_does_not():
    """SOURCE_SUPPORTED_BY is the manifest's answer; this is spytial obeying it.

    `flag` serializes as a bare value (`- flag: hideDisconnected`) with nowhere
    to put a block, and is the one item the manifest leaves out.
    """
    assert "flag" not in SOURCE_SUPPORTED_BY
    assert set(SCALAR_ITEMS) == {"flag"}

    @spytial.orientation(selector="a", directions=["below"])
    @spytial.hideField(field="_private")
    @spytial.flag(name="hideDisconnected")
    class Mixed:
        pass

    registry = Mixed.__spytial_registry__
    assert _source_of(registry["constraints"][0], "orientation")
    directives = {
        item: payload
        for entry in registry["directives"]
        for item, payload in entry.items()
    }
    assert "source" in directives["hideField"]
    assert directives["flag"] == "hideDisconnected"


def test_nothing_outside_the_manifests_list_is_stamped():
    """A form core would parse-and-ignore a source on gets no source."""
    for cls, item in _one_of_every_form():
        entry = _entry_for(cls, item)
        payload = entry[item]
        if not isinstance(payload, dict):
            continue
        assert ("source" in payload) == (item in SOURCE_SUPPORTED_BY), item


def _one_of_every_form():
    @spytial.orientation(selector="a", directions=["below"])
    @spytial.flag(name="hideDisconnected")
    @spytial.tag(toTag="Node", name="depth", value="d")
    class Sample:
        pass

    for section in ("constraints", "directives"):
        for entry in Sample.__spytial_registry__[section]:
            for item in entry:
                yield Sample, item


def _entry_for(cls, item):
    for section in ("constraints", "directives"):
        for entry in cls.__spytial_registry__[section]:
            if item in entry:
                return entry
    raise AssertionError(item)


# --------------------------------------------------------------------------- #
# The other authoring paths
# --------------------------------------------------------------------------- #


def test_an_instance_annotation_records_self_not_the_object_id():
    """`selector='self'` is what was written; `obj_N` is what it became."""
    obj = type("Thing", (), {})()
    spytial.annotate_group(obj, selector="self", name="root")

    entry = spytial.collect_decorators(obj)["constraints"][0]
    assert entry["group"]["selector"].startswith("obj_")
    assert entry["group"]["source"]["text"] == (
        "spytial.group(selector='self', name='root')"
    )


def test_an_annotated_alias_records_the_class_form():
    """In `Annotated[...]` the author wrote a class, not a decorator."""
    alias = __import__("typing").Annotated[
        list, spytial.Align(selector="items", direction="horizontal")
    ]
    entry = spytial.extract_spytial_annotations(alias)["constraints"][0]
    assert entry["align"]["source"]["text"] == (
        "Align(selector='items', direction='horizontal')"
    )
    assert entry["align"]["source"]["location"].startswith("test_source_block.py:")


def test_a_deprecated_spelling_records_what_was_written_not_the_rewrite():
    """The block is a record of the authoring site, which the rewrite is not."""
    with pytest.warns(DeprecationWarning):

        @spytial.atomColor(selector="Node", value="red")
        class Old:
            pass

    # Whatever the rewrite produced, the text still quotes the decorator.
    entry = Old.__spytial_registry__["directives"][0]
    (item,) = entry
    assert entry[item]["source"]["text"].startswith("@spytial.atomColor(")


# --------------------------------------------------------------------------- #
# Machinery that reads whole payloads
# --------------------------------------------------------------------------- #


@spytial.orientation(selector="p", directions=["below"])
class Parent:
    pass


@spytial.orientation(selector="p", directions=["below"])
class Sub(Parent):
    pass


def test_identical_rules_still_collapse_to_one():
    """The same rule on a class and its parent is one rule, not two.

    Without excluding `source` from the comparison this is the regression that
    lands the moment the block is introduced: two rules that differ in nothing
    a layout can see, because they were written on different lines.
    """
    constraints = spytial.collect_decorators(Sub())["constraints"]
    assert len(constraints) == 1


def test_the_surviving_rule_keeps_the_first_source():
    """Core de-duplicates and keeps the first source it was given; so does this."""
    constraints = spytial.collect_decorators(Sub())["constraints"]
    location = constraints[0]["orientation"]["source"]["location"]
    line = int(location.rpartition(":")[2])
    written = Path(__file__).read_text(encoding="utf-8").splitlines()[line - 1]
    # Sub is the object's own class, so its own rule is the one collected first.
    assert written.strip() == '@spytial.orientation(selector="p", directions=["below"])'
    assert Path(__file__).read_text(encoding="utf-8").splitlines()[line].strip() == (
        "class Sub(Parent):"
    )


def test_two_identical_style_rules_do_not_read_as_a_conflict():
    """The style-collision advisory must not compare source blocks.

    Two atomStyle rules setting the same property to the same value are not a
    collision. They are written on different lines, so their source texts
    differ -- and a walker that treats every leaf as a style property would
    report them as disagreeing about `source.text`.
    """
    import warnings

    @spytial.atomStyle(selector="Node", fillStyle=spytial.FillStyle(color="red"))
    class First:
        pass

    @spytial.atomStyle(selector="Node", fillStyle=spytial.FillStyle(color="red"))
    class Second(First):
        pass

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        spytial.collect_decorators(Second())


def test_a_genuine_style_conflict_is_still_reported():
    """Guards the test above against passing because nothing warns any more."""

    @spytial.atomStyle(selector="Node", fillStyle=spytial.FillStyle(color="red"))
    class First:
        pass

    @spytial.atomStyle(selector="Node", fillStyle=spytial.FillStyle(color="blue"))
    class Second(First):
        pass

    with pytest.warns(UserWarning, match="fillStyle.color"):
        spytial.collect_decorators(Second())


# --------------------------------------------------------------------------- #
# Turning it off
# --------------------------------------------------------------------------- #


def test_no_source_env_var_emits_exactly_what_5_2_1_did():
    """The whole feature is skippable, and what it adds is only the block.

    Run in a subprocess: the decorators run at import, so the switch has to be
    set before spytial is imported to mean anything.
    """
    program = textwrap.dedent(
        """
        import json, spytial

        @spytial.orientation(selector='p', directions=['below'])
        @spytial.atomColor(selector='n', value='red')
        class C: pass

        print(json.dumps(C.__spytial_registry__, sort_keys=True))
        """
    )

    def run(env_extra):
        import os

        env = dict(os.environ, PYTHONPATH=str(REPO_ROOT), **env_extra)
        out = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        return json.loads(out.stdout)

    with_source = run({})
    without = run({"SPYTIAL_NO_SOURCE": "1"})

    assert with_source != without
    stripped = {
        section: [
            {
                item: {k: v for k, v in payload.items() if k != "source"}
                for item, payload in entry.items()
            }
            for entry in entries
        ]
        for section, entries in with_source.items()
    }
    assert stripped == without


# --------------------------------------------------------------------------- #
# When there is no source to read
# --------------------------------------------------------------------------- #


def test_a_rule_written_in_a_repl_still_carries_its_text():
    """`exec` of a string has no file to read back, and must not lose the block."""
    namespace = {"spytial": spytial}
    exec(
        "@spytial.orientation(selector='x', directions=['below'])\n"
        "class Dynamic: pass\n",
        namespace,
    )
    entry = namespace["Dynamic"].__spytial_registry__["constraints"][0]
    block = entry["orientation"]["source"]
    assert block["text"] == (
        "spytial.orientation(selector='x', directions=['below'])"
    )
    # Nowhere to send anyone, so no location rather than a fabricated one.
    assert "location" not in block


def test_an_unparseable_file_falls_back_rather_than_raising(tmp_path):
    """The AST read is best-effort; a file it cannot parse is not an error."""
    assert _source._decorator_spans(str(tmp_path / "nope.py"), None) == (0, ())

    unparseable = tmp_path / "broken.py"
    unparseable.write_text("def (:\n", encoding="utf-8")
    line_count, spans = _source._decorator_spans(
        str(unparseable), _source._mtime(str(unparseable))
    )
    # Readable but not parseable: no decorator text, but the file is there, so
    # a location pointing into it is still good.
    assert spans == ()
    assert line_count == 1


def test_no_location_when_the_file_behind_the_frame_is_gone():
    """A module can run from bytecode whose .py has been moved or deleted.

    `co_filename` still looks like a real path, so the location would cite a
    file that is not there -- and the reader would be sent to look at nothing.
    """
    namespace = {"spytial": spytial}
    code = compile(
        "@spytial.orientation(selector='x', directions=['below'])\nclass Gone: pass\n",
        "/nonexistent/ghost.py",
        "exec",
    )
    exec(code, namespace)

    block = namespace["Gone"].__spytial_registry__["constraints"][0]["orientation"][
        "source"
    ]
    assert block["text"] == "spytial.orientation(selector='x', directions=['below'])"
    assert "location" not in block


def test_no_location_for_a_line_past_the_end_of_the_file(tmp_path):
    """A stale .pyc can report a line the current file does not reach."""
    short = tmp_path / "short.py"
    short.write_text("x = 1\n", encoding="utf-8")
    text, real_line = _source._read(str(short), 500)
    assert text is None
    assert not real_line


# --------------------------------------------------------------------------- #
# The class form records the call, not what the call was turned into
# --------------------------------------------------------------------------- #


def test_a_style_block_is_recorded_as_the_block_not_as_a_dict():
    """Subclasses coerce style blocks to plain dicts before the base sees them.

    `Annotated[...]` rules are calls rather than decorators, so they always
    use the reconstructed text -- which makes this the only record of them.
    """
    rule = spytial.Group(
        selector="Team.members",
        name="Team",
        addEdge=spytial.GroupEdge(
            points="togroup", lineStyle=spytial.LineStyle(pattern="dashed")
        ),
    )
    assert rule._source["text"] == (
        "Group(selector='Team.members', name='Team', "
        "addEdge=GroupEdge(points='togroup', lineStyle=LineStyle(pattern='dashed')))"
    )


def test_unset_style_fields_are_not_invented():
    """The generated dataclass repr spells every field, including the None ones."""
    assert _source._render_value(spytial.LineStyle(color="red")) == (
        "LineStyle(color='red')"
    )


def test_a_deprecated_class_records_the_spelling_that_was_written():
    """The rewrite happens before the base constructor; the text must precede it."""
    with pytest.warns(DeprecationWarning):
        rule = spytial.AtomColor(selector="Node", value="red")

    # The entry is rewritten to atomStyle/borderStyle, as it should be.
    assert _strip_source(rule.to_entry()) == {
        "atomStyle": {"selector": "Node", "borderStyle": {"color": "red"}}
    }
    # The source still quotes what is on the page.
    assert rule._source["text"] == "AtomColor(selector='Node', value='red')"


def test_the_block_is_omitted_rather_than_emitted_empty():
    """Core ignores a source whose text is empty, so spytial writes none."""
    assert _source.describe("orientation", {}, fallback="   ") is None


# --------------------------------------------------------------------------- #
# What core does with it
# --------------------------------------------------------------------------- #


def test_the_emitted_block_satisfies_the_core_schema():
    """Core's own schema, which is stricter than its parser.

    The parser ignores what it does not recognize, so a malformed source block
    would reach it, be dropped, and leave conflict reports quietly describing
    rules in the engine's words -- the exact failure this feature exists to
    remove, arriving with nothing to report it.
    """
    jsonschema = pytest.importorskip("jsonschema", reason="optional dev dependency")
    schema = json.loads(
        (REPO_ROOT / "spytial" / "_vendor" / "spytial-spec.schema.json").read_text(
            encoding="utf-8"
        )
    )
    schema.pop("$id", None)
    validator = jsonschema.Draft202012Validator(schema)

    @spytial.orientation(selector="children", directions=["below"])
    @spytial.group(selector="Team.members", name="Team")
    @spytial.hideAtom(selector="Internal")
    @spytial.atomStyle(selector="Dir", fillStyle=spytial.FillStyle(color="#eef6ff"))
    class Stamped:
        pass

    registry = Stamped.__spytial_registry__
    stamped = [
        payload
        for section in registry.values()
        for entry in section
        for payload in entry.values()
        if isinstance(payload, dict) and "source" in payload
    ]
    assert len(stamped) == 4, "every form here accepts a source"

    errors = list(validator.iter_errors(registry))
    assert not errors, "\n".join(
        f"at {list(e.absolute_path)}: {e.message}" for e in errors[:5]
    )


def test_the_schema_rejects_a_malformed_block():
    """Guards the check above against being vacuous."""
    jsonschema = pytest.importorskip("jsonschema", reason="optional dev dependency")
    schema = json.loads(
        (REPO_ROOT / "spytial" / "_vendor" / "spytial-spec.schema.json").read_text(
            encoding="utf-8"
        )
    )
    schema.pop("$id", None)
    validator = jsonschema.Draft202012Validator(schema)

    def spec(source):
        return {
            "constraints": [
                {
                    "orientation": {
                        "selector": "a",
                        "directions": ["below"],
                        "source": source,
                    }
                }
            ],
            "directives": [],
        }

    assert not list(validator.iter_errors(spec({"text": "@spytial.orientation(...)"})))
    # Core's own normalizer drops a block with empty or missing text and keeps
    # `location` only when it is a non-empty string; the schema says the same.
    assert list(validator.iter_errors(spec({"text": ""})))
    assert list(validator.iter_errors(spec({"location": "tree.py:1"})))
    assert list(validator.iter_errors(spec({"text": "x", "extra": 1})))


def test_a_source_block_does_not_change_what_a_spec_entails():
    """Carrying the author's text must be inert to the solver.

    `source` is documentation the engine displays, not a constraint. This runs
    the same shape through spytial-core's own harness with and without one and
    asks it what the spec entails, rather than trusting that an ignored-looking
    key is ignored.
    """
    conformance = pytest.importorskip("conformance")
    if not conformance.NODE or not conformance.CHECK_BIN:
        pytest.skip("conformance harness unavailable (no node runtime)")

    @spytial.orientation(
        selector="{x : Chain, y : Chain | y in x.kids.idx[int]}", directions=["below"]
    )
    class Chain:
        def __init__(self, name, kids=None):
            self.name = name
            self.kids = kids or []

    root = Chain("a", [Chain("b")])
    assertions = [
        {
            "query": "must.below(n0)",
            "contains": ["n2"],
            "because": "the child is below its parent in every permitted layout",
        }
    ]

    case = conformance.case("with-source", root, assertions)
    assert "source:" in case["spec"], "the fixture must actually carry one"
    with_source = conformance.run_cases([case])["cases"][0]

    # Strip the block structurally and re-serialize. Filtering the YAML by line
    # would cut a wrapped source text in half and prove only that broken YAML
    # fails.
    collected = spytial.collect_decorators(root)
    bare = {
        section: [
            {
                item: (
                    {k: v for k, v in payload.items() if k != "source"}
                    if isinstance(payload, dict)
                    else payload
                )
                for item, payload in entry.items()
            }
            for entry in entries
        ]
        for section, entries in collected.items()
    }
    stripped = dict(
        case,
        name="without-source",
        spec=spytial.serialize_to_yaml_string(bare),
    )
    assert "source:" not in stripped["spec"]
    without = conformance.run_cases([stripped])["cases"][0]

    assert with_source["ok"], conformance.explain(with_source)
    assert without["ok"], conformance.explain(without)
    assert [a["actual"] for a in with_source["assertions"]] == [
        a["actual"] for a in without["assertions"]
    ]


def test_source_text_survives_non_ascii_in_the_file(tmp_path):
    """Column offsets in the AST are utf-8 byte offsets, not character offsets.

    The slicing here is hand-rolled -- ast.get_source_segment re-splits the
    whole file per decorator, which made importing a module with a few hundred
    of them quadratic. Handling the byte offsets is the part that was being
    relied on, so a file with multi-byte characters before and inside the
    decorator is the case that proves the replacement.
    """
    module = tmp_path / "accented.py"
    module.write_text(
        "# coding: utf-8\n"
        "import spytial\n"
        "\n"
        "CAFÉ = 'Café'  # multi-byte characters before the decorator\n"
        "\n"
        "@spytial.group(selector='Café.membres', name='équipe')\n"
        "class Réunion:\n"
        "    pass\n",
        encoding="utf-8",
    )

    sys.path.insert(0, str(tmp_path))
    try:
        import importlib

        accented = importlib.import_module("accented")
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("accented", None)

    block = accented.Réunion.__spytial_registry__["constraints"][0]["group"]["source"]
    assert block["text"] == "@spytial.group(selector='Café.membres', name='équipe')"
    assert block["location"] == "accented.py:6"


def test_one_parse_per_file_however_many_decorators(tmp_path):
    """The file is read and parsed once, not once per rule.

    Guards the cache that makes the AST read affordable: without it every
    decorator in a module re-parses that module.
    """
    module = tmp_path / "several.py"
    module.write_text(
        "import spytial\n"
        + "".join(
            f"@spytial.orientation(selector='s{i}', directions=['below'])\n"
            f"class C{i}: pass\n"
            for i in range(20)
        ),
        encoding="utf-8",
    )

    _source._decorator_spans.cache_clear()
    sys.path.insert(0, str(tmp_path))
    try:
        import importlib

        importlib.import_module("several")
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("several", None)

    info = _source._decorator_spans.cache_info()
    assert info.misses == 1, "the file was parsed more than once"
    assert info.hits == 19


def test_a_notebook_cell_gets_its_text_and_no_location(tmp_path):
    """ipykernel writes each cell to a real file with a meaningless name.

    `1976988758.py:12` names nothing a reader can open -- and the directory is
    deleted when the kernel exits. The text is still worth quoting; the path
    is not.
    """
    cell_dir = tmp_path / "ipykernel_8231"
    cell_dir.mkdir()
    cell = cell_dir / "1976988758.py"
    cell.write_text(
        "@spytial.orientation(\n"
        "    selector='x',\n"
        "    directions=['below'],\n"
        ")\n"
        "class Cell: pass\n",
        encoding="utf-8",
    )

    namespace = {"spytial": spytial}
    exec(compile(cell.read_text(encoding="utf-8"), str(cell), "exec"), namespace)

    block = namespace["Cell"].__spytial_registry__["constraints"][0]["orientation"][
        "source"
    ]
    assert block["text"] == (
        "@spytial.orientation(\n    selector='x',\n    directions=['below'],\n)"
    )
    assert "location" not in block


def test_an_ordinary_file_in_a_normal_directory_still_gets_one():
    """Guards the check above against dropping every location."""
    block = _source_of(
        WrittenWithAName.__spytial_registry__["constraints"][0], "orientation"
    )
    assert block["location"].startswith("test_source_block.py:")
