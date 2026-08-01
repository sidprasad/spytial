"""Drift tests between spytial-core's language manifest and the Python surface.

spytial-core publishes ``docs/spytial-language.json``, a machine-readable
description of every constraint and directive its parser reads. It is vendored
at ``spytial/_vendor/spytial-language.json`` and generated into
``spytial/_spec_tables.py`` by ``scripts/generate_spec_tables.py``.

Core's parser ignores what it does not recognize, so a spec that has gone stale
does not fail -- it renders a diagram missing the part that no longer matches,
with no error anywhere. That makes drift between the two sides invisible in
exactly the cases that matter, which is what these tests exist to prevent:

* the checked-in tables still match what the vendored manifest generates,
* the vendored manifest still matches the pinned spytial-core release,
* the hand-written parts of ``annotations.py`` -- the style dataclasses, the
  ``Annotated[...]`` classes, the decorator docstrings -- still agree with the
  generated tables.

A spytial-core bump that changes the language fails here, naming what changed,
rather than shipping a spec core silently drops half of.
"""

import importlib
import inspect
import json
import pathlib
import sys
from dataclasses import fields as dataclass_fields

import pytest

import spytial
from spytial import annotations as ann
from spytial import _spec_tables as tables
from spytial.core_assets import SPYTIAL_CORE_VERSION

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
MANIFEST_PATH = REPO_ROOT / "spytial" / "_vendor" / "spytial-language.json"
GENERATED_PATH = REPO_ROOT / "spytial" / "_spec_tables.py"


