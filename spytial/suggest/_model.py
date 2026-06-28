"""Data model for ``spytial.suggest``.

These are plain, dependency-free containers shared across the introspection,
rule, and emit stages. Keeping them here (rather than threading dicts around)
makes each stage independently testable and gives heuristics a stable contract.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field as _dc_field
from typing import Any, Dict, List, Optional


# Confidence ranking used for conflict resolution (higher wins).
_CONF_RANK = {"high": 3, "medium": 2, "low": 1}


@dataclass
class FieldInfo:
    """Everything the analyzer learned about a single field of a class."""

    name: str
    type_repr: Optional[str] = None  # annotation as a string, e.g. "Optional[TreeNode]"
    is_self_ref: bool = False  # type (or container element) is a node-like type
    container: Optional[str] = None  # None | 'list' | 'dict' | 'set' | 'tuple'
    is_scalar: bool = False  # int/float/str/bool/bytes/Decimal
    enum_members: Optional[List[str]] = None
    has_none_default: bool = False
    is_private: bool = False  # leading underscore (read, but never emits a directive)
    is_nested_container: bool = False  # a container of containers (e.g. a matrix)
    source: str = "unknown"  # 'dataclass' | 'annotations' | 'init_ast' | 'instance'


@dataclass
class ClassInfo:
    """A class and its discovered fields; passed to class-scope heuristics."""

    cls: type
    fields: List[FieldInfo] = _dc_field(default_factory=list)

    @property
    def self_ref_fields(self) -> List[str]:
        """Names of fields that point back to a node-like type."""
        return [f.name for f in self.fields if f.is_self_ref]

    def get(self, name: str) -> Optional[FieldInfo]:
        for f in self.fields:
            if f.name == name:
                return f
        return None


@dataclass
class Suggestion:
    """One proposed directive, with the reasoning that produced it."""

    directive: str  # 'orientation', 'attribute', ...
    kwargs: Dict[str, Any]
    confidence: str = "medium"  # 'high' | 'medium' | 'low'
    rationale: str = ""  # human-readable "why" — teaches the directive language
    source_field: Optional[str] = None
    enabled_by_default: Optional[bool] = None
    source: str = "rule"  # 'rule' (deterministic) | 'llm' (model-enriched value)

    def __post_init__(self) -> None:
        if self.enabled_by_default is None:
            self.enabled_by_default = self.confidence == "high"

    @property
    def rank(self) -> int:
        return _CONF_RANK.get(self.confidence, 0)

    def dedup_key(self) -> str:
        """Identity for de-duplication: same directive + same kwargs."""
        return (
            self.directive + "::" + json.dumps(self.kwargs, sort_keys=True, default=str)
        )


class SpecDraft:
    """The result of :func:`spytial.suggest.suggest`.

    Holds the proposed directives plus the conflict "losers" (alternatives) and
    any informational notes, and knows how to render itself four ways.
    """

    def __init__(
        self,
        cls: type,
        suggestions: List[Suggestion],
        alternatives: Optional[List[Suggestion]] = None,
        notes: Optional[List[str]] = None,
    ) -> None:
        self.cls = cls
        self.suggestions = suggestions
        self.alternatives = alternatives or []
        self.notes = notes or []

    def enabled(self) -> List[Suggestion]:
        return [s for s in self.suggestions if s.enabled_by_default]

    # --- rendering (lazy imports avoid an import cycle with emit/_html) ---

    def to_source(self, enabled_only: bool = True, with_comments: bool = True) -> str:
        """A paste-able stack of ``@spytial.*`` decorators."""
        from .emit import to_source

        return to_source(self, enabled_only=enabled_only, with_comments=with_comments)

    def to_registry(self, enabled_only: bool = True) -> Dict[str, list]:
        """The ``{"constraints": [...], "directives": [...]}`` registry dict."""
        from .emit import to_registry

        return to_registry(self, enabled_only=enabled_only)

    def apply(self, enabled_only: bool = True) -> type:
        """Decorate the class live with the enabled suggestions; returns the class."""
        from .emit import apply

        return apply(self, enabled_only=enabled_only)

    def _repr_html_(self) -> str:  # noqa: N802 (Jupyter protocol)
        from ._html import render_html

        return render_html(self)

    def __repr__(self) -> str:
        n = len(self.enabled())
        extra = f", {len(self.alternatives)} alt" if self.alternatives else ""
        return (
            f"<SpecDraft {self.cls.__name__}: {n} directive(s){extra}; "
            f"call .to_source() or .apply()>"
        )
