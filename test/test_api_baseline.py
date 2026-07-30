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


def _field_sets_union(form):
    """All keywords a form accepts, and the ones every field set requires.

    A form with alternative field sets (``group``) requires a keyword only if
    no set lets you leave it out, which is what a user actually experiences.
    """
    accepted, required = set(), None
    for field_set in form["fieldSets"]:
        accepted |= set(field_set["required"]) | set(field_set["optional"])
        this_set = set(field_set["required"])
        required = this_set if required is None else (required & this_set)
    return accepted, (required or set())


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
        old_accepted, old_required = _field_sets_union(before)
        new_accepted, new_required = _field_sets_union(after)
        for key in sorted(old_accepted - new_accepted):
            breaking.append(f"`{name}` no longer accepts `{key}`")
        for key in sorted(new_accepted - old_accepted):
            additive.append(f"`{name}` accepts new keyword `{key}`")
        for key in sorted((new_required - old_required) & old_accepted):
            breaking.append(f"`{name}.{key}` became required")
        for key in sorted(old_required - new_required):
            additive.append(f"`{name}.{key}` is no longer required")

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