def _script(name):
    """Import a module from scripts/, which is not an installed package."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    return importlib.import_module(name)


def _generator():
    return _script("generate_spec_tables")


requires_repo = pytest.mark.skipif(
    not MANIFEST_PATH.exists() or not SCRIPTS_DIR.exists(),
    reason="generator and vendored manifest live in the repo, not the wheel",
)


# --------------------------------------------------------------------------- #
# The generated file is what the manifest says
# --------------------------------------------------------------------------- #


@requires_repo
def test_generated_tables_are_up_to_date():
    """`_spec_tables.py` must be exactly what the vendored manifest generates.

    Byte-for-byte, so an edit to the generated file is caught too: hand-editing
    it would survive until the next regeneration silently reverted it.
    """
    expected = _generator().render()
    actual = GENERATED_PATH.read_text(encoding="utf-8")
    assert actual == expected, (
        "spytial/_spec_tables.py is stale or hand-edited.\n"
        "Regenerate it with: python3 scripts/generate_spec_tables.py"
    )


@requires_repo
def test_vendored_manifest_matches_the_pinned_core_release():
    """The manifest and the browser bundle have to come from the same release.

    They are fetched separately -- the manifest is vendored, the bundle is
    loaded from a CDN by version -- so nothing but this check keeps spytial
    from validating against one version of the language and rendering with
    another.
    """
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["spytialCoreVersion"] == SPYTIAL_CORE_VERSION, (
        f"vendored manifest is from spytial-core {manifest['spytialCoreVersion']} "
        f"but core_assets.py pins {SPYTIAL_CORE_VERSION}. "
        f"Run ./update-spytial-core.sh to bring them back in step."
    )
    assert tables.CORE_VERSION == SPYTIAL_CORE_VERSION


@requires_repo
def test_vendored_schema_matches_the_pinned_core_release():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["x-spytial-core-version"] == SPYTIAL_CORE_VERSION, (
        f"vendored spec schema is from spytial-core "
        f"{schema['x-spytial-core-version']} but core_assets.py pins "
        f"{SPYTIAL_CORE_VERSION}. Run ./update-spytial-core.sh."
    )


@requires_repo
def test_every_vendored_file_came_from_the_pinned_release():
    """The evaluator bundle is the one vendored file with no version of its own.

    It is minified, and nothing in it names a release, so a stale copy is
    invisible on inspection -- which matters because it evaluates the same
    selectors the browser does, from a different build. VENDORED.json carries
    the version and a content hash for it, written at vendor time.
    """
    lock = _script("vendor_lock")
    recorded = json.loads(
        (REPO_ROOT / "spytial" / "_vendor" / "VENDORED.json").read_text(encoding="utf-8")
    )
    assert recorded["spytialCoreVersion"] == SPYTIAL_CORE_VERSION, (
        f"vendored files are from spytial-core {recorded['spytialCoreVersion']} but "
        f"core_assets.py pins {SPYTIAL_CORE_VERSION}. Run ./update-spytial-core.sh."
    )
    for name, entry in recorded["files"].items():
        path = REPO_ROOT / name
        assert path.exists(), f"{name} is recorded as vendored but is missing"
        assert lock.digest(path) == entry["sha256"], (
            f"{name} does not match what was vendored for spytial-core "
            f"{recorded['spytialCoreVersion']}. Either it was edited by hand, or it "
            f"was replaced without re-running ./update-spytial-core.sh."
        )


@requires_repo
def test_vendor_readme_pin_matches():
    """The README states the pin in prose, where it silently goes stale."""
    readme = (REPO_ROOT / "spytial" / "suggest" / "_vendor" / "README.md").read_text(
        encoding="utf-8"
    )
    assert f"Pinned version: **spytial-core {SPYTIAL_CORE_VERSION}**" in readme, (
        f"spytial/suggest/_vendor/README.md does not state the pinned version "
        f"{SPYTIAL_CORE_VERSION}"
    )


@requires_repo
def test_generator_rejects_an_unknown_construct():
    """The generator must fail on a manifest it cannot account for.

    That refusal is what turns a spytial-core feature addition into a build
    error instead of a field the Python side quietly never learns about, so it
    is worth a test of its own.
    """
    generator = _generator()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["items"].append(
        {
            "id": "invented",
            "yamlKey": "invented",
            "label": "Invented",
            "sections": ["constraints"],
            "valueShape": "mapping",
            "fields": [
                {"name": "mode", "type": "enum", "values": ["a", "b"], "required": True}
            ],
        }
    )
    with pytest.raises(generator.ManifestDrift, match="constant name"):
        generator.render(manifest)


# --------------------------------------------------------------------------- #
# The hand-written surface agrees with the generated tables
# --------------------------------------------------------------------------- #

# Style block dataclass per manifest block name.
BLOCK_CLASSES = {
    "textStyle": ann.TextStyle,
    "lineStyle": ann.LineStyle,
    "fillStyle": ann.FillStyle,
    "borderStyle": ann.BorderStyle,
    "iconStyle": ann.IconStyle,
}


def test_every_manifest_block_has_a_dataclass():
    assert set(BLOCK_CLASSES) == set(tables.BLOCKS), (
        "a style block was added or removed upstream; add or drop the matching "
        "dataclass in annotations.py and update BLOCK_CLASSES here"
    )


@pytest.mark.parametrize("block_name", sorted(tables.BLOCKS))
def test_block_dataclass_fields_match_the_manifest(block_name):
    declared = set(tables.BLOCKS[block_name])
    actual = {f.name for f in dataclass_fields(BLOCK_CLASSES[block_name])}
    assert actual == declared, (
        f"{BLOCK_CLASSES[block_name].__name__} accepts {sorted(actual)} but the "
        f"language manifest declares {sorted(declared)}"
    )


@pytest.mark.parametrize("block_name", sorted(tables.BLOCKS))
def test_block_enum_fields_reject_out_of_vocabulary_values(block_name):
    """Core drops an unrecognized block leaf silently, so this is the only check."""
    for field_name, facts in tables.BLOCKS[block_name].items():
        if facts.get("type") != "enum":
            continue
        vocabulary = getattr(tables, facts["enum"])
        block_cls = BLOCK_CLASSES[block_name]
        for value in vocabulary:
            block_cls(**{field_name: value})  # every listed value is accepted
        with pytest.raises(ValueError, match=field_name):
            block_cls(**{field_name: "not-in-the-vocabulary"})


@pytest.mark.parametrize("block_name", sorted(tables.BLOCKS))
def test_block_numeric_bounds_match_the_manifest(block_name):
    for field_name, facts in tables.BLOCKS[block_name].items():
        block_cls = BLOCK_CLASSES[block_name]
        if facts.get("exclusiveMinimum") == 0:
            block_cls(**{field_name: 1})
            for bad in (0, -1):
                with pytest.raises(ValueError, match=field_name):
                    block_cls(**{field_name: bad})
        if facts.get("minimum") is not None and facts.get("maximum") is not None:
            low, high = facts["minimum"], facts["maximum"]
            block_cls(**{field_name: low})
            block_cls(**{field_name: high})
            for bad in (low - 1, high + 1):
                with pytest.raises(ValueError, match=field_name):
                    block_cls(**{field_name: bad})


# --------------------------------------------------------------------------- #
# Every form in the tables is reachable from Python
# --------------------------------------------------------------------------- #

ALL_FORMS = sorted(set(tables.CONSTRAINT_TYPES) | set(tables.DIRECTIVE_TYPES))

# Decorator name -> Annotated[...] class, where the two spellings differ.
ANNOTATION_CLASSES = {
    "orientation": spytial.Orientation,
    "cyclic": spytial.Cyclic,
    "align": spytial.Align,
    "group": spytial.Group,
    "size": spytial.Size,
    "hideAtom": spytial.HideAtom,
    "flag": spytial.Flag,
    "atomStyle": spytial.AtomStyle,
    "atomColor": spytial.AtomColor,
    "edgeStyle": spytial.EdgeStyle,
    "edgeColor": spytial.EdgeColor,
    "attribute": spytial.Attribute,
    "tag": spytial.Tag,
    "hideField": spytial.HideField,
    "inferredEdge": spytial.InferredEdge,
    "icon": spytial.Icon,
    "projection": spytial.Projection,
}


@pytest.mark.parametrize("form", ALL_FORMS)
def test_every_form_has_a_decorator(form):
    assert callable(getattr(spytial, form, None)), (
        f"the language has a `{form}` form with no @spytial.{form} decorator"
    )


@pytest.mark.parametrize("form", ALL_FORMS)
def test_every_form_has_an_annotated_class(form):
    assert form in ANNOTATION_CLASSES, (
        f"the language has a `{form}` form with no Annotated[...] class; "
        f"add one, or add it here if it is deliberately decorator-only"
    )


@pytest.mark.parametrize("form", ALL_FORMS)
def test_annotated_class_accepts_every_field_in_the_tables(form):
    """A field core reads that the class cannot take is unreachable from Python.

    The decorators take ``**kwargs`` and are checked against the tables at call
    time, so they cannot drift. The ``Annotated[...]`` classes spell their
    parameters out, which is where a newly added field goes missing.
    """
    spec = tables.CONSTRAINT_TYPES.get(form) or tables.DIRECTIVE_TYPES[form]
    field_sets = spec if isinstance(spec, list) else [spec]
    allowed = {name for s in field_sets for name in s["required"] + s["optional"]}

    signature = inspect.signature(ANNOTATION_CLASSES[form].__init__)
    parameters = signature.parameters.values()
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters):
        return  # takes **kwargs; the shared validator covers it
    accepted = {
        name for name in signature.parameters if name not in ("self", "hold")
    }
    missing = (allowed - {"hold"}) - accepted
    assert not missing, (
        f"{ANNOTATION_CLASSES[form].__name__} cannot express {sorted(missing)}, "
        f"which spytial-core {tables.CORE_VERSION} reads on `{form}`"
    )


# --------------------------------------------------------------------------- #
# Vocabularies, which are written out in prose in three places
# --------------------------------------------------------------------------- #
#
# Generating the tables means a value core adds starts being *accepted*
# immediately, with no edit anywhere -- which is exactly what makes the prose
# easy to forget. A docstring listing seven of eight orientation directions
# still reads as authoritative, and `help()` is the only reference the
# **kwargs decorators have.

# Vocabulary -> where it is spelled out. ("hold", None) means every constraint
# that accepts `hold`, rather than one named place.
VOCABULARY_PROSE = {
    "ORIENTATION_DIRECTIONS": ("decorator", "orientation"),
    "ROTATION_DIRECTIONS": ("decorator", "cyclic"),
    "ALIGN_DIRECTIONS": ("decorator", "align"),
    "FLAG_NAMES": ("decorator", "flag"),
    "GROUP_EDGE_DIRECTIONS": ("decorator", "group"),
    "LINE_PATTERNS": ("block", "LineStyle"),
    "TEXT_SIZES": ("block", "TextStyle"),
    "ICON_PLACEMENTS": ("block", "IconStyle"),
    "CONSTRAINT_HOLDS": ("hold", None),
}

OPERATIONS_DOC = REPO_ROOT / "docs" / "operations.md"


def _all_vocabularies():
    """Every value vocabulary in the generated tables, found by shape.

    Discovered rather than listed, so a vocabulary core adds shows up here on
    its own and fails the completeness check below instead of going undocumented.
    """
    return {
        name: value
        for name, value in vars(tables).items()
        if name.isupper()
        and isinstance(value, tuple)
        and value
        and all(isinstance(item, str) for item in value)
    }


def _prose_for(kind, name):
    if kind == "decorator":
        return getattr(spytial, name).__doc__ or ""
    if kind == "block":
        return getattr(spytial, name).__doc__ or ""
    raise AssertionError(f"unknown documentation kind {kind!r}")


def test_every_vocabulary_has_a_documented_home():
    assert set(VOCABULARY_PROSE) == set(_all_vocabularies()), (
        "a value vocabulary was added or removed upstream; say where it is "
        "documented in VOCABULARY_PROSE so its values stay checked"
    )


@pytest.mark.parametrize("vocabulary", sorted(VOCABULARY_PROSE))
def test_vocabulary_values_are_spelled_out_in_the_python_docs(vocabulary):
    values = getattr(tables, vocabulary)
    kind, target = VOCABULARY_PROSE[vocabulary]

    if kind == "hold":
        # `hold` is documented per constraint, since that is where it is used.
        for form, spec in tables.CONSTRAINT_TYPES.items():
            field_sets = spec if isinstance(spec, list) else [spec]
            if not any("hold" in s["optional"] for s in field_sets):
                continue
            doc = getattr(spytial, form).__doc__ or ""
            missing = [v for v in values if v not in doc]
            assert not missing, (
                f"@spytial.{form} accepts hold={missing} but its docstring does "
                f"not mention {missing}"
            )
        return

    doc = _prose_for(kind, target)
    missing = [v for v in values if v not in doc]
    assert not missing, (
        f"{target} accepts {missing} from {vocabulary}, but its docstring never "
        f"lists {missing} -- help() is the only reference users have here"
    )


@pytest.mark.parametrize("vocabulary", sorted(VOCABULARY_PROSE))
def test_vocabulary_values_are_spelled_out_in_the_docs_site(vocabulary):
    """docs/operations.md enumerates these too, and goes stale the same way."""
    prose = OPERATIONS_DOC.read_text(encoding="utf-8")
    missing = [v for v in getattr(tables, vocabulary) if v not in prose]
    assert not missing, (
        f"docs/operations.md does not mention {missing} from {vocabulary}"
    )


@pytest.mark.parametrize("form", ALL_FORMS)
def test_decorator_docstring_names_every_accepted_key(form):
    """The decorators take **kwargs, so the docstring is the only key reference.

    A field that reaches the tables but never the docstring is one nobody can
    find; ``help()`` shows ``(**kwargs)`` and nothing else.
    """
    spec = tables.CONSTRAINT_TYPES.get(form) or tables.DIRECTIVE_TYPES[form]
    field_sets = spec if isinstance(spec, list) else [spec]
    doc = getattr(spytial, form).__doc__ or ""
    for field_set in field_sets:
        for name in field_set["required"] + field_set["optional"]:
            assert name in doc, (
                f"@spytial.{form} accepts `{name}` but its docstring never "
                f"mentions it"
            )


# --------------------------------------------------------------------------- #
# Section placement, which decides what the emitted YAML looks like
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("form", ALL_FORMS)
def test_annotated_class_agrees_with_its_table_on_section(form):
    """`_is_constraint` and table membership must not disagree.

    They are consulted by different paths -- the classes by the ``Annotated``
    extractor, the tables by the decorators -- so a disagreement puts the same
    annotation in different YAML sections depending on how it was written.
    """
    in_constraints = form in tables.CONSTRAINT_TYPES
    assert ANNOTATION_CLASSES[form]._is_constraint is in_constraints, (
        f"{ANNOTATION_CLASSES[form].__name__}._is_constraint disagrees with the "
        f"tables, which put `{form}` under "
        f"{'constraints' if in_constraints else 'directives'}"
    )


# --------------------------------------------------------------------------- #
# The other direction: is what spytial emits well-formed?
# --------------------------------------------------------------------------- #
#
# The manifest governs what spytial accepts; the schema governs what it writes.
# The tables cannot catch an emission bug -- a correctly validated annotation
# serialized into the wrong section, or nested one level off -- because they
# describe the input side only. Core's parser will not catch it either: it
# ignores what it does not recognize. The schema is stricter than the parser
# precisely so that this check can exist.

SCHEMA_PATH = REPO_ROOT / "spytial" / "_vendor" / "spytial-spec.schema.json"


def _schema_validator():
    jsonschema = pytest.importorskip("jsonschema", reason="optional dev dependency")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    # The `$id` is a urn, which older RefResolver-based jsonschema tries to
    # fetch when resolving the local `#/$defs/...` refs. Dropping it leaves
    # every ref resolving against the document itself, which is what they mean.
    schema.pop("$id", None)
    return jsonschema.Draft202012Validator(schema)


@requires_repo
def test_emitted_spec_validates_against_the_core_schema():
    """A spec using every current form must satisfy core's own schema."""
    import spytial as sp

    @sp.size(selector="Node", height=50, width=50)
    @sp.hideAtom(selector="Internal")
    @sp.orientation(selector="children", directions=["below"])
    @sp.align(selector="row", direction="horizontal")
    @sp.cyclic(selector="next", direction="clockwise")
    @sp.group(selector="Team.members", name="Team", addEdge="togroup")
    @sp.atomStyle(
        selector="Dir",
        borderStyle=sp.BorderStyle(color="steelblue", width=2),
        fillStyle=sp.FillStyle(color="#eef6ff"),
        iconStyle=sp.IconStyle(path="bi:folder-fill", placement="badge", opacity=0.6),
        textStyle=sp.TextStyle(size="large", color="navy"),
        showLabel=True,
    )
    @sp.edgeStyle(
        field="next",
        lineStyle=sp.LineStyle(color="red", pattern="dashed", weight=2, highlight="pink"),
        textStyle=sp.TextStyle(size="small"),
        showLabel=True,
    )
    @sp.attribute(field="value", textStyle=sp.TextStyle(size="small"))
    @sp.hideField(field="_private")
    @sp.tag(toTag="Node", name="depth", value="d")
    @sp.inferredEdge(name="link", selector="^parent", draw="Team -> Team")
    @sp.flag(name="hideDisconnected")
    class Everything:
        pass

    errors = list(_schema_validator().iter_errors(Everything.__spytial_registry__))
    assert not errors, "\n".join(
        f"at {list(e.absolute_path)}: {e.message}" for e in errors[:5]
    )


