"""Develop diagramming rules through proposals, examples, and human critique.

``suggest(Cls)`` prepares data. Type a requirement in the session to start a round.
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
from ._living import LivingSpec
from ..annotations import SpecUnavailableError
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
    "LivingSpec",
    "SpecUnavailableError",
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
    "Requirement",
]


from ._draft import suggest_draft
from ._search import ExampleSearch, FixedExamples, HypothesisSearch
from ._proposals import FixedProposals
from ._requirement import Requirement


def suggest(
    target,
    *,
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
    """Prepare an interactive specification from examples and/or a generator.

    The first diagram has no inferred rules. Pass ``registry=DEFAULT_REGISTRY``
    to include fixed presentation rules such as attributes and hidden atoms.
    Display the session and enter a requirement such as "Parents above children"
    in the prompt. Select Explore to ask the model for candidate interpretations.
    Both diagrams retain every other accepted requirement; votes judge only the
    current requirement.

    Upvotes support candidates permitting the arrangement and count against
    those excluding it. Downvotes count against candidates permitting it. Unsure
    supplies no evidence. Thresholds default to two negative votes for elimination
    and one positive vote for support. Duplicate evidence counts once per requirement.
    A sole survivor is automatically accepted after a completed pair only when
    supported, consistent with its requirement's evidence, and feasible together
    with accepted requirements. Search exhaustion never establishes equivalence.

    ``done()`` combines all supported survivors, requiring shared positive support,
    agreement with this requirement's judgments, and feasibility with accepted rules.
    It saves an unfinished round when these checks fail.
    Unreviewed and eliminated candidates contribute no rules.
    Revising a prompt replaces its candidates, withdraws its old definition, and
    replays its history. Other accepted requirements remain active. Select Continue
    to revisit the existing candidates. Historical corrections can withdraw an
    accepted definition.

    ``session.spec`` is a stable handle to accepted requirements. ``apply()`` binds
    it to the class; later ``diagram`` calls read its current rules. Existing
    diagrams stay fixed. No accepted requirement, or conflicting accepted requirements,
    makes live use raise ``SpecUnavailableError``. An unresolved new requirement does
    not prevent using already accepted requirements. ``close()`` stops controls;
    the supported spec remains usable. ``save()`` / ``load()`` preserve requirements,
    revisions, datums, arrangements, and scoped votes in format version 3.

    The default proposer is ``Codex()``; use a provider callable, model-id string,
    or ``FixedProposals`` to replace it. Search defaults to ``HypothesisSearch``;
    ``strategy=`` supplies its source and ``max_examples`` bounds each invocation.
    ``FixedExamples`` disables generated search. Core checks sampled data; they
    are not proofs. Startup is asynchronous; ``wait()`` waits explicitly.
    """
    from ._session import SuggestSession

    return SuggestSession(
        target,
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
