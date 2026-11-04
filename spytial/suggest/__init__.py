"""Develop diagramming rules through proposals, examples, and human critique.

``suggest(Cls, rules=[...])`` starts the combined LLM/Hypothesis session.
``suggest_draft(Cls)`` explicitly selects the old one-shot draft builder.
Optional model and search dependencies are loaded only when used.
"""

from __future__ import annotations

import sys as _sys
import types as _types
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._session import SuggestSession

from . import rules  # noqa: F401  (import for the side effect of registering built-ins)
from ._ask import AskError
from ._model import ClassInfo, FieldInfo, SpecDraft, Suggestion
from .introspect import build_class_info
from .providers import (
    ClaudeCode,
    Codex,
    EnrichError,
    EnrichProvider,
    LlmModel,
    as_provider,
)
from .registry import DEFAULT_REGISTRY, HeuristicRegistry, build_draft, heuristic

__all__ = [
    "suggest",
    "suggest_draft",
    "ExampleSearch",
    "HypothesisSearch",
    "FixedExamples",
    "FixedProposals",
    "heuristic",
    "HeuristicRegistry",
    "DEFAULT_REGISTRY",
    "Suggestion",
    "SpecDraft",
    "FieldInfo",
    "ClassInfo",
    "build_class_info",
    "EnrichProvider",
    "EnrichError",
    "AskError",
    "LlmModel",
    "ClaudeCode",
    "Codex",
    "SuggestSession",
]


from ._draft import suggest_draft
from ._search import ExampleSearch, FixedExamples, HypothesisSearch
from ._proposals import FixedProposals


def suggest(
    target,
    *,
    rules=None,
    examples=None,
    instance=None,
    proposer=None,
    search=None,
    strategy=None,
    registry=None,
    max_examples=20,
    elimination_threshold=2,
    min_positive_votes=1,
    max_candidates=4,
) -> "SuggestSession":
    """Start a critique session over complete candidate Spytial programs.

    ``target`` is a class or example object; ``rules`` is an optional list of
    ordinary-language requests. Fixed ``examples`` supplement generated data.

    The default proposer is ``Codex()``. Replace it with a provider callable
    ``(prompt, *, schema) -> dict``, a model-id string, or ``FixedProposals``.
    The default search is ``HypothesisSearch(strategy or 'auto')``; ``strategy``
    is a convenience for supplying a domain-specific Hypothesis strategy.
    Alternatively supply an ``ExampleSearch`` implementation, including
    ``FixedExamples()`` to search only the supplied examples. Missing dependencies
    and provider failures appear in the view and raise from ``wait()``; they
    never silently select another workflow.

    ``max_examples`` bounds each generated search, not the whole session. Checks
    are evidence on sampled data, never proofs. Use ``show()`` or display the
    session in a local notebook. Startup runs in the background so the view
    opens immediately. ``wait()`` waits explicitly before inspecting attributes;
    ``next()``, ``vote()``, ``revise()``, and ``finish()`` wait automatically.
    Each image has independent upvote/downvote/unsure judgments. PICK uses
    ``elimination_threshold=2`` negative votes and ``min_positive_votes=1``
    positive vote. ``max_candidates=4`` caps each proposal batch, including repair.
    Definite programmatic votes require the displayed ``layout_state``.
    ``revise()`` replays history; ``finish()`` exports the supported, consistent
    conjunction without applying it. ``done()`` checkpoints any result;
    ``resume()`` continues. ``save()`` / ``SuggestSession.load()`` persist the loop.
    """
    from ._session import SuggestSession

    return SuggestSession(
        target,
        rules=rules,
        examples=examples,
        instance=instance,
        proposer=proposer,
        search=search,
        strategy=strategy,
        registry=registry,
        max_examples=max_examples,
        elimination_threshold=elimination_threshold,
        min_positive_votes=min_positive_votes,
        max_candidates=max_candidates,
    )


class _CallableModule(_types.ModuleType):
    """Support both ``spytial.suggest(...)`` and subpackage imports."""

    def __call__(self, *args, **kwargs):
        return suggest(*args, **kwargs)


_sys.modules[__name__].__class__ = _CallableModule


def __getattr__(name):
    if name == "SuggestSession":
        from ._session import SuggestSession

        return SuggestSession
    raise AttributeError(name)
