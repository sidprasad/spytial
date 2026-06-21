"""Ephemeral localhost server backing :func:`spytial.edit` (v1: local script + local Jupyter).

The page is served at ``/<token>/`` on ``127.0.0.1:<ephemeral-port>``. The
Done / Cancel buttons in ``input_template.html`` POST the current data instance
(or ``{"cancelled": true}``) to ``/<token>/commit``; the page also heartbeats
``/<token>/heartbeat`` so the Python side can tell a *live* page from a dead one.

Design notes:

* **Token** — a per-session ``secrets.token_urlsafe`` gates every request. Without
  it, any local process (or any web page open in the user's browser) could POST a
  forged data instance that :func:`reify` would turn into a Python object in the
  user's process. A cross-origin attacker can't read the served HTML, so it can't
  learn the token; blind requests 404.
* **Liveness** — :meth:`wait` blocks the *calling* thread but watches three
  deadlines so it can never hang forever against a dead page: ``connect_timeout``
  (page never made contact — e.g. an unreachable iframe in a hosted notebook),
  ``idle_timeout`` (heartbeats stopped — tab closed), and the caller's overall
  ``timeout``. The server itself runs on a daemon thread.
"""

import hmac
import http.server
import json
import secrets
import threading
import time
from typing import Optional

_MAX_BODY = 1_000_000  # 1 MB cap on a committed data instance


class _EditServer:
    """Serve one token-gated editor page and block until commit / cancel / death."""

    def __init__(self, html: str):
        self._html = html.encode("utf-8")
        self.token = secrets.token_urlsafe(16)
        self.payload: Optional[dict] = None
        self._done = threading.Event()
        self._commit_lock = threading.Lock()
        self._connected = threading.Event()
        self._last_seen: Optional[float] = None
        self._httpd = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), self._make_handler()
        )
        self.port: int = self._httpd.server_address[1]

    @property
    def url(self) -> str:
        # Trailing slash matters: it makes the page's relative fetch('commit') /
        # fetch('heartbeat') resolve under /<token>/.
        return f"http://127.0.0.1:{self.port}/{self.token}/"

    @property
    def _origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def _touch(self) -> None:
        self._last_seen = time.monotonic()
        self._connected.set()

    def _make_handler(self):
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _route(self):
                """Return the path segment after a valid token, or ``None`` if the token is wrong."""
                seg, _, rest = self.path.lstrip("/").partition("/")
                if not hmac.compare_digest(seg, server.token):
                    return None
                return rest

            def _bad_origin(self) -> bool:
                origin = self.headers.get("Origin")
                return origin is not None and origin != server._origin

            def do_GET(self):
                rest = self._route()
                if rest is None:
                    self.send_error(404)
                    return
                if rest == "heartbeat":
                    server._touch()
                    self.send_response(204)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if rest != "":
                    self.send_error(404)
                    return
                server._touch()  # first page GET == "connected"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(server._html)))
                self.end_headers()
                self.wfile.write(server._html)

            def do_POST(self):
                if self._route() != "commit":
                    self.send_error(404)
                    return
                if self._bad_origin():
                    self.send_error(403)
                    return
                try:
                    length = int(self.headers.get("Content-Length", 0))
                except ValueError:
                    self.send_error(400)
                    return
                if length < 0 or length > _MAX_BODY:
                    self.send_error(413)
                    return
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    # A garbled commit is an error, NOT a silent cancel: leave
                    # _done unset and let the liveness loop decide.
                    self.send_error(400)
                    return
                if not isinstance(data, dict):
                    self.send_error(400)
                    return
                self.send_response(204)  # respond before unblocking, so the
                self.end_headers()       # browser gets its reply before shutdown
                # First writer wins: a pagehide cancel beacon racing an in-flight
                # Done POST must not clobber the real committed payload.
                with server._commit_lock:
                    if not server._done.is_set():
                        server.payload = data
                        server._done.set()

            def log_message(self, *args):  # silence default stderr logging
                pass

        return Handler

    def wait(
        self,
        timeout: Optional[float] = None,
        *,
        connect_timeout: float = 20.0,
        idle_timeout: float = 10.0,
        poll: float = 0.25,
    ) -> Optional[dict]:
        """Serve in the background and block the caller until one of three outcomes.

        Returns:
            * the committed payload dict (a ``/commit`` POST landed), or
            * ``{"disconnected": True, "reason": "never-connected" | "page-closed"
              | "timeout"}`` if the page never made contact / stopped beating /
              the overall ``timeout`` elapsed, or
            * ``None`` on ``KeyboardInterrupt`` (treated as cancel).

        The ``finally`` always shuts the server down, so no socket leaks on any path.
        """
        if self._httpd is None:
            raise RuntimeError("_EditServer.wait() is single-use")
        thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        thread.start()
        start = time.monotonic()
        try:
            while True:
                if self._done.wait(poll):
                    return self.payload
                now = time.monotonic()
                if timeout is not None and now - start > timeout:
                    return {"disconnected": True, "reason": "timeout"}
                if not self._connected.is_set():
                    if now - start > connect_timeout:
                        return {"disconnected": True, "reason": "never-connected"}
                elif now - (self._last_seen or start) > idle_timeout:
                    return {"disconnected": True, "reason": "page-closed"}
        except KeyboardInterrupt:
            return None
        finally:
            self.close()

    def close(self) -> None:
        """Shut the server down and free the socket. Idempotent; guards each step."""
        httpd, self._httpd = self._httpd, None
        if httpd is None:
            return
        try:
            httpd.shutdown()
        except Exception:
            pass
        try:
            httpd.server_close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
