"""Pinned browser assets and output-specific delivery.

SPYTIAL_ASSETS=auto (default), embedded, or cdn controls generated pages.
Vendored bytes are never downloaded at runtime.
"""

import base64
from functools import lru_cache
import os
from pathlib import Path
import sys

SPYTIAL_CORE_VERSION = "6.6.0"

_CDN_BASE = f"https://cdn.jsdelivr.net/npm/spytial-core@{SPYTIAL_CORE_VERSION}"
_BROWSER = "spytial-core-complete.global.js"
_COMPONENTS = "react-component-integration.global.js"
_CSS = "react-component-integration.css"
BROWSER_ASSETS = {
    _BROWSER: "text/javascript",
    _COMPONENTS: "text/javascript",
    _CSS: "text/css",
}
_ASSET_DIR = Path(__file__).parent / "_vendor" / "browser"
SPYTIAL_CORE_BROWSER_BUNDLE_URL = f"{_CDN_BASE}/dist/browser/{_BROWSER}"
SPYTIAL_CORE_COMPONENTS_BUNDLE_URL = f"{_CDN_BASE}/dist/components/{_COMPONENTS}"
SPYTIAL_CORE_COMPONENTS_CSS_URL = f"{_CDN_BASE}/dist/components/{_CSS}"


def get_spytial_core_version() -> str:
    """Return the version of spytial-core used by this package."""
    return SPYTIAL_CORE_VERSION


@lru_cache(maxsize=3)
def browser_asset(name):
    """Read one allowlisted package asset; also used by the local editor server."""
    if name not in BROWSER_ASSETS:
        raise ValueError(f"Unknown spytial browser asset: {name}")
    try:
        return (_ASSET_DIR / name).read_bytes()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Missing vendored browser asset {name}. Reinstall spytial, or run "
            "./update-spytial-core.sh in the source checkout."
        ) from exc


@lru_cache(maxsize=3)
def _embedded_url(name):
    # Data URLs preserve the exact published bytes, including strings containing
    # </script>. They do not need eval or HTML-parser escaping of bundled JS.
    encoded = base64.b64encode(browser_asset(name)).decode("ascii")
    return f"data:{BROWSER_ASSETS[name]};base64,{encoded}"


def get_template_asset_context(method=None):
    """Resolve delivery for the output, with an explicit environment override.

    Local edit() pages share vendored files through their existing server.
    Files/browser/headless outputs embed assets. Notebook outputs and Pyodide
    retain pinned CDN URLs to avoid repeating megabytes in each cell. Explicit
    file/headless output is portable even under Pyodide.
    """
    mode = os.environ.get("SPYTIAL_ASSETS", "auto")
    if mode not in ("auto", "embedded", "cdn"):
        raise ValueError("SPYTIAL_ASSETS must be auto, embedded, or cdn")
    if mode == "auto":
        if method == "server":
            mode = "local"
        elif method in ("file", "headless"):
            mode = "embedded"
        elif (
            method == "inline"
            or sys.platform == "emscripten"
            or "pyodide" in sys.modules
        ):
            mode = "cdn"
        else:
            mode = "embedded"
    names = (_BROWSER, _COMPONENTS, _CSS)
    if mode == "embedded":
        urls = [_embedded_url(name) for name in names]
    elif mode == "local":
        urls = [f"assets/{SPYTIAL_CORE_VERSION}/{name}" for name in names]
    else:
        urls = [
            SPYTIAL_CORE_BROWSER_BUNDLE_URL,
            SPYTIAL_CORE_COMPONENTS_BUNDLE_URL,
            SPYTIAL_CORE_COMPONENTS_CSS_URL,
        ]
    context = dict(
        zip(
            (
                "spytial_core_browser_bundle_url",
                "spytial_core_components_bundle_url",
                "spytial_core_components_css_url",
            ),
            urls,
        )
    )
    context["spytial_core_offline"] = mode != "cdn"
    return context
