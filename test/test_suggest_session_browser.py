"""Real embedded controls: requirement prompts, dragging, acceptance, and history."""

import os
from pathlib import Path
import threading

import pytest

from spytial.suggest import suggest, FixedExamples, FixedProposals
from test_suggest_session import Tree, tree, Provider, clean_tree_binding
from test_suggest_living import alignment

pytestmark = pytest.mark.skipif(
    os.environ.get("SPYTIAL_BROWSER_TESTS") != "1", reason="opt-in real browser test"
)


@pytest.fixture(autouse=True)
def local_renderer(monkeypatch):
    monkeypatch.setenv(
        "SPYTIAL_BROWSER_BUNDLE",
        str(
            Path(__file__).resolve().parents[1]
            / "spytial/_vendor/browser/spytial-core-complete.global.js"
        ),
    )


def ready(page):
    page.get_by_role("button", name="Upvote", exact=True).first.wait_for()
    page.wait_for_function(
        "document.querySelector('.vote') && !document.querySelector('.vote').disabled"
    )


def request_requirement(page, prompt):
    if not page.locator("#requirement-form").is_visible():
        page.get_by_role("button", name="Add requirement", exact=True).click()
    page.get_by_label("Requirement", exact=True).fill(prompt)
    page.get_by_role("button", name="Explore", exact=True).click()
    ready(page)


def accept_first(page):
    page.get_by_role("button", name="Upvote", exact=True).first.click()
    page.get_by_role("button", name="Downvote", exact=True).last.click()
    page.get_by_role("button", name="Resume", exact=True).wait_for()
    page.locator("#requirement-form").wait_for(state="visible")
    assert page.get_by_label("Requirement", exact=True).input_value() == ""


def test_prompt_drag_partial_vote_reload_and_history():
    from playwright.sync_api import sync_playwright

    provider = Provider()
    with suggest(
        tree(), search=FixedExamples(), proposer=provider
    ) as s, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1000, "height": 600})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(s._url())
        page.wait_for_function(
            "document.querySelector('webcola-cnd-graph')?.getNodePositions().length > 0"
        )
        assert not provider.prompts
        assert page.locator("webcola-cnd-graph").count() == 1
        request_requirement(page, "Parents above children")
        assert page.locator("webcola-cnd-graph").count() == 2
        assert not page.locator("#requirement-form").is_visible()
        node = page.locator("#diagram-0 webcola-cnd-graph .node").first
        box = node.bounding_box()
        assert box
        positions = (
            "document.querySelector('#diagram-0 webcola-cnd-graph').getNodePositions()"
        )
        before = page.evaluate(positions)
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 55, y + 25, steps=12)
        page.wait_for_function(
            f"before => JSON.stringify({positions}) !== JSON.stringify(before)",
            arg=before,
        )
        page.mouse.up()
        page.get_by_role("button", name="Upvote", exact=True).first.click()
        page.wait_for_function(
            "document.querySelector('[data-side=\"0\"] [data-value=upvote]').getAttribute('aria-pressed') === 'true'"
        )
        assert s.history[0]["votes"] == ["upvote", None]
        saved = s.history[0]["layout_states"][0]["positions"]
        page.reload()
        ready(page)
        assert (
            page.get_by_role("button", name="Upvote", exact=True).first.get_attribute(
                "aria-pressed"
            )
            == "true"
        )
        page.get_by_role("button", name="Downvote", exact=True).last.click()
        page.get_by_role("button", name="Resume", exact=True).wait_for()
        assert s.active_requirement.status == "accepted"
        page.get_by_role("button", name="History", exact=True).click()
        page.wait_for_function(
            "document.querySelector('#history-position').textContent === '1 / 1'"
        )
        restored = page.evaluate(positions)
        for a, b in zip(
            sorted(saved, key=lambda p: p["id"]),
            sorted(restored, key=lambda p: p["id"]),
        ):
            assert abs(a["x"] - b["x"]) < 0.5 and abs(a["y"] - b["y"]) < 0.5
        page.get_by_role("button", name="Unsure", exact=True).first.click()
        page.wait_for_function(
            "document.querySelector('[data-side=\"0\"] [data-value=unsure]').getAttribute('aria-pressed') === 'true'"
        )
        assert s.active_requirement.status == "draft"
        assert s.history[0]["votes"] == ["unsure", "downvote"]
        assert not errors
        browser.close()


