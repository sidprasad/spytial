from dataclasses import dataclass

from spytial.dataclass_builder import _generate_dataclass_builder_html
from spytial.evaluator import _generate_evaluator_html
from spytial.visualizer import (
    _generate_sequence_visualizer_html,
    _generate_visualizer_html,
)


def test_visualizer_html_uses_current_core_bundle_urls():
    html = _generate_visualizer_html({"atoms": [], "relations": []}, "constraints: []\n")

    assert "cdn.jsdelivr.net/npm/spytial-core@" in html
    assert "spytial-core-complete.global.js" in html
    assert "spytial-core-complete.global.min.js" not in html
    assert "window.__spytialCoreBrowserBundle" not in html
    assert "typeof candidate.JSONDataInstance === 'function'" in html


def test_sequence_visualizer_html_uses_current_core_bundle_urls():
    html = _generate_sequence_visualizer_html(
        data_instances=[{"atoms": [], "relations": []}],
        spytial_spec="constraints: []\n",
        sequence_policy="stability",
    )

    assert "cdn.jsdelivr.net/npm/spytial-core@" in html
    assert "spytial-core-complete.global.js" in html
    assert "spytial-core-complete.global.min.js" not in html
    assert "window.__spytialCoreBrowserBundle" not in html
    assert 'typeof candidate.JSONDataInstance === "function"' in html


def test_evaluator_html_uses_current_core_bundle_urls():
    html = _generate_evaluator_html({"atoms": [], "relations": []})

    assert "cdn.jsdelivr.net/npm/spytial-core@" in html
    assert "spytial-core-complete.global.js" in html
    assert "spytial-core-complete.global.min.js" not in html
    assert "window.spytialcore || window.CndCore || window.CnDCore" in html


def test_dataclass_builder_html_uses_current_core_bundle_urls():
    @dataclass
    class SampleNode:
        value: int = 1

    html = _generate_dataclass_builder_html(
        initial_data={"atoms": [], "relations": []},
        cnd_spec="constraints: []\ndirectives: []\n",
        dataclass_name=SampleNode.__name__,
    )

    assert "cdn.jsdelivr.net/npm/spytial-core@" in html
    assert "spytial-core-complete.global.js" in html
    assert "spytial-core-complete.global.min.js" not in html
    assert "window.__spytialCoreBrowserBundle" not in html
    assert "typeof candidate.JSONDataInstance === 'function'" in html
    assert "window.clearAllErrors" in html