@requires_repo
def test_the_schema_would_reject_the_deprecated_placement():
    """Guards the check above against being vacuous.

    `size` under `directives` is exactly the placement spytial emitted before
    spytial-core 4.3. The schema marks it deprecated but still valid, so what
    proves the schema has teeth here is a genuinely malformed spec.
    """
    validator = _schema_validator()
    assert list(validator.iter_errors({"constraints": [{"size": {"width": 0, "height": 5}}]}))
    assert list(validator.iter_errors({"constraints": [{"invented": {"selector": "x"}}]}))
    assert not list(validator.iter_errors({"constraints": [], "directives": []}))


# --------------------------------------------------------------------------- #
# hold, which not every constraint takes
# --------------------------------------------------------------------------- #


def test_hold_support_matches_the_tables():
    """HOLD_SUPPORTED_BY and the `hold` keyword in the tables come from the same
    manifest by two different routes; a disagreement would make the runtime
    check and the accepted-keys check contradict each other."""
    from_tables = set()
    for form, spec in tables.CONSTRAINT_TYPES.items():
        field_sets = spec if isinstance(spec, list) else [spec]
        if any("hold" in field_set["optional"] for field_set in field_sets):
            from_tables.add(form)
    assert from_tables == set(tables.HOLD_SUPPORTED_BY)


