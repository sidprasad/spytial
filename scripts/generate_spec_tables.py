#!/usr/bin/env python3
"""Generate ``spytial/_spec_tables.py`` from spytial-core's language manifest.

    python3 scripts/generate_spec_tables.py

spytial-core publishes ``docs/spytial-language.json``, a machine-readable
description of every constraint and directive its layout-spec parser reads:
which section each belongs in, which fields it takes, which of those are
required, what each enum accepts, and how each deprecated spelling rewrites.
The manifest is vendored at ``spytial/_vendor/spytial-language.json``, pinned
to the spytial-core release named in ``spytial/core_assets.py``.

This script turns that manifest into the tables and value vocabularies
``spytial/annotations.py`` validates against. They used to be maintained by
hand, so a spytial-core release could add a field, move a form to the other
section, or retire a spelling, and the Python side would go on accepting
exactly what it accepted before, with nothing anywhere to say otherwise.

The generator refuses to emit output it cannot account for. Every item, field,
enum, and block in the manifest has to map onto something below; one that does
not is an error rather than a silent omission. That is the whole point of
generating rather than copying: when spytial-core grows a feature, the next
``./update-spytial-core.sh`` stops and names it.

Where the Python surface differs from the manifest on purpose, the difference
lives in an override table below with the reason it exists. Everything else is
mechanical.

``render()`` is kept separate from ``main()`` so ``test_spec_tables.py`` can
compare what the manifest *would* produce against what is checked in, without
writing anything -- the same drift check spytial-core runs over the manifest.
"""

from __future__ import annotations

import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "spytial" / "_vendor" / "spytial-language.json"
OUTPUT_PATH = REPO_ROOT / "spytial" / "_spec_tables.py"


class ManifestDrift(Exception):
    """The manifest contains something this generator was not written for.

    Raised instead of guessing. The message names the construct, so a
    spytial-core bump that adds one reports it by name rather than dropping it.
    """


# --------------------------------------------------------------------------- #
# Overrides: where Python deliberately differs from the manifest
# --------------------------------------------------------------------------- #

# Fields core treats as optional that the Python authoring surface requires.
# Each entry narrows what callers may write, never widens it, so a spec that
# passes here still parses in core.
REQUIRED_IN_PYTHON = {
    ("cyclic", "direction"): (
        "Core defaults a missing direction to 'clockwise' -- and reads an "
        "unrecognized one as 'clockwise' too. An omission and a typo are "
        "therefore indistinguishable in the diagram, so the ring's traversal "
        "order has to be stated at the authoring site to mean anything."
    ),
    ("icon", "showLabels"): (
        "Core reads a missing showLabels as False, which silently drops the "
        "atom's label. Requiring it keeps that from being a surprise."
    ),
}

# Manifest field name -> Python keyword, where the two differ.
FIELD_RENAMES = {
    # `flag` is a scalar item: the YAML is `- flag: hideDisconnected`, so the
    # manifest names the field after the item. As a Python keyword that would
    # read `flag(flag=...)`, so the decorator takes `name` and the scalar is
    # rebuilt at serialization time.
    ("flag", "flag"): "name",
}

# Forms Python still accepts that the manifest does not list, because core no
# longer reads them at all. Kept as tombstones: authoring one warns rather than
# raising an unknown-type error, which would be a worse message for anyone
# upgrading. Remove an entry once the deprecation has run its course.
PYTHON_ONLY_ITEMS = {
    "projection": {
        "section": "directives",
        "required": ["sig"],
        "optional": [],
        "reason": (
            "Never read by the layout-spec parser. Projection is a pre-layout "
            "transform over the data instance, driven by the viewer's "
            "projection controls, not something a spec declares. spytial warns "
            "at the authoring site; see _NOOP_ANNOTATIONS in annotations.py."
        ),
    },
}