def test_add_and_edit_requirement_keep_context_and_enduring_evidence():
    from playwright.sync_api import sync_playwright
    from test_suggest_session import proposal

    provider = Provider(
        [proposal(["below"]), proposal(["right"])],
        [alignment("horizontal"), alignment("vertical")],
        [proposal(["below", "left"])],
    )
    with suggest(
        tree(), search=FixedExamples(), proposer=provider
    ) as s, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1100, "height": 650})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(s._url())
        request_requirement(page, "Parents above children")
        accept_first(page)
        first = s.requirements[0]
        background = s.spec.to_registry()
        request_requirement(page, "Align siblings")
        assert s.current["context"] == background
        for side in s.current["sides"]:
            assert all(
                c in side["program"]["constraints"] for c in background["constraints"]
            )
        accept_first(page)
        assert all(p.status == "accepted" for p in s.requirements)
        page.get_by_role(
            "button", name="Edit requirement: Parents above children", exact=True
        ).click()
        page.get_by_label("Requirement", exact=True).fill(
            "Left children below and left"
        )
        page.get_by_role("button", name="Revise", exact=True).click()
        ready(page)
        assert len(s.history) == 2 and s.requirements[0].id == first.id
        assert s.current["requirement_revision"] == 2
        assert any("align" in c for c in s.current["context"]["constraints"])
        page.get_by_role("button", name="I'm done", exact=True).click()
        page.get_by_role("button", name="Resume", exact=True).wait_for()
        assert all(p.status == "accepted" for p in s.requirements)
        page.wait_for_function(
            "document.querySelectorAll('.card:not([hidden])').length === 1"
        )
        page.screenshot(path="/tmp/spytial-requirement-session.png", full_page=True)
        page.get_by_role("button", name="History", exact=True).click()
        page.get_by_role("button", name="Previous judgment", exact=True).click()
        page.get_by_role("status").filter(has_text="Parents above children").wait_for()
        assert not errors
        browser.close()


def test_notebook_is_interactive_before_model_finishes(monkeypatch):
    from playwright.sync_api import sync_playwright, expect

    entered, release = threading.Event(), threading.Event()
    checking, checked = threading.Event(), threading.Event()
    provider = Provider()
    from spytial.suggest._checks import ProgramChecks

    selectors = ProgramChecks.selectors

    def slow_check(*args, **kwargs):
        checking.set()
        assert checked.wait(30)
        return selectors(*args, **kwargs)

    monkeypatch.setattr(ProgramChecks, "selectors", slow_check)

    def slow(prompt, *, schema):
        entered.set()
        assert release.wait(30)
        return provider(prompt, schema=schema)

    with suggest(
        tree(), search=FixedExamples(), proposer=slow
    ) as s, sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(s._repr_html_())
            frame = page.frame_locator('iframe[title="Diagram requirements"]')
            frame.get_by_label("Requirement", exact=True).fill("Parents above children")
            assert not entered.is_set()
            frame.get_by_role("button", name="Explore", exact=True).click()
            assert entered.wait(5)
            frame.get_by_role("status").filter(
                has_text="Drafting requirement"
            ).wait_for()
            assert not s._requirements[0].candidates
            release.set()
            assert checking.wait(5)
            frame.get_by_role("status").filter(
                has_text="Checking requirement"
            ).wait_for()
            checked.set()
            expect(
                frame.get_by_role("button", name="Upvote", exact=True).first
            ).to_be_enabled(timeout=30000)
            browser.close()
        finally:
            release.set()
            checked.set()


@pytest.mark.parametrize("direction", ["clockwise", "counterclockwise"])
def test_cyclic_requirements_remain_draggable_and_classifiable(direction):
    from playwright.sync_api import sync_playwright

    nodes = [Tree(i) for i in range(4)]
    for a, b in zip(nodes, nodes[1:] + nodes[:1]):
        a.left = b
    programs = [
        {
            "summary": d,
            "operations": [
                {"kind": "cyclic", "selector": "left", "direction": d, "hold": "always"}
            ],
        }
        for d in (
            direction,
            "counterclockwise" if direction == "clockwise" else "clockwise",
        )
    ]
    with suggest(
        nodes[0], search=FixedExamples(), proposer=FixedProposals(programs)
    ) as s, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(s._url())
        request_requirement(page, "Draw this ring in a circle")
        assert s.current["kind"] == "confirmation"
        for side in (0, 1):
            layout = page.locator(f"#diagram-{side} webcola-cnd-graph").evaluate(
                "g => g.getLayoutState()"
            )
            s.vote(side, "upvote", layout_state=layout)
        assert s.history[0]["complete"]
        browser.close()


def test_done_button_combines_multiple_supported_survivors():
    from playwright.sync_api import sync_playwright
    from test_suggest_session import state

    with suggest(
        tree(), search=FixedExamples(), proposer=Provider()
    ) as s, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(s._url())
        request_requirement(page, "Parents above children")
        page.get_by_role("button", name="Unsure", exact=True).first.click()
        page.get_by_role("button", name="Unsure", exact=True).last.click()
        ready(page)
        # A shared approved arrangement supports both surviving interpretations.
        s.next()
        s.vote(0, "upvote", layout_state=state(120, 150))
        assert len(s.survivors) == 2
        page.get_by_role("button", name="I'm done", exact=True).click()
        page.get_by_role("button", name="Resume", exact=True).wait_for()
        page.wait_for_function(
            "document.querySelectorAll('.card:not([hidden])').length === 1"
        )
        assert len(s.active_requirement.result["accepted_ids"]) == 2
        assert s.active_requirement.status == "accepted"
        browser.close()
