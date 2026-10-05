import base64
import re
from pathlib import Path

import pytest

from spytial import core_assets
from spytial.structured_input import _generate_editor_html
from spytial.evaluator import _generate_evaluator_html
from spytial.visualizer import (
    _generate_sequence_visualizer_html,
    _generate_visualizer_html,
)

EMPTY = {"atoms": [], "relations": []}


def pages(method=None):
    return [
        _generate_visualizer_html(EMPTY, "constraints: []\n", method=method),
        _generate_sequence_visualizer_html(
            [EMPTY], "constraints: []\n", "stability", method=method
        ),
        _generate_evaluator_html(EMPTY, method=method),
        _generate_editor_html(EMPTY, "constraints: []\n", "dict", method=method),
    ]


@pytest.fixture(autouse=True)
def default_assets(monkeypatch):
    monkeypatch.delenv("SPYTIAL_ASSETS", raising=False)


def test_standalone_pages_embed_exact_published_bytes():
    for html in pages("file"):
        scripts = re.findall(r'<script[^>]+src="(data:[^"]+)"', html)
        assert scripts
        assert base64.b64decode(
            scripts[0].split(",", 1)[1]
        ) == core_assets.browser_asset("spytial-core-complete.global.js")
        assert 'src="https://cdn.jsdelivr.net/' not in html
        assert 'href="https://cdn.jsdelivr.net/' not in html
    # The editor retry reuses the original script URL; it must not embed a
    # second multi-megabyte copy of the core bundle in its retry handler.
    assert pages("file")[-1].count("data:text/javascript;base64,") == 2


def test_notebook_outputs_remain_small_and_version_pinned():
    for html in pages("inline"):
        assert core_assets.SPYTIAL_CORE_BROWSER_BUNDLE_URL in html
        assert 'src="data:' not in html
        assert len(html) < 150_000


@pytest.mark.parametrize(
    "mode,method,embedded", [("embedded", "inline", True), ("cdn", "file", False)]
)
def test_explicit_override_applies_to_every_output(monkeypatch, mode, method, embedded):
    monkeypatch.setenv("SPYTIAL_ASSETS", mode)
    for html in pages(method):
        assert ('src="data:text/javascript;base64,' in html) == embedded


def test_pyodide_default_and_portable_export(monkeypatch):
    monkeypatch.setattr(core_assets.sys, "platform", "emscripten")
    assert core_assets.get_template_asset_context()[
        "spytial_core_browser_bundle_url"
    ].startswith("https:")
    assert core_assets.get_template_asset_context("file")[
        "spytial_core_browser_bundle_url"
    ].startswith("data:")
    monkeypatch.setenv("SPYTIAL_ASSETS", "embedded")
    assert core_assets.get_template_asset_context("inline")[
        "spytial_core_browser_bundle_url"
    ].startswith("data:")


def test_live_editor_uses_relative_packaged_assets():
    html = _generate_editor_html(EMPTY, "constraints: []\n", "dict", commit=True)
    assert (
        f'src="assets/{core_assets.SPYTIAL_CORE_VERSION}/spytial-core-complete.global.js"'
        in html
    )
    assert 'src="https:' not in html
    assert 'src="data:' not in html


def test_invalid_mode_and_missing_package_asset_fail_clearly(monkeypatch, tmp_path):
    monkeypatch.setenv("SPYTIAL_ASSETS", "typo")
    with pytest.raises(ValueError, match="SPYTIAL_ASSETS"):
        core_assets.get_template_asset_context()
    monkeypatch.setattr(core_assets, "_ASSET_DIR", tmp_path)
    core_assets.browser_asset.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="Reinstall spytial"):
            core_assets.browser_asset("spytial-core-complete.global.js")
        with pytest.raises(ValueError):
            core_assets.browser_asset("../../core_assets.py")
    finally:
        core_assets.browser_asset.cache_clear()


def test_file_output_stays_embedded_in_a_notebook(monkeypatch, tmp_path):
    import spytial
    import spytial.utils

    monkeypatch.setattr(spytial.utils, "is_notebook", lambda: True)
    monkeypatch.chdir(tmp_path)
    path = spytial.diagram({"value": 1}, method="file", auto_open=False)
    assert 'src="data:text/javascript;base64,' in Path(path).read_text()