# Enum vocabularies get a module-level constant so annotations.py, the suggest
# prompts, and tests can all name the same tuple. Keyed by where the enum
# lives: ("item"|"block", owner, field).
#
# An enum in the manifest with no entry here is a hard error -- that is how a
# newly added vocabulary announces itself instead of going unvalidated.
ENUM_CONSTANTS = {
    ("item", "orientation", "directions"): "ORIENTATION_DIRECTIONS",
    ("item", "cyclic", "direction"): "ROTATION_DIRECTIONS",
    ("item", "align", "direction"): "ALIGN_DIRECTIONS",
    ("item", "flag", "flag"): "FLAG_NAMES",
    ("item", "group", "addEdge"): "GROUP_EDGE_DIRECTIONS",
    # `addEdge`'s block form carries the same direction under `points`.
    ("item", "group", "points"): "GROUP_EDGE_DIRECTIONS",
    ("item", "inferredEdge", "style"): "LINE_PATTERNS",
    ("item", "edgeColor", "style"): "LINE_PATTERNS",
    ("block", "textStyle", "size"): "TEXT_SIZES",
    ("block", "lineStyle", "pattern"): "LINE_PATTERNS",
    ("block", "iconStyle", "placement"): "ICON_PLACEMENTS",
}

# Field types the generator knows how to place in a table. Types carry no
# Python-side behaviour beyond enum membership, so this list exists only to
# make an unfamiliar one fail loudly.
KNOWN_FIELD_TYPES = frozenset(
    {
        "selector",
        "relation",
        "string",
        "color",
        "icon-path",
        "enum",
        "enum-list",
        "integer",
        "number",
        "boolean",
        "block",
    }
)

# Top-level manifest keys this generator knows how to read. Everything else it
# checks -- fields, enums, sections, arities -- it checks *inside* `items` and
# `blocks`, so a release that introduces a construct one level above those was
# free to land with nothing on this side noticing. That is exactly how `source`
# arrived in 5.4.3: a new top-level key describing a block every item accepts,
# generating cleanly and silently, because nothing here was looking at the
# manifest's own shape. A new key now stops the update and names itself.
KNOWN_MANIFEST_KEYS = frozenset(
    {
        "language",
        "languageVersion",
        "spytialCoreVersion",
        "versioning",
        "document",
        "documentation",
        "hold",
        "source",
        "blocks",
        "items",
        "deprecations",
    }
)

KNOWN_SECTIONS = frozenset({"constraints", "directives"})
KNOWN_VALUE_SHAPES = frozenset({"mapping", "scalar"})

# Arities a selector slot can declare. `n-ary` means the slot puts no arity
# requirement on the expression (`filter`, `tag.value`), which is a different
# statement from "any arity is fine to *suggest*" -- so it is carried through
# rather than dropped, and consumers decide what to do with it.
KNOWN_ARITIES = frozenset({"unary", "binary", "n-ary"})


# --------------------------------------------------------------------------- #
# Reading the manifest
# --------------------------------------------------------------------------- #


def load_manifest(path=MANIFEST_PATH):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def check_manifest_shape(manifest):
    """Fail on a top-level construct this generator was never written for.

    The rest of the drift checking assumes the manifest is a bag of `items` and
    `blocks`; this is the one that notices when it stops being only that.
    """
    unknown = sorted(set(manifest) - KNOWN_MANIFEST_KEYS)
    if unknown:
        raise ManifestDrift(
            f"the manifest has top-level key(s) {unknown} this generator was not "
            f"written for. Each describes part of the spec language with nothing "
            f"on the Python side reading it, so specs would keep generating while "
            f"silently not using it. Add it to KNOWN_MANIFEST_KEYS, with a build_* "
            f"for whatever it describes if it needs one, before regenerating."
        )


