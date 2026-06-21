"""Real-browser end-to-end tests for ``spytial.edit()``.

These drive a real headless Chromium against the live editor page (which loads
spytial-core from the CDN) — covering the one surface the unit tests can't: the
actual web component rendering, ``getDataInstance()``, and the Done/Cancel POST →
``reify`` chain.

**Opt-in.** They are skipped unless ``SPYTIAL_BROWSER_TESTS=1`` is set, so the
normal suite / CI never depends on a browser or network. Even when opted in they
skip gracefully if Playwright, Chromium, or the CDN is unavailable.

Run with::

    SPYTIAL_BROWSER_TESTS=1 python -m pytest test/test_edit_browser.py -v
"""

import os
import queue
import threading
from contextlib import contextmanager

import pytest

import spytial
import spytial.structured_input as si

pytestmark = pytest.mark.skipif(
    os.environ.get("SPYTIAL_BROWSER_TESTS") != "1",
    reason="set SPYTIAL_BROWSER_TESTS=1 to run real-browser e2e (needs playwright + chromium + network)",
)

DONE = "#spytial-done"
CANCEL = "#spytial-cancel"
COMMITTED = "document.body.innerText.includes('sent back to Python')"


@pytest.fixture(scope="module")
def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright not installed")

    # CDN reachability — turn "offline" into a skip, not a failure.
    import urllib.request
    from spytial.core_assets import SPYTIAL_CORE_BROWSER_BUNDLE_URL

    try:
        urllib.request.urlopen(SPYTIAL_CORE_BROWSER_BUNDLE_URL, timeout=8).read(1)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"spytial-core CDN unreachable: {exc}")

    pw = sync_playwright().start()
    try:
        b = pw.chromium.launch(headless=True)
    except Exception as exc:  # noqa: BLE001 — browser binary may be missing
        pw.stop()
        pytest.skip(f"chromium not available (run `playwright install chromium`): {exc}")
    yield b
    b.close()
    pw.stop()


@contextmanager
def _editing(monkeypatch, seed, **edit_kwargs):
    """Run ``edit(seed)`` in a worker thread; yield ``(url, result_holder)``.

    ``_show`` is patched to hand us the server URL instead of opening a browser,
    so the test can drive the page itself. The worker is joined on exit.
    """
    url_q: "queue.Queue[str]" = queue.Queue()
    monkeypatch.setattr(si, "_show", lambda url, height: url_q.put(url))
    monkeypatch.setattr(si, "_announce_editing", lambda url: None)

    holder: dict = {}

    def run():
        try:
            holder["value"] = spytial.edit(seed, **edit_kwargs)
        except BaseException as exc:  # noqa: BLE001 — surface to the test
            holder["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    try:
        yield url_q.get(timeout=15), holder, worker
    finally:
        worker.join(timeout=25)


def _open_editor(browser, url):
    page = browser.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_function(
        "customElements.get('structured-input-graph') !== undefined", timeout=30000
    )
    return page


# ---------------------------------------------------------------------------


def test_done_round_trips(browser, monkeypatch):
    seed = {"name": "root", "children": [{"v": 1}, {"v": 2}], "count": 3}
    with _editing(monkeypatch, seed, timeout=60) as (url, holder, worker):
        page = _open_editor(browser, url)
        # Done enables only when getDataInstance() has atoms → component works.
        page.wait_for_selector(f"{DONE}:not([disabled])", timeout=40000)
        page.click(DONE)
        page.wait_for_function(COMMITTED, timeout=15000)
        page.close()
    assert "error" not in holder, holder.get("error")
    assert holder.get("value") == seed


def test_cancel_returns_seed(browser, monkeypatch):
    seed = {"a": 1, "b": [2, 3]}
    with _editing(monkeypatch, seed, timeout=60) as (url, holder, worker):
        page = _open_editor(browser, url)
        page.wait_for_selector(CANCEL, timeout=40000)
        page.click(CANCEL)
        page.wait_for_function(COMMITTED, timeout=15000)
        page.close()
    assert holder.get("value") is seed  # default on_cancel="seed"


def test_an_edit_is_reflected(browser, monkeypatch):
    seed = {"count": 3, "tag": "x"}
    with _editing(monkeypatch, seed, timeout=60) as (url, holder, worker):
        page = _open_editor(browser, url)
        page.wait_for_selector(f"{DONE}:not([disabled])", timeout=40000)
        # Change the int atom labelled "3" to "99" and push it back through the
        # component, proving edit() returns the *current* state, not the seed.
        n = page.evaluate(
            """() => {
                const el = document.getElementById('structured-graph');
                const core = window.spytialcore || window.CnDCore || window.CndCore;
                const di = el.getDataInstance();
                let n = 0;
                for (const a of di.atoms) if (a.type === 'int' && a.label === '3') { a.label = '99'; n++; }
                el.setDataInstance(new core.JSONDataInstance(di));
                return n;
            }"""
        )
        assert n == 1
        page.wait_for_selector(f"{DONE}:not([disabled])", timeout=20000)
        page.click(DONE)
        page.wait_for_function(COMMITTED, timeout=15000)
        page.close()
    assert holder.get("value") == {"count": 99, "tag": "x"}


def test_closing_the_page_does_not_hang(browser, monkeypatch):
    # The worst failure mode: a closed page that deadlocks the kernel. Closing
    # the tab must unblock edit() (pagehide beacon, or the overall timeout).
    seed = {"a": 1}
    with _editing(monkeypatch, seed, timeout=5) as (url, holder, worker):
        page = _open_editor(browser, url)
        page.wait_for_selector(CANCEL, timeout=40000)  # connected
        page.close()  # close without committing
    assert not worker.is_alive(), "edit() hung after the page closed"
    assert holder.get("value") is seed  # disconnect/cancel → on_cancel="seed"