@pytest.mark.parametrize("form", sorted(tables.HOLD_SUPPORTED_BY))
def test_negatable_constraints_accept_hold(form):
    example = {
        "orientation": {"selector": "s", "directions": ["above"]},
        "cyclic": {"selector": "s", "direction": "clockwise"},
        "align": {"selector": "s", "direction": "horizontal"},
        "group": {"selector": "s", "name": "g"},
    }[form]
    decorated = getattr(spytial, form)(hold="never", **example)(type("C", (), {}))
    entry = decorated.__spytial_registry__["constraints"][0][form]
    assert entry["hold"] == "never"


@pytest.mark.parametrize(
    "form, example",
    [
        ("size", {"height": 10, "width": 10}),
        ("hideAtom", {"selector": "s"}),
    ],
)
def test_non_negatable_constraints_reject_hold(form, example):
    """Core takes the key and ignores it, so the spec would say one thing and
    render the other. Nothing downstream can catch that."""
    with pytest.raises(ValueError, match="does not support hold"):
        getattr(spytial, form)(hold="never", **example)(type("C", (), {}))


def test_size_and_hide_atom_are_constraints():
    """Both moved sections in spytial-core 4.3.

    Called out by name because the move is silent in both directions: the old
    placement still parses, so nothing complains, and these emit into whichever
    section the tables say.
    """
    assert "size" in tables.CONSTRAINT_TYPES
    assert "hideAtom" in tables.CONSTRAINT_TYPES
    assert "size" not in tables.DIRECTIVE_TYPES
    assert "hideAtom" not in tables.DIRECTIVE_TYPES