def build_source_support(manifest):
    """Which items carry a ``source`` block, and which display it, as yaml keys.

    `source` is the language's channel for the rule as its author wrote it, so
    a generator that does not stamp one is leaving conflict reports to describe
    rules in the engine's words instead of the author's. Which items accept one
    is the manifest's call: an item outside `supportedBy` has the block parsed
    and thrown away, and a scalar item has no block to put it in at all.
    """
    source = manifest["source"]
    if source.get("field") != "source":
        raise ManifestDrift(
            f"the source block is written under {source.get('field')!r}, not "
            f"'source'; annotations.py stamps the key by name."
        )

    fields = {field["name"]: field for field in source.get("fields", [])}
    if set(fields) != {"text", "location"}:
        raise ManifestDrift(
            f"the source block's fields are {sorted(fields)}, not ['location', "
            f"'text']; spytial/_source.py emits exactly those two."
        )
    if not fields["text"].get("required"):
        raise ManifestDrift("source.text is no longer required; revisit _source.py.")
    if fields["location"].get("required"):
        raise ManifestDrift(
            "source.location is now required, but spytial omits it when the "
            "authoring site is a REPL or has no readable file; revisit _source.py."
        )

    ids_to_keys = {item["id"]: item["yamlKey"] for item in manifest["items"]}
    lists = {}
    for name in ("supportedBy", "displayedBy"):
        keys = []
        for item_id in source[name]:
            if item_id not in ids_to_keys:
                raise ManifestDrift(
                    f"source.{name} names unknown item {item_id!r}."
                )
            keys.append(ids_to_keys[item_id])
        lists[name] = keys

    scalar = {
        item["yamlKey"]
        for item in manifest["items"]
        if item.get("valueShape") == "scalar"
    }
    carried_by_scalars = scalar & set(lists["supportedBy"])
    if carried_by_scalars:
        raise ManifestDrift(
            f"source.supportedBy lists scalar item(s) {sorted(carried_by_scalars)}, "
            f"which serialize as a bare value and have no block to carry a source."
        )
    undeclared = set(lists["displayedBy"]) - set(lists["supportedBy"])
    if undeclared:
        raise ManifestDrift(
            f"source.displayedBy names {sorted(undeclared)}, which "
            f"source.supportedBy does not accept a source on."
        )

    return sorted(lists["supportedBy"]), sorted(lists["displayedBy"])


def _python_name(item_id, field):
    """The Python keyword for a manifest field."""
    return FIELD_RENAMES.get((item_id, field["name"]), field["name"])


def _check_field(item_id, field):
    field_type = field.get("type")
    if field_type not in KNOWN_FIELD_TYPES:
        raise ManifestDrift(
            f"{item_id}.{field.get('name')} has unfamiliar type {field_type!r}. "
            f"Teach the generator about it (KNOWN_FIELD_TYPES) before regenerating."
        )
    if field_type in ("enum", "enum-list") and not field.get("values"):
        raise ManifestDrift(f"{item_id}.{field['name']} is an enum with no values.")


def _collect_enums(manifest):
    """Enum vocabularies from the manifest, keyed by constant name.

    Two fields may legitimately share a vocabulary (a legacy inline `style` and
    the `lineStyle.pattern` that replaced it); if they ever disagree, that is a
    manifest change worth stopping on rather than picking a winner.
    """
    constants = {}
    seen_owners = {}

    def record(kind, owner, field):
        if field.get("type") not in ("enum", "enum-list"):
            return
        key = (kind, owner, field["name"])
        constant = ENUM_CONSTANTS.get(key)
        if constant is None:
            raise ManifestDrift(
                f"{kind} {owner}.{field['name']} is an enum with no constant name. "
                f"Add it to ENUM_CONSTANTS (it would otherwise go unvalidated)."
            )
        values = tuple(field["values"])
        if constant in constants and constants[constant] != values:
            raise ManifestDrift(
                f"{constant} is claimed by {seen_owners[constant]} with "
                f"{constants[constant]} and by {owner}.{field['name']} with "
                f"{values}; they must agree or use separate constants."
            )
        constants[constant] = values
        seen_owners.setdefault(constant, f"{owner}.{field['name']}")

    for item in manifest["items"]:
        for field in item.get("fields", []):
            _check_field(item["id"], field)
            record("item", item["id"], field)
            # A field may also accept a block form (`group.addEdge`), whose own
            # leaves need the same treatment -- including its enums, which is
            # how `points` gets checked against the same vocabulary `addEdge`
            # uses rather than going unvalidated.
            for sub in (field.get("alternativeForm") or {}).get("fields", []):
                _check_field(item["id"], sub)
                record("item", item["id"], sub)

    for block in manifest["blocks"]:
        for field in block["fields"]:
            _check_field(block["name"], field)
            record("block", block["name"], field)

    hold = manifest["hold"]
    constants["CONSTRAINT_HOLDS"] = tuple(hold["values"])
    return constants


