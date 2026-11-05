"""One supervised Node worker per session; no layout or search policy here."""

import atexit
from collections import deque
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import weakref

from . import _eval


_workers = weakref.WeakSet()


def _shutdown():
    for worker in list(_workers):
        worker.close()


atexit.register(_shutdown)


def _read_output(stream, output):
    try:
        for line in stream:
            output.put(line)
    finally:
        output.put(None)


def _read_errors(stream, errors):
    for line in stream:
        errors.append(line[-1000:])


class CoreRuntime:
    def __init__(self):
        self._process = None
        self._directory = None
        self._lock = threading.Lock()
        _workers.add(self)

    def _start(self):
        from .._conformance import _harness_bin

        node, checker, core_env = (
            _eval._node_bin(),
            _harness_bin(),
            _eval._resolve_core(),
        )
        if not node or not checker or core_env is None:
            raise RuntimeError("Core checks need Node and the bundled core assets.")
        self._directory = tempfile.TemporaryDirectory(prefix="spytial-check-")
        self._output, self._errors = queue.Queue(), deque(maxlen=8)
        try:
            self._process = subprocess.Popen(
                [
                    node,
                    str(Path(__file__).with_name("_worker.js")),
                    checker,
                    self._directory.name,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env={**os.environ, **core_env},
            )
        except Exception:
            self._stop()
            raise
        threading.Thread(
            target=_read_output, args=(self._process.stdout, self._output), daemon=True
        ).start()
        threading.Thread(
            target=_read_errors, args=(self._process.stderr, self._errors), daemon=True
        ).start()

    def request(self, payload, *, timeout=20):
        with self._lock:
            if self._process is None:
                self._start()
            try:
                self._process.stdin.write(json.dumps(payload, allow_nan=False) + "\n")
                self._process.stdin.flush()
                line = self._output.get(timeout=timeout)
                if line is None:
                    raise RuntimeError("Core worker stopped: " + "".join(self._errors))
                response = json.loads(line)
                if not response.get("ok"):
                    raise RuntimeError(
                        "Core worker failed: " + str(response.get("error"))
                    )
                return response["value"]
            except queue.Empty as exc:
                self._stop()
                raise RuntimeError(f"Core check exceeded {timeout} seconds.") from exc
            except Exception:
                self._stop()
                raise

    def run_cases(self, cases, *, timeout=20):
        from .._conformance import _validate_result

        documents = list(cases)
        result = self.request({"kind": "check", "cases": documents}, timeout=timeout)
        return _validate_result(documents, result)

    def evaluate_selectors(self, datum, selectors):
        if not selectors:
            return []
        result = self.request(
            {"kind": "selectors", "datum": datum, "selectors": selectors}
        )
        return _eval._decode_result(result)

    def _stop(self):
        if self._process is not None:
            process, self._process = self._process, None
            if process.poll() is None:
                process.kill()
            process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
        if self._directory is not None:
            self._directory.cleanup()
            self._directory = None

    def close(self):
        with self._lock:
            self._stop()

    def __del__(self):
        self.close()
