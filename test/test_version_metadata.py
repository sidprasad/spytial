from pathlib import Path

import spytial
from spytial._version import __version__


def test_public_version_matches_internal_version():
    assert spytial.__version__ == __version__


def test_pyproject_uses_dynamic_version_from_package():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")

    assert 'dynamic = ["version"]' in text
    assert 'version = {attr = "spytial._version.__version__"}' in text