# --------------------------------------------------------------------------- #
# What spytial.suggest proposes, which has to be sayable in the language
# --------------------------------------------------------------------------- #
#
# suggest writes specs on the user's behalf and puts vocabularies into model
# prompts. Every one of those is a restatement of something the manifest already
# says, and a restatement that falls behind is the same silent failure the rest
# of this file exists to prevent -- with one extra turn of the screw: a prompt
# that names a stale vocabulary produces a model answer that is then correctly
# rejected, so it reads as the model being unhelpful rather than as drift.


def test_suggest_orders_every_form_it_could_emit():
    """`emit._PREFERRED` is a display order, so a gap in it is invisible.

    A form missing from the list still renders -- it just sorts to the end of
    its section, silently, and only in specs that happen to use it.
    """
    from spytial.suggest.emit import _PREFERRED

    assert set(_PREFERRED) == set(ALL_FORMS), (
        f"emit._PREFERRED and the tables disagree: "
        f"missing {sorted(set(ALL_FORMS) - set(_PREFERRED))}, "
        f"unknown {sorted(set(_PREFERRED) - set(ALL_FORMS))}"
    )


def test_suggest_emits_constraints_before_directives():
    """`to_source` and `to_registry` have to agree on the split.

    They are read together -- the source is what a user pastes, the registry is
    what gets applied -- so a rule that reads as geometry and lands under
    directives is a discrepancy the user has no way to see.
    """
    from spytial.suggest.emit import _rank

    ranks = {form: _rank(form) for form in ALL_FORMS}
    constraints = [f for f in ALL_FORMS if f in tables.CONSTRAINT_TYPES]
    directives = [f for f in ALL_FORMS if f not in tables.CONSTRAINT_TYPES]
    assert max(ranks[f] for f in constraints) < min(ranks[f] for f in directives)