def build_hold_support(manifest):
    """The forms `hold` actually negates, as yaml keys.

    Not every constraint takes it. `size` and `hideAtom` accept the key
    syntactically and ignore it, which is the worst combination -- a spec
    reading `hold: never` that quietly means the opposite of what it says.

    The manifest states this twice, as a per-item ``supportsHold`` flag and as
    the ``hold.supportedBy`` list. Cross-check them: if they ever disagree,
    picking either one silently would be guessing.
    """
    by_flag = {
        item["yamlKey"] for item in manifest["items"] if item.get("supportsHold")
    }
    ids_to_keys = {item["id"]: item["yamlKey"] for item in manifest["items"]}
    by_list = {ids_to_keys[i] for i in manifest["hold"]["supportedBy"] if i in ids_to_keys}
    if by_flag != by_list:
        raise ManifestDrift(
            f"the manifest disagrees with itself about `hold`: supportsHold flags "
            f"give {sorted(by_flag)}, hold.supportedBy gives {sorted(by_list)}."
        )
    return sorted(by_flag)


def _field_sets(item):
    """(required, optional) Python keywords for one manifest item."""
    required, optional = [], []
    for field in item.get("fields", []):
        name = _python_name(item["id"], field)
        is_required = bool(field.get("required")) or (
            (item["id"], field["name"]) in REQUIRED_IN_PYTHON
        )
        (required if is_required else optional).append(name)
    if item.get("supportsHold"):
        optional.append("hold")
    return required, optional


def build_tables(manifest):
    """Split the manifest's items into the constraint and directive tables.

    Items sharing a ``yamlKey`` become a list of alternative field sets, which
    is what ``validate_fields`` already understands: it accepts the first set
    whose required fields are all present. Alternatives are disjoint on their
    required fields, so the order only affects the wording of the error when
    none matches. ``group`` and ``group.byField`` were the only such pair until
    spytial-core 5.0 retired the latter; nothing shares a key today.
    """
    tables = {"constraints": {}, "directives": {}}

    for item in manifest["items"]:
        shape = item.get("valueShape")
        if shape not in KNOWN_VALUE_SHAPES:
            raise ManifestDrift(f"{item['id']} has unfamiliar valueShape {shape!r}.")
        sections = item.get("sections") or []
        unknown = set(sections) - KNOWN_SECTIONS
        if unknown:
            raise ManifestDrift(f"{item['id']} names unknown section(s) {sorted(unknown)}.")
        if len(sections) != 1:
            raise ManifestDrift(
                f"{item['id']} lists {sections} as its home section; the Python "
                f"tables assume exactly one (deprecated placements live in "
                f"deprecatedSections and are not authorable here)."
            )

        required, optional = _field_sets(item)
        entry = {"required": required, "optional": optional}
        table = tables[sections[0]]
        key = item["yamlKey"]
        if key in table:
            existing = table[key]
            table[key] = (existing if isinstance(existing, list) else [existing]) + [entry]
        else:
            table[key] = entry

    for name, spec in PYTHON_ONLY_ITEMS.items():
        table = tables[spec["section"]]
        if name in table:
            raise ManifestDrift(
                f"{name} is listed in PYTHON_ONLY_ITEMS but the manifest now "
                f"defines it; drop the override and let it generate."
            )
        table[name] = {"required": list(spec["required"]), "optional": list(spec["optional"])}

    return tables["constraints"], tables["directives"]


