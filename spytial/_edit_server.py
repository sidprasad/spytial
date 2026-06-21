"""Ephemeral localhost server backing :func:`spytial.edit` (v1: local script + local Jupyter).

The page is served at ``/``; the Done / Cancel buttons in ``input_template.html``
POST the current data instance (or ``{"cancelled": true}``) to ``/commit``. The
server runs on a daemon thread so the *calling* thread can block on
:meth:`_EditServer.wait` — which is what lets :func:`spytial.edit` be a plain
synchronous call in both a script and a (local) notebook cell without starving
the served page.
"""

import http.server
import json
import threading
from typing import Optional


class _EditServer:
    """Serve one editor page on ``127.0.0.1:<ephemeral-port>`` and block until commit."""

    def __init__(self, html: str):
        self._html = html.encode("utf-8")
        self.payload: Optional[dict] = None
        self._done = threading.Event()
        self._httpd = http.server.HTTPServer(("127.0.0.1", 0), self._make_handler())
        self.port: int = self._httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def _make_handler(self):
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/":
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(server._html)))
                self.end_headers()
                self.wfile.write(server._html)

            def do_POST(self):
                if self.path != "/commit":
                    self.send_error(404)
                    return
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    server.payload = json.loads(raw)
                except json.JSONDecodeError:
                    server.payload = {"cancelled": True}
                self.send_response(204)
                self.end_headers()
                server._done.set()

            def log_message(self, *args):  # silence default stderr logging
                pass

        return Handler

    def wait(self, timeout: Optional[float] = None) -> Optional[dict]:
        """Serve in the background and block the caller until commit (or timeout / interrupt).

        Returns the committed payload dict, or ``None`` on timeout / ``KeyboardInterrupt``.
        """
        thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        thread.start()
        try:
            self._done.wait(timeout)
        except KeyboardInterrupt:
            pass  # Ctrl-C / interrupt kernel == cancel
        finally:
            self._httpd.shutdown()
            self._httpd.server_close()
        return self.payload
