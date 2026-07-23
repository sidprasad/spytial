"""Real-browser end-to-end test for ``spytial.diagram()``.

The offline tests in ``test_core_embedding_assets.py`` check what the generated
HTML *asks* for. This one checks that the pinned spytial-core release actually
*delivers* it: that the CDN bundle still exposes the handful of symbols the
visualizer page reads off ``window.spytialcore``, still registers
``<webcola-cnd-graph>``, and still renders a diagram.

That contract is not hypothetical. spytial-core 4.0.0 shrank the main global on
purpose, moving ``SQLEvaluator`` to ``spytial-core/sql-evaluator`` and
``SpytialExplorer`` to ``spytial-core/explorer``. Neither is used here, so the
bump was a no-op, but a future release that moves ``LayoutInstance`` or
``SGraphQueryEvaluator`` the same way would break every diagram at runtime with
nothing in the offline suite noticing.

**Opt-in**, like ``test_edit_browser.py``: skipped unless
``SPYTIAL_BROWSER_TESTS=1``, and it skips rather than fails when Playwright,
Chromium, or the CDN is unavailable.

Run with::

    SPYTIAL_BROWSER_TESTS=1 python -m pytest test/test_visualizer_browser.py -v
"""

import os
from dataclasses import dataclass
from typing import Optional

import pytest

import spytial
from spytial.annotations import serialize_to_yaml_string
from spytial.provider_system import CnDDataInstanceBuilder
from spytial.visualizer import _generate_visualizer_html

pytestmark = pytest.mark.skipif(
    os.environ.get("SPYTIAL_BROWSER_TESTS") != "1",
    reason="set SPYTIAL_BROWSER_TESTS=1 to run real-browser e2e (needs playwright + chromium + network)",
)


@pytest.fixture(scope="module")
def pw_browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright not installed")

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


@spytial.orientation(selector="next", directions=["left"])
@spytial.atomStyle(selector="Node", fillStyle=spytial.FillStyle(color="lightblue"))
@dataclass
class Node:
    value: int
    next: Optional["Node"] = None


# webcola-cnd-graph draws into its shadow root, so plain document queries miss
# the SVG entirely. Everything below goes through this.
SVG_TEXTS = """() => {
    const el = document.querySelector('webcola-cnd-graph');
    const root = el && (el.shadowRoot || el);
    if (!root) return [];
    return Array.from(root.querySelectorAll('text')).map(t => t.textContent.trim());
}"""


@pytest.fixture(scope="module")
def rendered(pw_browser, tmp_path_factory):
    """Render a small annotated object and hand back the settled page."""
    chain = Node(1, Node(2, Node(3)))

    # Same two steps diagram() takes before handing off to the template.
    builder = CnDDataInstanceBuilder()
    html = _generate_visualizer_html(
        builder.build_instance(chain),
        serialize_to_yaml_string(builder.get_collected_decorators()),
    )
    page_file = tmp_path_factory.mktemp("viz") / "diagram.html"
    page_file.write_text(html)

    errors: list = []

    def on_console(msg):
        if msg.type == "error":
            errors.append(f"[{msg.type}] {msg.text}")

    page = pw_browser.new_page()
    page.on("console", on_console)
    page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
    page.goto(page_file.as_uri(), wait_until="domcontentloaded", timeout=30000)
    page.wait_for_function(
        "customElements.get('webcola-cnd-graph') !== undefined", timeout=30000
    )
    page.wait_for_function(f"() => ({SVG_TEXTS})().length > 0", timeout=30000)
    yield page, errors
    page.close()


def test_core_global_exposes_the_symbols_the_page_reads(rendered):
    """The three symbols visualizer_template.html pulls off window.spytialcore."""
    page, _ = rendered
    present = page.evaluate(
        """() => {
            const core = window.spytialcore || window.CndCore || window.CnDCore;
            const want = ['JSONDataInstance', 'LayoutInstance', 'SGraphQueryEvaluator'];
            return core && want.filter(n => typeof core[n] === 'function');
        }"""
    )
    assert present == ["JSONDataInstance", "LayoutInstance", "SGraphQueryEvaluator"]


def test_error_modal_mount_api_is_available(rendered):
    """window.mountErrorMessageModal comes from the separate components bundle."""
    page, _ = rendered
    assert page.evaluate("typeof window.mountErrorMessageModal") == "function"


def test_diagram_actually_renders(rendered):
    """A real diagram, not just a loaded bundle: labelled nodes in the SVG."""
    page, _ = rendered
    labels = page.evaluate(SVG_TEXTS)
    assert "next" in labels
    assert {"1", "2", "3"} <= set(labels)


def test_render_is_console_clean(rendered):
    page, errors = rendered
    assert errors == []