def build_enum_values(manifest):
    """(item, keyword) -> enum constant, for author-time value checking.

    Skips anything validation cannot reach, because ``_prepare_kwargs`` checks
    values only *after* rewriting the kwargs:

    * fields of a deprecated item, and deprecated fields of a current one --
      ``_desugar_legacy_style`` has folded both into their replacement by then,
      and it deliberately drops a bad legacy value with a warning rather than
      raising, matching core's own lenience about them;
    * fields with an ``alternativeForm``, whose value may legitimately be a
      block dict rather than one of the enum's strings (``group.addEdge``).

    An entry for any of those would read as live validation while being
    unreachable by construction.
    """
    pairs = {}
    for item in manifest["items"]:
        if item.get("deprecated"):
            continue
        for field in item.get("fields", []):
            if field.get("type") not in ("enum", "enum-list"):
                continue
            if field.get("deprecated") or field.get("alternativeForm"):
                continue
            constant = ENUM_CONSTANTS[("item", item["id"], field["name"])]
            pairs[(item["yamlKey"], _python_name(item["id"], field))] = constant
    return pairs


def build_selector_arity(manifest):
    """(item, keyword) -> the arity a selector in that slot has to evaluate to.

    Nothing in Python can check this: an arity mismatch is only discoverable by
    evaluating the expression against a datum, which is what
    ``spytial.suggest`` does before it proposes a rule. Core itself does not
    check it either -- a unary expression in a slot wanting pairs matches no
    tuples, and the constraint disappears from the diagram. Carrying the
    declared arity here is what lets the suggest tiers reject a candidate at
    the point where they can still say why.

    Deprecated items are skipped, which is also what keeps the two ``group``
    forms from colliding: they share a ``yamlKey`` and disagree about arity
    (the current form's selector is binary, the by-field form's is unary).
    """
    arities = {}
    for item in manifest["items"]:
        if item.get("deprecated"):
            continue
        for field in item.get("fields", []):
            if field.get("type") != "selector":
                continue
            arity = field.get("arity")
            if arity not in KNOWN_ARITIES:
                raise ManifestDrift(
                    f"{item['id']}.{field['name']} is a selector with arity "
                    f"{arity!r}; teach the generator about it (KNOWN_ARITIES) "
                    f"before regenerating."
                )
            key = (item["yamlKey"], _python_name(item["id"], field))
            if key in arities and arities[key] != arity:
                raise ManifestDrift(
                    f"{key[0]}.{key[1]} is declared {arities[key]!r} by one form "
                    f"and {arity!r} by another; they must agree."
                )
            arities[key] = arity
    return {key: arities[key] for key in sorted(arities)}


def build_blocks(manifest):
    """Shared style blocks, as field name -> validation facts.

    Consumed by the block dataclasses' drift test rather than at runtime: the
    dataclasses stay hand-written so ``help()`` and IDE hovers keep real
    signatures and docstrings, and the test holds them to this shape.
    """
    blocks = {}
    for block in manifest["blocks"]:
        fields = {}
        for field in block["fields"]:
            facts = {"type": field["type"]}
            if field.get("type") == "enum":
                facts["enum"] = ENUM_CONSTANTS[("block", block["name"], field["name"])]
            for bound in ("exclusiveMinimum", "minimum", "maximum"):
                if field.get(bound) is not None:
                    facts[bound] = field[bound]
            fields[field["name"]] = facts
        blocks[block["name"]] = fields
    return blocks


def build_deprecations(manifest):
    """Deprecated items and fields, with the rewrite each one maps onto."""
    items, fields = {}, {}
    for entry in manifest.get("deprecations", []):
        kind = entry.get("kind")
        if kind not in ("item", "field", "placement"):
            raise ManifestDrift(f"deprecation {entry.get('id')} has unfamiliar kind {kind!r}.")
        if kind == "placement":
            # `size`/`hideAtom` under `directives`: a tolerated *location* for a
            # form that is not itself deprecated. The tables put each in its home
            # section, so spytial never emits the deprecated placement and has
            # nothing to record here.
            continue
        target = items if kind == "item" else fields
        target[entry["id"]] = {
            "path": entry.get("path"),
            "replacedBy": entry.get("replacedBy"),
            "mapping": entry.get("mapping") or {},
        }
    return items, fields


