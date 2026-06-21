"""Tests for the server-backed ``spytial.edit()`` flow and its hardening.

``edit()`` blocks on a browser interaction, so it can't be called live in CI.
These drive ``_EditServer`` over the loopback socket (token gating, body limits,
the three liveness outcomes) and exercise the pure helpers + ``edit()`` policy
with the server/display monkeypatched — no browser, no real kernel.
"""

import http.client
import json
import threading
import time
from dataclasses import dataclass

import pytest

import spytial.structured_input as si
import spytial.utils as su
from spytial.structured_input import (
    _EditServer,
    _is_cancel,
    _reify_committed,
    EditCancelled,
)
from spytial.provider_system import CnDDataInstanceBuilder


# ---------------------------------------------------------------------------
# loopback helpers
# ---------------------------------------------------------------------------


def _di(value={"a": 1}):
    return CnDDataInstanceBuilder().build_instance(value)


def _request(server, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=3)
    conn.request(method, path, body=body, headers=headers or {})
    resp = conn.getresponse()
    payload = resp.read()
    conn.close()
    return resp.status, payload


def _tok(server, rest=""):
    return f"/{server.token}/{rest}"


def _serve_in_thread(server, **wait_kw):
    """Run server.wait() in a daemon thread; return (thread, box) where box['r'] is the result."""
    box = {}
    t = threading.Thread(
        target=lambda: box.__setitem__("r", server.wait(**wait_kw)), daemon=True
    )
    t.start()
    time.sleep(0.1)  # let serve_forever spin up
    return t, box


# ---------------------------------------------------------------------------
# M1 — token gating + Origin check
# ---------------------------------------------------------------------------


def test_token_gating():
    server = _EditServer("<html><body>hello editor</body></html>")
    t, box = _serve_in_thread(server, connect_timeout=3, idle_timeout=3, poll=0.05)
    try:
        assert _request(server, "GET", "/")[0] == 404            # no token
        assert _request(server, "GET", "/wrongtoken/")[0] == 404  # wrong token
        status, body = _request(server, "GET", _tok(server))
        assert status == 200 and b"hello editor" in body         # right token
        assert _request(server, "POST", "/wrong/commit", b"{}")[0] == 404
        # foreign Origin is rejected even with the right token path
        assert _request(
            server, "POST", _tok(server, "commit"), b'{"cancelled":true}',
            {"Content-Type": "application/json", "Origin": "http://evil.example"},
        )[0] == 403
        # valid commit ends wait()
        assert _request(server, "POST", _tok(server, "commit"), b'{"cancelled":true}',
                        {"Content-Type": "application/json"})[0] == 204
    finally:
        t.join(timeout=3)
    assert box["r"] == {"cancelled": True}
    assert server._httpd is None  # cleaned up


# ---------------------------------------------------------------------------
# M5 — body hardening (no fabricated cancel)
# ---------------------------------------------------------------------------


def test_malformed_json_is_400_not_a_fake_cancel():
    server = _EditServer("<html></html>")
    t, box = _serve_in_thread(server, connect_timeout=3, idle_timeout=3, poll=0.05)
    try:
        assert _request(server, "POST", _tok(server, "commit"), b"{not json",
                        {"Content-Type": "application/json"})[0] == 400
        assert not server._done.is_set()        # did NOT unblock
        assert server.payload is None            # did NOT fabricate {"cancelled": True}
        _request(server, "POST", _tok(server, "commit"), b'{"cancelled":true}',
                 {"Content-Type": "application/json"})
    finally:
        t.join(timeout=3)


def test_oversize_body_is_413_without_reading_it():
    server = _EditServer("<html></html>")
    t, box = _serve_in_thread(server, connect_timeout=3, idle_timeout=3, poll=0.05)
    try:
        # Declare a huge Content-Length with a tiny body: the server must reject
        # on the header (the DoS guard) before reading the body.
        assert _request(server, "POST", _tok(server, "commit"), b"{}",
                        {"Content-Type": "application/json", "Content-Length": "2000000"})[0] == 413
        assert not server._done.is_set()
        _request(server, "POST", _tok(server, "commit"), b'{"cancelled":true}',
                 {"Content-Type": "application/json"})
    finally:
        t.join(timeout=3)


