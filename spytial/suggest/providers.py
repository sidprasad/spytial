"""The provider slot for ``spytial.suggest`` enrichment.

Enrichment needs exactly one thing from a model: given a prompt and a JSON schema,
return the structured reply. So a **provider is a callable** ::

    (prompt: str, *, schema: dict) -> dict

Anything with that shape works — a bare function, a ``lambda``, or a class with
``__call__`` that carries config. ``suggest(obj, enrich=...)`` accepts:

* ``None`` — off (no enrichment).
* a model-id **string** — sugar for a named model in the ``llm`` library
  (:class:`LlmModel`); e.g. ``enrich="llama3.2"``, ``enrich="gpt-4o"``.
* any **callable** provider — for a subscription CLI, a raw API client, or a test
  stub. Built-ins: :class:`LlmModel`, :class:`ClaudeCode`, :class:`Codex`.

There is no ambient default: you always say *what* to enrich with. A provider is
free to raise on failure — the caller (``suggest`` / ``enrich_draft``) catches it
and degrades to the static draft with a note, so enrichment never crashes
``suggest()``.

Writing one is short. A backend with **native** JSON-schema output returns the
object directly; a text-only backend leans on the two helpers here::

    def my_provider(prompt, *, schema):
        text = call_some_model(instruct_json(prompt, schema))
        return extract_json(text)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Mapping, runtime_checkable

try:  # Protocol is stdlib on 3.8+.
    from typing import Protocol
except ImportError:  # pragma: no cover
    from typing_extensions import Protocol  # type: ignore


class EnrichError(RuntimeError):
    """A provider couldn't be built or a provider call failed.

    ``suggest`` catches this (and, at call time, any exception a provider raises)
    and records a note instead of propagating — enrichment is best-effort.
    """


@runtime_checkable
class EnrichProvider(Protocol):
    """The provider slot: a callable ``(prompt, *, schema) -> dict``.

    Implement it as a function or as a class with ``__call__``. The return value is
    a JSON object (mapping) conforming to ``schema`` — the model's structured reply.
    """

    def __call__(self, prompt: str, *, schema: Mapping[str, Any]) -> Mapping[str, Any]:
        ...


# --------------------------------------------------------------------------- #
# Helpers for text-only backends (no native structured-output mode).
# --------------------------------------------------------------------------- #


def instruct_json(prompt: str, schema: Mapping[str, Any]) -> str:
    """Append a strict "reply with only this JSON" instruction to ``prompt``.

    For backends without a native schema mode (e.g. ``claude -p``): pair it with
    :func:`extract_json` on the response.
    """
    return (
        f"{prompt}\n\n"
        "Respond with ONLY a single JSON object conforming to this JSON Schema. "
        "No prose, no explanation, no markdown code fence.\n\n"
        f"JSON Schema:\n{json.dumps(schema)}"
    )


def extract_json(text: str) -> dict:
    """Parse a JSON object out of model output, tolerating fences and stray prose.

    Tries the whole string first, then falls back to the first balanced ``{...}``.
    Raises :class:`EnrichError` if nothing parseable is found.
    """
    s = text.strip()
    if s.startswith("```"):  # ```json ... ``` or ``` ... ```
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Fall back to the first balanced object anywhere in the text.
    start = s.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(s)):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start : i + 1])
                    except json.JSONDecodeError:
                        break
    raise EnrichError(f"no JSON object found in model output: {text[:200]!r}")


# --------------------------------------------------------------------------- #
# Built-in providers.
# --------------------------------------------------------------------------- #


class LlmModel:
    """Provider backed by a *named* model in Simon Willison's ``llm`` library.

    ``enrich="llama3.2"`` / ``enrich="gpt-4o"`` resolve here. The id is explicit — no
    ``llm`` *default* model is ever consulted, so the same call enriches the same way
    everywhere. Raises :class:`EnrichError` if ``llm`` isn't installed or the id is
    unknown, so a typo fails loudly rather than silently doing nothing.
    """

    def __init__(self, model_id: str):
        try:
            import llm  # type: ignore
        except ImportError as exc:
            raise EnrichError(
                f'enrich="{model_id}" needs the optional llm library — install it '
                'with: pip install "spytial_diagramming[suggest-llm]" plus a provider '
                "plugin (e.g. llm-ollama for local models, or llm-anthropic)."
            ) from exc
        try:
            self._model = llm.get_model(model_id)
        except Exception as exc:  # noqa: BLE001 — llm.UnknownModelError et al.
            raise EnrichError(f'enrich="{model_id}": {exc}') from exc

    def __call__(self, prompt: str, *, schema: Mapping[str, Any]) -> Mapping[str, Any]:
        # llm has native schema support; it returns the JSON as text.
        return json.loads(self._model.prompt(prompt, schema=schema).text())


class ClaudeCode:
    """Provider backed by the Claude Code CLI (``claude -p``) — your subscription.

    Runs on Claude Code's auth (OAuth/subscription), so it needs no separate API key.
    ``claude`` has no native JSON-schema flag, so the schema is injected into the
    prompt and the reply is parsed with :func:`extract_json`.

    Individual, local use only: Claude Code's subscription token isn't licensed for
    multi-user or hosted services — use an API key (an :class:`LlmModel`) for those.
    """

    def __init__(self, model: str = "sonnet", *, bin: str = "claude", timeout: int = 120):
        self.model = model
        self.bin = bin
        self.timeout = timeout

    def __call__(self, prompt: str, *, schema: Mapping[str, Any]) -> Mapping[str, Any]:
        exe = shutil.which(self.bin) or self.bin
        proc = subprocess.run(
            [exe, "-p", "--model", self.model, instruct_json(prompt, schema)],
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if proc.returncode != 0:
            raise EnrichError(
                f"claude exited {proc.returncode}: {(proc.stderr or '').strip()[:300]}"
            )
        return extract_json(proc.stdout)


class Codex:
    """Provider backed by the OpenAI Codex CLI (``codex exec``) — your ChatGPT plan.

    Uses ``--output-schema`` for *native* JSON-schema-enforced output, so the reply
    conforms to ``schema`` by construction. Runs on your ChatGPT (Plus/Pro/…) sign-in.

    Individual, local use only — as with :class:`ClaudeCode`.
    """

    def __init__(self, model: str = "", *, bin: str = "codex", timeout: int = 120):
        self.model = model
        self.bin = bin
        self.timeout = timeout

    def __call__(self, prompt: str, *, schema: Mapping[str, Any]) -> Mapping[str, Any]:
        exe = shutil.which(self.bin) or self.bin
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(schema, f)
            cmd = [exe, "exec", "--output-schema", path]
            if self.model:
                cmd += ["--model", self.model]
            cmd.append(prompt)
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout
            )
        finally:
            os.unlink(path)
        if proc.returncode != 0:
            raise EnrichError(
                f"codex exited {proc.returncode}: {(proc.stderr or '').strip()[:300]}"
            )
        return extract_json(proc.stdout)


# --------------------------------------------------------------------------- #
# Resolution.
# --------------------------------------------------------------------------- #


def as_provider(spec: Any) -> EnrichProvider:
    """Resolve an ``enrich=`` value to a provider callable.

    A ``str`` is a named ``llm`` model id (wrapped in :class:`LlmModel`); any other
    callable is used as-is. Raises :class:`EnrichError` on anything else. ``None`` is
    handled by the caller (it means "no enrichment") and never reaches here.
    """
    if isinstance(spec, str):
        return LlmModel(spec)
    if callable(spec):
        return spec
    raise EnrichError(
        "enrich must be a model-id string or a callable provider "
        f"(prompt, *, schema) -> dict; got {type(spec).__name__}."
    )
