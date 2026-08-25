"""Release check: has spytial's public authoring surface changed, and how?

Most of what a user writes -- which decorators exist, which keyword each takes,
which values each keyword accepts -- is generated from spytial-core's language
manifest. That is what keeps it accurate, and it is also why this test exists:
the API can now change without anyone editing a line of Python. Vendor a new
core release, run the generator, and the surface users program against is
different, with the whole change sitting inside a generated file.

``test/api_baseline.json`` is the acknowledged surface. This test rebuilds the
live one and fails on any difference, sorting each into:

* **additive** -- new form, new optional keyword, new accepted value, a keyword
  that stopped being required. Existing user code keeps working.
* **breaking** -- form or keyword removed, keyword became required, accepted
  value removed, or a form moved between the constraints and directives
  sections. Existing user code stops working, or quietly draws something else.

Regenerating the baseline is the acknowledgement:

    python3 scripts/generate_api_baseline.py

The regenerated file records the spytial version that made the change, so the
history of this one file is the history of the public API.
"""

import importlib
import json
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
BASELINE_PATH = REPO_ROOT / "test" / "api_baseline.json"

requires_repo = pytest.mark.skipif(
    not SCRIPTS_DIR.exists() or not BASELINE_PATH.exists(),
    reason="baseline and generator live in the repo, not the wheel",
)


def _capture():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    return importlib.import_module("generate_api_baseline").capture()


def _baseline():
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Classifying a surface diff
# --------------------------------------------------------------------------- #


def _accepted(field_set):
    return set(field_set["required"]) | set(field_set["optional"])


def _match_variants(old_sets, new_sets):
    """Pair up a form's alternative field sets, by keyword overlap.

    A form with alternatives has variants whose required keys are disjoint --
    ``group`` had two until spytial-core 5.0, one needing field/groupOn/
    addToGroup and one needing selector/name -- so they cannot be matched
    positionally: a reorder upstream would read as both removed and both added.

    They also must not be collapsed into one union. Disjoint required keys are
    what an intersection across variants reduces to nothing, and an empty
    intersection stays empty however the variants change, so every requiredness
    change on such a form would become invisible.

    Returns (pairs, dropped, added).
    """
    unmatched = list(range(len(new_sets)))
    pairs, dropped = [], []
    for old in old_sets:
        best, best_score = None, 0
        for index in unmatched:
            score = len(_accepted(old) & _accepted(new_sets[index]))
            if score > best_score:
                best, best_score = index, score
        if best is None:
            dropped.append(old)
        else:
            unmatched.remove(best)
            pairs.append((old, new_sets[best]))
    return pairs, dropped, [new_sets[i] for i in unmatched]


def _describe(field_set):
    return ", ".join(sorted(field_set["required"])) or "no required keys"


def _qualifier(field_set, multiple):
    """Which alternative a change lands on, when a form has more than one.

    A suffix rather than a prefix, so the common single-variant message stays
    the compact `form.keyword` it has always been.
    """
    return f" (in the {_describe(field_set)} form)" if multiple else ""