# ---------------------------------------------------------------------------
# M2 / §4 — the three liveness outcomes
# ---------------------------------------------------------------------------


def test_liveness_committed():
    server = _EditServer("<html>hi</html>")
    t, box = _serve_in_thread(server, connect_timeout=2, idle_timeout=2, poll=0.05)
    try:
        _request(server, "GET", _tok(server))  # connect
        _request(server, "POST", _tok(server, "commit"),
                 json.dumps({"data_instance": _di()}).encode(),
                 {"Content-Type": "application/json"})
    finally:
        t.join(timeout=3)
    assert "data_instance" in box["r"]
    assert server._httpd is None


def test_liveness_never_connected():
    server = _EditServer("<html></html>")
    # No client ever contacts it → connect-timeout fires.
    r = server.wait(connect_timeout=0.4, idle_timeout=0.4, poll=0.05)
    assert r == {"disconnected": True, "reason": "never-connected"}
    assert server._httpd is None


def test_liveness_page_closed():
    server = _EditServer("<html></html>")
    t, box = _serve_in_thread(server, connect_timeout=2, idle_timeout=0.4, poll=0.05)
    try:
        _request(server, "GET", _tok(server))            # connect
        _request(server, "GET", _tok(server, "heartbeat"))  # one beat, then stop
    finally:
        t.join(timeout=3)
    assert box["r"]["reason"] == "page-closed"


def test_liveness_overall_timeout():
    server = _EditServer("<html></html>")
    t, box = _serve_in_thread(server, timeout=0.4, connect_timeout=3, idle_timeout=3, poll=0.05)
    try:
        _request(server, "GET", _tok(server))  # connect so it's not 'never-connected'
    finally:
        t.join(timeout=3)
    assert box["r"]["reason"] == "timeout"


def test_wait_is_single_use():
    server = _EditServer("<html></html>")
    server.wait(connect_timeout=0.2, idle_timeout=0.2, poll=0.05)
    with pytest.raises(RuntimeError):
        server.wait(connect_timeout=0.2)


# ---------------------------------------------------------------------------
# M3 — cancel/commit classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", [
    None, {}, {"cancelled": True}, {"disconnected": True, "reason": "x"},
    {"data_instance": None}, {"data_instance": {}}, {"data_instance": {"atoms": []}},
    {"data_instance": {"relations": []}},  # missing atoms
])
def test_is_cancel_true(payload):
    assert _is_cancel(payload)


def test_is_cancel_false_for_real_commit():
    assert not _is_cancel({"data_instance": {"atoms": [{"id": "a0"}], "relations": []}})


# ---------------------------------------------------------------------------
# M4 — root handling on a structurally-edited commit
# ---------------------------------------------------------------------------


def test_reify_committed_round_trips_builtin():
    seed = {"nums": [1, 2, 3], "k": "v"}
    di = _di(seed)
    assert _reify_committed(dict, {"data_instance": di}, di) == seed


@dataclass
class P:
    x: int = 0
    y: int = 0


def test_reify_committed_rebuilds_dataclass():
    di = _di(P(3, 4))
    assert _reify_committed(P, {"data_instance": di}, di) == P(3, 4)


def test_reify_committed_tolerates_missing_relations():
    # The editor's getDataInstance() may drop an empty relations list; reify()
    # requires the key, so _reify_committed must normalize rather than crash.
    di = _di(5)  # a primitive: relations is legitimately empty
    assert di["relations"] == []
    di.pop("relations")
    assert _reify_committed(int, {"data_instance": di}, di) == 5


def test_reify_committed_ignores_stale_initial_root_when_gone():
    # The initial root atom is absent from the committed instance (structural
    # re-root). _reify_committed must NOT force the stale root; it falls through.
    di = _di({"nums": [1, 2, 3]})
    initial = {"rootId": "atom-that-no-longer-exists"}
    out = _reify_committed(dict, {"data_instance": di}, initial)
    assert out == {"nums": [1, 2, 3]}  # reconstructed via topology, no crash


