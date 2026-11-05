"""Token-gated, loopback-only UI for a live SuggestSession."""

import hmac
import http.server
import json
import os
from pathlib import Path
import secrets
import threading

from ..core_assets import browser_asset


class SessionServer:
    def __init__(self, session):
        self.session = session
        self.token = secrets.token_urlsafe(24)
        self.lock = threading.Lock()
        self.bundle = os.environ.get("SPYTIAL_BROWSER_BUNDLE")
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/{self.token}/"

    def state(self):
        return self.session._poll()

    def _handler(self):
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def route(self):
                token, _, route = self.path.lstrip("/").partition("/")
                host = self.headers.get("Host")
                if host != f"127.0.0.1:{server.port}" or not hmac.compare_digest(
                    token, server.token
                ):
                    return None
                return route

            def reply(self, body, content_type="application/json", status=200):
                if not isinstance(body, bytes):
                    body = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                route = self.route()
                try:
                    if route == "":
                        page = Path(__file__).with_name("_session.html").read_text()
                        import html

                        src = "core.js"
                        self.reply(
                            page.replace(
                                "__CORE_URL__", html.escape(src, quote=True)
                            ).encode(),
                            "text/html; charset=utf-8",
                        )
                    elif route == "core.js":
                        self.reply(
                            (
                                Path(server.bundle).read_bytes()
                                if server.bundle
                                else browser_asset("spytial-core-complete.global.js")
                            ),
                            "text/javascript",
                        )
                    elif route == "session.js":
                        self.reply(
                            Path(__file__).with_name("_session.js").read_bytes(),
                            "text/javascript; charset=utf-8",
                        )
                    elif route == "state":
                        with server.lock:
                            self.reply(server.state())
                    elif route == "history":
                        with server.session._operation_lock:
                            self.reply({"records": server.session.history})
                    else:
                        self.send_error(404)
                except Exception as exc:
                    self.reply({"error": str(exc)}, status=400)

            def do_POST(self):
                route = self.route()
                if route not in {
                    "vote",
                    "reclassify",
                    "done",
                    "resume",
                    "add-property",
                    "edit-property",
                }:
                    self.send_error(404)
                    return
                if self.headers.get("Origin") != f"http://127.0.0.1:{server.port}":
                    self.send_error(403)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > 50000:
                        raise ValueError("Invalid request size")
                    data = json.loads(self.rfile.read(length))
                    if not isinstance(data, dict):
                        raise ValueError("Expected an object")
                    with server.lock:
                        if route == "add-property":
                            prop = server.session.add_property(data.get("prompt"))
                            self.reply({"property_id": prop.id})
                        elif route == "edit-property":
                            prop = server.session.edit_property(
                                data.get("property_id"), data.get("prompt")
                            )
                            self.reply({"property_id": prop.id})
                        elif route == "done":
                            checkpoint = server.session.done()
                            self.reply(
                                {
                                    "status": checkpoint["status"],
                                    "message": checkpoint["message"],
                                }
                            )
                        elif route == "resume":
                            server.session.resume(data.get("property_id"))
                            self.reply({"resumed": True})
                        else:
                            if not data.get("question_id"):
                                raise ValueError("A question ID is required")
                            if route == "reclassify":
                                record = server.session.reclassify(
                                    data["question_id"],
                                    data.get("side"),
                                    data.get("value"),
                                )
                            else:
                                record = server.session.vote(
                                    data.get("side"),
                                    data.get("value"),
                                    question_id=data["question_id"],
                                    layout_state=data.get("layout_state"),
                                )
                            self.reply(
                                {"recorded": True, "complete": record["complete"]}
                            )
                except Exception as exc:
                    self.reply({"error": str(exc)}, status=400)

            def log_message(self, *args):
                pass

        return Handler

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
