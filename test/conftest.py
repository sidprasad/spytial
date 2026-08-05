"""Make this directory importable, so test modules can share helpers.

``test/`` is a flat directory of test modules, not a package. Under pytest's
default ``prepend`` import mode that is already enough -- pytest puts the
directory on ``sys.path`` before importing anything in it, so ``import
conformance`` resolves. Under ``--import-mode=importlib`` it does not, and
collection fails outright with ``ModuleNotFoundError``.

conftest is loaded before the test modules beside it under either mode, so
doing it here covers both. Without this, a helper module is usable only by the
import mode that happens to be the default today.
"""

import sys
from pathlib import Path

_TEST_DIR = str(Path(__file__).resolve().parent)

if _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)