def test_ask_kinds_are_forms_the_language_has():
    """`ask` admits candidates by kind before evaluating them.

    A kind that no longer exists upstream would be admitted here and then fail
    at render, which is exactly the point at which nothing reports why.
    """
    from spytial.suggest._ask import _ASK_KINDS, _KIND_ARITY

    assert set(_ASK_KINDS) <= set(ALL_FORMS), sorted(set(_ASK_KINDS) - set(ALL_FORMS))
    for kind in _ASK_KINDS:
        assert (kind, "selector") in tables.SELECTOR_ARITY, (
            f"ask authors `{kind}` with a selector, but the tables do not give "
            f"that slot an arity"
        )
        assert _KIND_ARITY[kind] == {"unary": 1, "binary": 2}[
            tables.SELECTOR_ARITY[(kind, "selector")]
        ]


def test_shape_tier_offers_the_whole_vocabulary_it_accepts():
    """The prompt and the response schema have to name the same directions.

    They are written metres apart and validated by different code, so a prompt
    listing fewer values than the schema allows costs suggestions with no
    symptom: the model simply never proposes what it was not offered.
    """
    from spytial.suggest import _enrich

    prompt = _enrich._SHAPE_PROMPT.format(
        cls="C",
        fields="- f",
        orient_dirs=", ".join(_enrich._ORIENT_DIRS),
        cyclic_dirs=" / ".join(_enrich._CYCLIC_DIRS),
    )
    for direction in tables.ORIENTATION_DIRECTIONS:
        assert direction in prompt, f"the shape prompt never offers {direction!r}"
    for direction in tables.ROTATION_DIRECTIONS:
        assert direction in prompt, f"the shape prompt never offers {direction!r}"

    schema = _enrich._SHAPE_SCHEMA["properties"]["shapes"]["items"]["properties"]
    assert schema["directions"]["items"]["enum"] == list(tables.ORIENTATION_DIRECTIONS)
    assert schema["direction"]["enum"] == list(tables.ROTATION_DIRECTIONS)


def test_shape_tier_constraints_are_forms_the_language_has():
    from spytial.suggest import _enrich

    schema = _enrich._SHAPE_SCHEMA["properties"]["shapes"]["items"]["properties"]
    kinds = set(schema["constraint"]["enum"]) - {"none"}  # 'none' is the abstain
    assert kinds <= set(tables.CONSTRAINT_TYPES), sorted(
        kinds - set(tables.CONSTRAINT_TYPES)
    )
