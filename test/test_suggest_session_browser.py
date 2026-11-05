"""Local, real-renderer smoke tests; opt in with SPYTIAL_BROWSER_TESTS=1."""

import os
from pathlib import Path
import threading

import pytest

from test_suggest_session import Tree, tree, Provider
from spytial.suggest import suggest, FixedExamples, FixedProposals

pytestmark = pytest.mark.skipif(
    os.environ.get("SPYTIAL_BROWSER_TESTS") != "1", reason="opt-in real browser test"
)


@pytest.fixture(autouse=True)
def local_renderer(monkeypatch):
    bundle = (
        Path(__file__).resolve().parents[1]
        / "spytial/_vendor/browser/spytial-core-complete.global.js"
    )
    monkeypatch.setenv("SPYTIAL_BROWSER_BUNDLE", str(bundle))


def ready(page):
    page.wait_for_function(
        "document.querySelector('.vote') && !document.querySelector('.vote').disabled"
    )


def test_independent_votes_reload_and_programmatic_revision():
    from playwright.sync_api import sync_playwright

    provider = Provider()
    with suggest(
        tree(), search=FixedExamples(), proposer=provider
    ) as session, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 450})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(session._url())
        ready(page)
        assert page.get_by_role("alert").is_hidden()
        assert page.locator("webcola-cnd-graph").count() == 2
        assert (
            page.locator(
                ":is(h1, h2, textarea, input, select, details):visible"
            ).count()
            == 0
        )
        # Six votes plus History and I'm done; no renderer toolbar.
        assert page.get_by_role("button").count() == 8
        assert page.locator("#status").is_hidden()
        assert page.evaluate(
            "document.documentElement.scrollHeight <= window.innerHeight"
        )
        assert (
            page.evaluate(
                "document.querySelector('#diagram-0 webcola-cnd-graph').getNodePositions().length"
            )
            > 0
        )
        page.screenshot(path="/tmp/spytial-suggest-minimal.png", full_page=True)

        # A late renderer failure must prevent collecting a misleading judgment.
        page.evaluate(
            """document.querySelector('webcola-cnd-graph').dispatchEvent(
            new CustomEvent('layout-error', {detail: {message: 'Simulated layout failure'}}))"""
        )
        assert page.get_by_role("button", name="Upvote").first.is_disabled()
        assert not session.history
        page.reload()
        ready(page)
        # Critique includes exploring the permitted layouts by dragging.
        node = page.locator("#diagram-0 webcola-cnd-graph .node").first
        box = node.bounding_box()
        assert box is not None
        positions = (
            "document.querySelector('#diagram-0 webcola-cnd-graph').getNodePositions()"
        )
        before = page.evaluate(positions)
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 60, y + 30, steps=12)
        page.wait_for_function(
            f"before => JSON.stringify({positions}) !== JSON.stringify(before)",
            arg=before,
        )
        page.mouse.up()
        page.get_by_role("button", name="Upvote").first.click()
        page.wait_for_function(
            "document.querySelector('[data-side=\"0\"] [data-value=upvote]').getAttribute('aria-pressed') === 'true'"
        )
        assert session.history[0]["votes"] == ["upvote", None]
        page.reload()
        ready(page)
        assert (
            page.get_by_role("button", name="Upvote").first.get_attribute(
                "aria-pressed"
            )
            == "true"
        )
        page.get_by_role("button", name="Unsure").last.click()
        page.get_by_role("button", name="I'm done", exact=True).click()
        page.get_by_role("button", name="Resume", exact=True).wait_for()
        assert session.paused
        assert session.history[0]["votes"] == ["upvote", "unsure"]
        assert session.history[0]["complete"]
        assert all(
            layout["positions"] for layout in session.history[0]["layout_states"]
        )
        saved = session.history[0]["layout_states"][0]["positions"]
        page.get_by_role("button", name="History", exact=True).click()
        page.wait_for_function(
            "document.querySelector('#history-position').textContent === '1 / 1'"
        )
        restored = page.evaluate(
            "document.querySelector('#diagram-0 webcola-cnd-graph').getNodePositions()"
        )
        assert {p["id"] for p in restored} == {p["id"] for p in saved}
        for a, b in zip(
            sorted(saved, key=lambda p: p["id"]),
            sorted(restored, key=lambda p: p["id"]),
        ):
            assert abs(a["x"] - b["x"]) < 0.5
            assert abs(a["y"] - b["y"]) < 0.5
        page.get_by_role("button", name="Unsure").first.click()
        page.wait_for_function(
            "document.querySelector('[data-side=\"0\"] [data-value=unsure]').getAttribute('aria-pressed') === 'true'"
        )
        assert session.history[0]["votes"] == ["unsure", "unsure"]
        assert all(c.positive_votes == 0 for c in session.candidates)
        page.get_by_role("button", name="Back", exact=True).click()
        session.resume()
        session.revise("Keep whole subtrees together")
        assert len(session.history) == 1
        assert '"votes": ["unsure", "unsure"]' in provider.prompts[-1]
        assert not errors
        browser.close()


