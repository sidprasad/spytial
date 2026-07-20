"""Depth guard for the object walk.

The walker recurses through real Python frames: one level of nesting costs
3-4 of them. Its own limit is therefore derived from the interpreter's frame
budget rather than fixed, so it always trips *before* CPython's — the walker
raises one clean error, CPython unwinds thousands of frames.

Tracked for removal in sidprasad/spytial#131 (iterative walk).
"""

import dataclasses
import sys
from typing import Optional

import pytest

from spytial.provider_system import (
    CnDDataInstanceBuilder,
    default_max_depth,
    _MIN_WALK_DEPTH,
    _MAX_WALK_DEPTH,
)


@dataclasses.dataclass
class Link:
    value: int
    _next: Optional["Link"] = None


def chain(n):
    head = Link(n)
    for i in range(n - 1, 0, -1):
        head = Link(i, head)
    return head


@pytest.fixture
def recursion_limit():
    """Restore the interpreter's recursion limit after a test changes it."""
    original = sys.getrecursionlimit()
    yield sys.setrecursionlimit
    sys.setrecursionlimit(original)


def test_depth_scales_with_interpreter_limit(recursion_limit):
    recursion_limit(1000)  # stock CPython
    stock = default_max_depth()
    recursion_limit(4000)
    raised = default_max_depth()
    assert raised > stock


def test_depth_stays_within_documented_bounds(recursion_limit):
    for limit in (100, 1000, 3000, 100_000):
        recursion_limit(max(limit, 100))
        assert _MIN_WALK_DEPTH <= default_max_depth() <= _MAX_WALK_DEPTH


def test_guard_trips_before_cpython_does(recursion_limit):
    # The point of deriving the cap: our error, not a 1000-frame unwind.
    recursion_limit(1000)
    with pytest.raises(RecursionError) as exc:
        CnDDataInstanceBuilder().build_instance(chain(default_max_depth() + 50))
    assert "nests deeper than" in str(exc.value)


def test_error_message_does_not_embed_the_object():
    # A deep structure's repr is a screenful and can itself raise while
    # formatting, so the message names the type only.
    deep = chain(default_max_depth() + 50)
    with pytest.raises(RecursionError) as exc:
        CnDDataInstanceBuilder().build_instance(deep)
    message = str(exc.value)
    assert "Link(value=" not in message
    assert "Link" in message and len(message) < 400


def test_chain_within_limit_walks_fully():
    # Regression: with `_next` skipped this produced 2 atoms regardless of
    # length; the depth guard must not silently truncate what it now follows.
    length = min(120, default_max_depth() - 5)
    di = CnDDataInstanceBuilder().build_instance(chain(length))
    assert sum(1 for a in di["atoms"] if a["type"] == "Link") == length
