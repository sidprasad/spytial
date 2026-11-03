"""Local, real-renderer smoke tests; opt in with SPYTIAL_BROWSER_TESTS=1."""

import os
from pathlib import Path
import threading

import pytest

from test_suggest_session import tree, Provider
from spytial.suggest import suggest, FixedExamples

pytestmark = pytest.mark.skipif(
    os.environ.get("SPYTIAL_BROWSER_TESTS") != "1", reason="opt-in real browser test"
)


@pytest.fixture(autouse=True)
def local_renderer(monkeypatch):
    bundle = (
        Path(__file__).resolve().parents[2]
        / "spytial-core/dist/browser/spytial-core-complete.global.js"
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
        # Only the six vote controls are visible, including inside the renderer.
        assert page.get_by_role("button").count() == 6
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
        page.wait_for_function(
            "document.querySelector('#status').textContent === 'No further comparison found.'"
        )
        assert session.history[0]["votes"] == ["upvote", "unsure"]
        assert session.history[0]["complete"]
        assert all(
            layout["positions"] for layout in session.history[0]["layout_states"]
        )
        session.revise("Keep whole subtrees together")
        assert len(session.history) == 1
        assert '"votes": ["upvote", "unsure"]' in provider.prompts[-1]
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
            assert frame.get_by_role("button").count() == 6
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
