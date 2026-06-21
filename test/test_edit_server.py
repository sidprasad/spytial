"""Tests for the server-backed ``spytial.edit()`` flow.

``edit()`` blocks on a browser interaction, so it can't be called directly in
CI. These exercise its pieces: the ephemeral ``_EditServer`` (real HTTP round
trip), the cancel/commit decision, reification of a committed payload, and
``edit()`` itself with the server + display monkeypatched out.
"""

import json
import threading
import urllib.request
from dataclasses import dataclass

import pytest

import spytial.structured_input as si
from spytial.structured_input import (
    _EditServer,
    _is_cancel,
    _reify_committed,
    EditCancelled,
)
from spytial.provider_system import CnDDataInstanceBuilder


# ---------------------------------------------------------------------------
# _EditServer — real HTTP round trip
# ---------------------------------------------------------------------------


def test_edit_server_serves_page_and_receives_commit():
    server = _EditServer("<html><body>hello editor</body></html>")
    box = {}

    waiter = threading.Thread(target=lambda: box.__setitem__("payload", server.wait(timeout=5)))
    waiter.start()
    try:
        page = urllib.request.urlopen(server.url, timeout=5).read().decode()
        assert "hello editor" in page

        di = CnDDataInstanceBuilder().build_instance({"a": 1})
        req = urllib.request.Request(
            server.url + "commit",
            data=json.dumps({"data_instance": di}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    finally:
        waiter.join(timeout=5)

    assert box["payload"] is not None
    assert "data_instance" in box["payload"]


def test_edit_server_wait_times_out_to_none():
    server = _EditServer("<html></html>")
    assert server.wait(timeout=0.2) is None


# ---------------------------------------------------------------------------
# Cancel decision + payload reification
# ---------------------------------------------------------------------------


def test_is_cancel():
    assert _is_cancel(None)
    assert _is_cancel({})
    assert _is_cancel({"cancelled": True})
    assert not _is_cancel({"data_instance": {"atoms": [], "relations": []}})


def test_reify_committed_round_trips_builtin():
    seed = {"nums": [1, 2, 3], "k": "v"}
    di = CnDDataInstanceBuilder().build_instance(seed)
    assert _reify_committed(dict, {"data_instance": di}, di) == seed


@dataclass
class P:
    x: int = 0
    y: int = 0


def test_reify_committed_rebuilds_dataclass():
    di = CnDDataInstanceBuilder().build_instance(P(3, 4))
    out = _reify_committed(P, {"data_instance": di}, di)
    assert isinstance(out, P) and out == P(3, 4)


# ---------------------------------------------------------------------------
# edit() — server + display monkeypatched out
# ---------------------------------------------------------------------------


class _FakeServer:
    def __init__(self, payload):
        self._payload = payload
        self.url = "http://127.0.0.1:0/"

    def wait(self, timeout=None):
        return self._payload


@pytest.fixture
def no_show(monkeypatch):
    monkeypatch.setattr(si, "_show", lambda url, height: None)


def _patch_server(monkeypatch, payload):
    monkeypatch.setattr(si, "_EditServer", lambda html: _FakeServer(payload))


def test_edit_commit_returns_reified(monkeypatch, no_show):
    seed = {"nums": [1, 2, 3]}
    di = CnDDataInstanceBuilder().build_instance(seed)
    _patch_server(monkeypatch, {"data_instance": di})
    assert si.edit(seed) == seed


def test_edit_cancel_default_none(monkeypatch, no_show):
    _patch_server(monkeypatch, {"cancelled": True})
    assert si.edit({"a": 1}) is None


def test_edit_cancel_seed_returns_original(monkeypatch, no_show):
    seed = {"a": 1}
    _patch_server(monkeypatch, None)  # timeout / closed tab
    assert si.edit(seed, on_cancel="seed") is seed


def test_edit_cancel_raise(monkeypatch, no_show):
    _patch_server(monkeypatch, {"cancelled": True})
    with pytest.raises(EditCancelled):
        si.edit({"a": 1}, on_cancel="raise")
