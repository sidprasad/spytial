"""Shared spytial-core asset definitions.

Assets are vendored locally (spytial/vendor/) by running::

    python scripts/vendor_core.py

The vendored files are read once at import time and served inline in
HTML templates and anywidget ESM modules, eliminating CDN dependency
and browser cache issues.
"""

import os
from pathlib import Path

SPYTIAL_CORE_NPM_VERSION = os.environ.get("SPYTIAL_CORE_NPM_VERSION", "2.2.3")

_VENDOR_DIR = Path(__file__).parent / "vendor"


def _read_vendor(filename: str) -> str:
    """Read a vendored asset file, raising a clear error if missing."""
    path = _VENDOR_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Vendored asset {filename} not found in {_VENDOR_DIR}.\n"
            "Run: python scripts/vendor_core.py"
        )
    return path.read_text(encoding="utf-8")


def get_vendor_js_core() -> str:
    """Return the spytial-core browser bundle JS source."""
    return _read_vendor("spytial-core-complete.global.js")


def get_vendor_js_components() -> str:
    """Return the React component integration JS source."""
    return _read_vendor("react-component-integration.global.js")


def get_vendor_css_components() -> str:
    """Return the React component integration CSS source."""
    return _read_vendor("react-component-integration.css")


def get_template_asset_context() -> dict:
    """Return inline asset content for injection into HTML templates."""
    return {
        "spytial_core_js": get_vendor_js_core(),
        "spytial_components_js": get_vendor_js_components(),
        "spytial_components_css": get_vendor_css_components(),
    }
