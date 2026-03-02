"""Shared spytial-core browser asset definitions for HTML templates."""

SPYTIAL_CORE_NPM_VERSION = "1.9.4"
_CDN_BASE = f"https://cdn.jsdelivr.net/npm/spytial-core@{SPYTIAL_CORE_NPM_VERSION}"

SPYTIAL_CORE_BROWSER_BUNDLE_URL = (
    f"{_CDN_BASE}/dist/browser/spytial-core-complete.global.js"
)
SPYTIAL_CORE_COMPONENTS_BUNDLE_URL = (
    f"{_CDN_BASE}/dist/components/react-component-integration.global.js"
)
SPYTIAL_CORE_COMPONENTS_CSS_URL = (
    f"{_CDN_BASE}/dist/components/react-component-integration.css"
)


def get_template_asset_context():
    """Return the shared asset URLs injected into HTML templates."""

    return {
        "spytial_core_browser_bundle_url": SPYTIAL_CORE_BROWSER_BUNDLE_URL,
        "spytial_core_components_bundle_url": SPYTIAL_CORE_COMPONENTS_BUNDLE_URL,
        "spytial_core_components_css_url": SPYTIAL_CORE_COMPONENTS_CSS_URL,
    }