def classify(old, new):
    """Return (breaking, additive) lists of human-readable change descriptions."""
    breaking, additive = [], []

    def compare_sets(old_items, new_items, removed_msg, added_msg, *, removal_breaks=True):
        for item in sorted(set(old_items) - set(new_items)):
            (breaking if removal_breaks else additive).append(removed_msg.format(item))
        for item in sorted(set(new_items) - set(old_items)):
            additive.append(added_msg.format(item))

    # Forms
    compare_sets(
        old["forms"], new["forms"],
        "form `{}` was removed", "form `{}` was added",
    )
    for name in sorted(set(old["forms"]) & set(new["forms"])):
        before, after = old["forms"][name], new["forms"][name]
        if before["section"] != after["section"]:
            breaking.append(
                f"form `{name}` moved from {before['section']} to {after['section']} "
                f"(same Python call, different emitted section)"
            )
        pairs, dropped, added = _match_variants(before["fieldSets"], after["fieldSets"])
        multiple = len(before["fieldSets"]) > 1 or len(after["fieldSets"]) > 1
        for field_set in dropped:
            breaking.append(
                f"`{name}` no longer accepts the {_describe(field_set)} form"
            )
        for field_set in added:
            additive.append(f"`{name}` accepts a new form: {_describe(field_set)}")
        for old_set, new_set in pairs:
            where = _qualifier(old_set, multiple)
            for key in sorted(_accepted(old_set) - _accepted(new_set)):
                breaking.append(f"`{name}` no longer accepts `{key}`{where}")
            for key in sorted(_accepted(new_set) - _accepted(old_set)):
                additive.append(f"`{name}` accepts new keyword `{key}`{where}")
            became_required = set(new_set["required"]) - set(old_set["required"])
            for key in sorted(became_required & _accepted(old_set)):
                breaking.append(f"`{name}.{key}` became required{where}")
            for key in sorted(set(old_set["required"]) - set(new_set["required"])):
                if key in _accepted(new_set):
                    additive.append(f"`{name}.{key}` is no longer required{where}")

    # Value vocabularies
    compare_sets(
        old["vocabularies"], new["vocabularies"],
        "vocabulary `{}` was removed", "vocabulary `{}` was added",
    )
    for name in sorted(set(old["vocabularies"]) & set(new["vocabularies"])):
        compare_sets(
            old["vocabularies"][name], new["vocabularies"][name],
            f"`{name}` no longer accepts '{{}}'", f"`{name}` accepts new value '{{}}'",
        )

    # Style blocks
    compare_sets(
        old["blocks"], new["blocks"],
        "style block `{}` was removed", "style block `{}` was added",
    )
    for name in sorted(set(old["blocks"]) & set(new["blocks"])):
        compare_sets(
            old["blocks"][name], new["blocks"][name],
            f"`{name}` no longer has field `{{}}`", f"`{name}` gained field `{{}}`",
        )

    # Annotated[...] classes
    compare_sets(
        old["classes"], new["classes"],
        "class `{}` was removed", "class `{}` was added",
    )
    for name in sorted(set(old["classes"]) & set(new["classes"])):
        before, after = old["classes"][name], new["classes"][name]
        if before == after:
            continue
        if before == "**kwargs" or after == "**kwargs":
            breaking.append(f"class `{name}` changed how it takes parameters")
            continue
        compare_sets(
            before, after,
            f"`{name}` no longer takes `{{}}`", f"`{name}` takes new parameter `{{}}`",
        )
        for key in sorted(set(before) & set(after)):
            if before[key] == "optional" and after[key] == "required":
                breaking.append(f"`{name}.{key}` became required")
            elif before[key] == "required" and after[key] == "optional":
                additive.append(f"`{name}.{key}` is no longer required")

    # Exports
    compare_sets(
        old["exports"], new["exports"],
        "`spytial.{}` was removed from the public API",
        "`spytial.{}` was added to the public API",
    )
    return breaking, additive


# --------------------------------------------------------------------------- #
# The check
# --------------------------------------------------------------------------- #


@requires_repo
def test_public_surface_matches_the_baseline():
    breaking, additive = classify(_baseline(), _capture())
    if not breaking and not additive:
        return

    report = ["spytial's public authoring surface has changed.", ""]
    if breaking:
        report.append("BREAKING -- existing user code stops working or draws differently:")
        report += [f"  - {line}" for line in breaking]
        report.append("")
    if additive:
        report.append("Additive -- existing user code keeps working:")
        report += [f"  - {line}" for line in additive]
        report.append("")
    report += [
        "If this is intended, acknowledge it by regenerating the baseline:",
        "    python3 scripts/generate_api_baseline.py",
        "",
        (
            "A breaking change warrants more than the usual patch bump in "
            "spytial/_version.py; the regenerated baseline records which version "
            "made the change."
            if breaking
            else "A patch bump is enough for an additive change."
        ),
    ]
    pytest.fail("\n".join(report), pytrace=False)


@requires_repo
def test_baseline_records_the_version_that_produced_it():
    """A baseline whose version is stale makes its own history unreadable."""
    import spytial
    from spytial import _spec_tables as tables

    baseline = _baseline()
    assert baseline["spytialCoreVersion"] == tables.CORE_VERSION, (
        "the baseline was captured against a different spytial-core; regenerate it"
    )
    assert baseline["spytialVersion"] == spytial.__version__, (
        f"baseline records spytial {baseline['spytialVersion']} but the package is "
        f"{spytial.__version__}; regenerate it so the surface and the version that "
        f"shipped it stay together"
    )