# --------------------------------------------------------------------------- #
# Emitting
# --------------------------------------------------------------------------- #


def _lit(value, indent=0):
    """Deterministic Python literal, so the drift test can compare bytes."""
    pad = " " * indent
    inner = " " * (indent + 4)
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = [f"{inner}{key!r}: {_lit(val, indent + 4)}," for key, val in value.items()]
        return "{\n" + "\n".join(lines) + f"\n{pad}}}"
    if isinstance(value, list):
        if not value:
            return "[]"
        lines = [f"{inner}{_lit(item, indent + 4)}," for item in value]
        return "[\n" + "\n".join(lines) + f"\n{pad}]"
    return repr(value)


def _tuple_lit(values):
    lines = [f"    {value!r}," for value in values]
    return "(\n" + "\n".join(lines) + "\n)"


def render(manifest=None):
    """The exact bytes ``spytial/_spec_tables.py`` should contain."""
    manifest = manifest or load_manifest()
    check_manifest_shape(manifest)

    enums = _collect_enums(manifest)
    constraints, directives = build_tables(manifest)
    hold_supported_by = build_hold_support(manifest)
    source_supported_by, source_displayed_by = build_source_support(manifest)
    enum_values = build_enum_values(manifest)
    selector_arity = build_selector_arity(manifest)
    blocks = build_blocks(manifest)
    deprecated_items, deprecated_fields = build_deprecations(manifest)
    # A scalar item serializes as a bare value rather than a mapping, so it
    # needs to know which keyword carries that value.
    scalar_items = {}
    for item in manifest["items"]:
        if item.get("valueShape") != "scalar":
            continue
        fields = item.get("fields", [])
        if len(fields) != 1:
            raise ManifestDrift(
                f"{item['id']} is a scalar item with {len(fields)} fields; a bare "
                f"value can only carry one."
            )
        scalar_items[item["yamlKey"]] = _python_name(item["id"], fields[0])

    out = [
        '"""Field tables and value vocabularies for the spytial layout-spec language.',
        "",
        "GENERATED FILE -- DO NOT EDIT BY HAND.",
        "",
        "    Source:   spytial/_vendor/spytial-language.json",
        f"    Language: {manifest['languageVersion']} (spytial-core {manifest['spytialCoreVersion']})",
        "    Regenerate with: python3 scripts/generate_spec_tables.py",
        "",
        "Everything here is derived from the manifest spytial-core publishes, so a",
        "field, section, or vocabulary that changes upstream changes here as a diff",
        "in review rather than as a spec that quietly stops matching. Deliberate",
        "differences from the manifest are declared in the generator's override",
        "tables, each with its reason.",
        '"""',
        "",
        "# The manifest this was generated from. `LANGUAGE_VERSION` only moves when",
        "# the spec language itself changes, so an unchanged value across a",
        "# spytial-core bump means nothing here needed revisiting.",
        f"LANGUAGE_VERSION = {manifest['languageVersion']!r}",
        f"CORE_VERSION = {manifest['spytialCoreVersion']!r}",
        "",
        "",
        "# --------------------------------------------------------------------------- #",
        "# Value vocabularies",
        "# --------------------------------------------------------------------------- #",
        "#",
        "# These are TypeScript union types in core, so they are erased at runtime and",
        "# nothing downstream re-checks them. An unrecognized value is kept by the",
        "# parser and then quietly does the wrong thing -- an out-of-vocab orientation",
        "# direction matches no case and the constraint evaporates; a misspelled cyclic",
        "# direction reads as 'clockwise'; an unknown flag name does nothing. Authoring",
        "# time is the only place they can surface.",
        "",
    ]

    for constant in sorted(enums):
        out.append(f"{constant} = {_tuple_lit(enums[constant])}")
        out.append("")

    out += [
        "",
        "# --------------------------------------------------------------------------- #",
        "# Field tables",
        "# --------------------------------------------------------------------------- #",
        "#",
        "# `hold` is optional on every constraint that supports negation: core reads",
        "# `hold: never` off the inner block and flips the constraint to its negation.",
        "# A key with a list of field sets accepts any one of them (`group`, whose",
        "# deprecated by-field form takes different keys than the selector form).",
        "",
        f"CONSTRAINT_TYPES = {_lit(constraints)}",
        "",
        f"DIRECTIVE_TYPES = {_lit(directives)}",
        "",
        "# Items written as a bare scalar rather than a mapping",
        "# (`- flag: hideDisconnected`), mapped to the keyword carrying the value.",
        f"SCALAR_ITEMS = {_lit(scalar_items)}",
        "",
        "# The forms `hold: never` actually negates. `size` and `hideAtom` are",
        "# constraints that do NOT take it -- core accepts the key and ignores it,",
        "# so a spec reading `hold: never` there quietly means the opposite of what",
        "# it says. annotations.py rejects it rather than emitting a no-op.",
        f"HOLD_SUPPORTED_BY = frozenset({_lit(hold_supported_by)})",
        "",
        "# The forms that accept a `source` block -- the rule as its author wrote",
        "# it, which conflict reports cite in place of the engine's own rendering.",
        "# Every block-bodied item accepts one; a scalar item (`- flag: ...`) has",
        "# no block to carry it. spytial/_source.py builds the block, annotations.py",
        "# stamps it on the entries named here.",
        f"SOURCE_SUPPORTED_BY = frozenset({_lit(source_supported_by)})",
        "",
        "# The subset core actually shows a source for today: the layout constraints",
        "# and hideAtom, the forms that turn up in conflict reports. On the rest the",
        "# block parses and is ignored, so this is advisory -- spytial stamps every",
        "# form in SOURCE_SUPPORTED_BY, uniformly, and lets core decide what to show.",
        f"SOURCE_DISPLAYED_BY = frozenset({_lit(source_displayed_by)})",
        "",
        "",
        "# --------------------------------------------------------------------------- #",
        "# Author-time value checking",
        "# --------------------------------------------------------------------------- #",
        "",
        "# (annotation type, keyword) -> the values core accepts. List-valued keywords",
        "# are checked element-wise.",
        "ENUM_VALUES = {",
    ]
    for (item, keyword), constant in sorted(enum_values.items()):
        out.append(f"    ({item!r}, {keyword!r}): {constant},")
    out += [
        "}",
        "",
        "# (annotation type, keyword) -> the arity a selector written there has to",
        "# evaluate to. Not checkable without a datum, so nothing enforces it at",
        "# authoring time; spytial.suggest evaluates candidates against example",
        "# instances and uses this to reject the ones that would match no tuples.",
        f"SELECTOR_ARITY = {_lit(selector_arity)}",
        "",
        "",
        "# --------------------------------------------------------------------------- #",
        "# Shared style blocks",
        "# --------------------------------------------------------------------------- #",
        "#",
        "# The dataclasses in annotations.py are hand-written -- they carry the",
        "# docstrings and real signatures that `help()` shows -- and test_spec_tables.py",
        "# holds them to the shape below.",
        "",
        f"BLOCKS = {_lit(blocks)}",
        "",
        "",
        "# --------------------------------------------------------------------------- #",
        "# Deprecations",
        "# --------------------------------------------------------------------------- #",
        "#",
        "# A deprecated form keeps parsing and keeps its meaning until a spytial-core",
        "# major. `mapping` is the rewrite core documents; annotations.py implements it",
        "# in _desugar_legacy_style so the emitted spec uses the current spelling.",
        "",
        f"DEPRECATED_ITEMS = {_lit(deprecated_items)}",
        "",
        f"DEPRECATED_FIELDS = {_lit(deprecated_fields)}",
        "",
    ]

    return "\n".join(out)


def main():
    manifest = load_manifest()
    rendered = render(manifest)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} "
        f"(spec language {manifest['languageVersion']}, "
        f"spytial-core {manifest['spytialCoreVersion']}, "
        f"{len(manifest['items'])} items)."
    )


if __name__ == "__main__":
    main()