# ---------------------------------------------------------------------------
# edit() — policy, validation, env gating (server + display monkeypatched)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Template hardening (Codex review): commit-race + non-dataclass export
# ---------------------------------------------------------------------------


def test_template_commit_js_is_unload_safe():
    from spytial.structured_input import _generate_editor_html

    html = _generate_editor_html({"atoms": [], "relations": []}, "c: []\n", "X", commit=True)
    # Done survives a tab close, and a commit-in-flight suppresses the pagehide cancel.
    assert "keepalive: true" in html
    assert "if (committed)" in html


def test_template_export_is_reify_based_for_builtins():
    from spytial.structured_input import _generate_editor_html

    html = _generate_editor_html({"atoms": [], "relations": []}, "c: []\n", "dict", commit=False)
    # Builtin seeds get a general, valid spytial.reify() snippet — not list(idx=0,...).
    assert "spytial.reify(json.loads" in html
    assert "BUILTIN" in html


class _FakeServer:
    def __init__(self, payload):
        self._payload = payload
        self.url = "http://127.0.0.1:0/tok/"

    def wait(self, timeout=None, **kw):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def no_show(monkeypatch):
    monkeypatch.setattr(si, "_show", lambda url, height: None)
    monkeypatch.setattr(si, "_announce_editing", lambda url: None)


def _patch_server(monkeypatch, payload):
    monkeypatch.setattr(si, "_EditServer", lambda html: _FakeServer(payload))


def test_edit_validates_on_cancel_before_anything(monkeypatch):
    # Must raise before constructing a server.
    monkeypatch.setattr(si, "_EditServer", lambda html: pytest.fail("server built"))
    with pytest.raises(ValueError, match="on_cancel"):
        si.edit({"a": 1}, on_cancel="nope")


def test_edit_commit_returns_reified(monkeypatch, no_show):
    seed = {"nums": [1, 2, 3]}
    _patch_server(monkeypatch, {"data_instance": _di(seed)})
    assert si.edit(seed) == seed


def test_edit_cancel_default_seed(monkeypatch, no_show):
    seed = {"a": 1}
    _patch_server(monkeypatch, {"cancelled": True})
    assert si.edit(seed) is seed  # default on_cancel="seed"


def test_edit_cancel_none(monkeypatch, no_show):
    _patch_server(monkeypatch, {"cancelled": True})
    assert si.edit({"a": 1}, on_cancel="none") is None


def test_edit_cancel_raise(monkeypatch, no_show):
    _patch_server(monkeypatch, None)  # KeyboardInterrupt path
    with pytest.raises(EditCancelled):
        si.edit({"a": 1}, on_cancel="raise")


def test_edit_disconnect_notes_reason(monkeypatch, no_show, capsys):
    _patch_server(monkeypatch, {"disconnected": True, "reason": "never-connected"})
    seed = {"a": 1}
    assert si.edit(seed, on_cancel="seed") is seed
    assert "never connected" in capsys.readouterr().err


def test_edit_reify_failure_degrades_to_on_cancel(monkeypatch, no_show, capsys):
    # A commit that can't be reconstructed must not crash the caller's kernel.
    seed = {"a": 1}
    _patch_server(monkeypatch, {"data_instance": _di(seed)})

    def _boom(*a, **k):
        raise RuntimeError("bad instance")

    monkeypatch.setattr(si, "_reify_committed", _boom)
    assert si.edit(seed, on_cancel="seed") is seed
    assert "couldn't reconstruct" in capsys.readouterr().err


@pytest.mark.parametrize("env", ["pyodide", "remote"])
def test_edit_unsupported_env_falls_back_to_edit_html(monkeypatch, env):
    monkeypatch.setattr(su, "edit_environment", lambda: env)
    monkeypatch.setattr(si, "_EditServer", lambda html: pytest.fail("server must not be built"))
    calls = {}
    monkeypatch.setattr(si, "edit_html", lambda inst, **k: calls.setdefault("inst", inst))
    assert si.edit({"a": 1}) is None
    assert calls["inst"] == {"a": 1}