def test_notebook_frame_appears_before_model_finishes():
    from playwright.sync_api import sync_playwright

    entered, release = threading.Event(), threading.Event()

    def slow_provider(prompt, *, schema):
        entered.set()
        assert release.wait(30)
        return Provider()(prompt, schema=schema)

    with suggest(
        tree(), search=FixedExamples(), proposer=slow_provider
    ) as session, sync_playwright() as pw:
        try:
            assert entered.wait(5)
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 900, "height": 500})
            page.set_content(session._repr_html_())
            frame = page.frame_locator('iframe[title="Diagram comparisons"]')
            frame.get_by_role("status").filter(has_text="Drafting proposals").wait_for()
            assert frame.locator(".card").count() == 2
            assert frame.get_by_role("button").count() == 8
            assert frame.get_by_role("button", name="Upvote").first.is_disabled()
            assert not session._ready.is_set()
            release.set()
            from playwright.sync_api import expect

            expect(frame.get_by_role("button", name="Upvote").first).to_be_enabled(
                timeout=30000
            )
            assert frame.locator("webcola-cnd-graph").count() == 2
            browser.close()
        finally:
            release.set()


@pytest.mark.parametrize("direction", ["clockwise", "counterclockwise"])
def test_cyclic_rendered_arrangements_can_be_classified(direction):
    from playwright.sync_api import sync_playwright

    nodes = [Tree(i) for i in range(4)]
    for a, b in zip(nodes, nodes[1:] + nodes[:1]):
        a.left = b
    proposals = [
        {
            "summary": direction,
            "operations": [
                {
                    "kind": "cyclic",
                    "selector": "left",
                    "direction": direction,
                    "hold": "always",
                }
            ],
        }
        for direction in (
            direction,
            "counterclockwise" if direction == "clockwise" else "clockwise",
        )
    ]
    with suggest(
        nodes[0], search=FixedExamples(), proposer=FixedProposals(proposals)
    ) as session, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 450})
        page.goto(session._url())
        ready(page)
        # Core cannot check the conjunction of the two cyclic directions.
        # This must not break exploration or count as rejection evidence.
        assert session.spec.result["status"] == "unsupported"
        assert all(c.negative_votes == 0 for c in session.candidates)
        assert session.current["kind"] == "confirmation"
        for side in (0, 1):
            layout = page.locator(f"#diagram-{side} webcola-cnd-graph").evaluate(
                "g => g.getLayoutState()"
            )
            record = session.vote(side, "upvote", layout_state=layout)
            assert record["votes"][side] == "upvote"
        # Confirmation shows an instance and a counterexample for the first
        # candidate, not necessarily an instance of each cyclic direction.
        candidate = session.candidates[0]
        assert candidate.positive_votes == 1
        assert candidate.negative_votes == 1
        browser.close()