# --------------------------------------------------------------------------- #
# The classifier itself, which the check above is only as good as
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "mutate, expected_breaking",
    [
        (lambda s: s["forms"].pop("cyclic"), "form `cyclic` was removed"),
        (
            lambda s: s["forms"]["size"].update(section="directives"),
            "form `size` moved from constraints to directives",
        ),
        (
            lambda s: s["forms"]["edgeStyle"]["fieldSets"][0]["optional"].remove("hidden"),
            "`edgeStyle` no longer accepts `hidden`",
        ),
        (
            lambda s: (
                s["forms"]["atomStyle"]["fieldSets"][0]["optional"].remove("selector"),
                s["forms"]["atomStyle"]["fieldSets"][0]["required"].append("selector"),
            ),
            "`atomStyle.selector` became required",
        ),
        (
            lambda s: s["vocabularies"]["LINE_PATTERNS"].remove("dotted"),
            "`LINE_PATTERNS` no longer accepts 'dotted'",
        ),
        (
            lambda s: s["blocks"]["lineStyle"].remove("highlight"),
            "`lineStyle` no longer has field `highlight`",
        ),
        (
            lambda s: s["exports"].remove("orientation"),
            "`spytial.orientation` was removed from the public API",
        ),
    ],
)
def test_classifier_calls_a_removal_breaking(mutate, expected_breaking):
    """Each mutation is a real way core could narrow the language."""
    before = _baseline()
    after = _baseline()
    mutate(after)
    breaking, _ = classify(before, after)
    assert any(expected_breaking in line for line in breaking), (
        f"expected a breaking change matching {expected_breaking!r}, got {breaking}"
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s["forms"]["align"]["fieldSets"][0]["optional"].append("newKey"),
        lambda s: s["vocabularies"]["TEXT_SIZES"].append("enormous"),
        lambda s: s["blocks"]["fillStyle"].append("opacity"),
        lambda s: s["exports"].append("newThing"),
        lambda s: (
            s["forms"]["tag"]["fieldSets"][0]["required"].remove("name"),
            s["forms"]["tag"]["fieldSets"][0]["optional"].append("name"),
        ),
    ],
)
def test_classifier_calls_an_addition_or_relaxation_additive(mutate):
    before = _baseline()
    after = _baseline()
    mutate(after)
    breaking, additive = classify(before, after)
    assert not breaking, f"expected no breaking changes, got {breaking}"
    assert additive


def test_classifier_reports_nothing_when_nothing_changed():
    assert classify(_baseline(), _baseline()) == ([], [])


# --------------------------------------------------------------------------- #
# Forms with alternative field sets
# --------------------------------------------------------------------------- #
#
# `group` is the only one, and it is the case a union-based comparison gets
# wrong: its two variants have disjoint required keys, so intersecting them
# gives the empty set, which stays empty however either variant changes. Every
# requiredness change on `group` was invisible until these landed.


def _mutate_group_variant(surface, find, move_from, move_to):
    for field_set in surface["forms"]["group"]["fieldSets"]:
        if find in field_set[move_from]:
            field_set[move_from].remove(find)
            field_set[move_to].append(find)
            return surface
    raise AssertionError(f"no group variant has {find!r} in {move_from}")


def test_relaxing_a_key_in_one_group_variant_is_seen_and_additive():
    before = _baseline()
    after = _mutate_group_variant(_baseline(), "name", "required", "optional")
    breaking, additive = classify(before, after)
    assert not breaking, breaking
    assert any("`group.name` is no longer required" in line for line in additive), additive


def test_requiring_a_key_in_one_group_variant_is_seen_and_breaking():
    before = _baseline()
    after = _mutate_group_variant(_baseline(), "addEdge", "optional", "required")
    breaking, _ = classify(before, after)
    assert any("`group.addEdge` became required" in line for line in breaking), breaking


def test_removing_a_key_from_one_group_variant_is_breaking():
    before = _baseline()
    after = _baseline()
    for field_set in after["forms"]["group"]["fieldSets"]:
        if "textStyle" in field_set["optional"]:
            field_set["optional"].remove("textStyle")
    breaking, _ = classify(before, after)
    assert any("no longer accepts `textStyle`" in line for line in breaking), breaking


# `group` carried the manifest's only pair of alternative field sets until
# spytial-core 5.0 retired its by-field form -- which is the change these two
# check for, so their fixture has to be synthetic now. `_match_variants` is
# still live code, and the next form with alternatives will arrive the same way
# this one left: inside a generated file, with no Python edited.
def _two_variant_surface():
    surface = _baseline()
    surface["forms"]["group"]["fieldSets"] = [
        {"required": ["selector", "name"], "optional": ["addEdge", "hold", "textStyle"]},
        {"required": ["addToGroup", "field", "groupOn"], "optional": ["hold", "selector"]},
    ]
    return surface


def test_dropping_a_whole_variant_is_breaking():
    """Core retiring the by-field form looked like this."""
    before = _two_variant_surface()
    after = _two_variant_surface()
    after["forms"]["group"]["fieldSets"] = [
        fs for fs in after["forms"]["group"]["fieldSets"] if "field" not in fs["required"]
    ]
    breaking, _ = classify(before, after)
    assert any("no longer accepts the" in line and "form" in line for line in breaking), (
        breaking
    )


def test_reordering_variants_alone_is_not_a_change():
    """Matching must be by content; the manifest's item order is not a contract."""
    before = _two_variant_surface()
    after = _two_variant_surface()
    after["forms"]["group"]["fieldSets"].reverse()
    assert classify(before, after) == ([], [])
