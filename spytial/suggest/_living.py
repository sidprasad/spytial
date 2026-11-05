"""A stable, usable reference to a session's evolving specification."""

from ..annotations import LIVE_SPEC_ATTR, SpecUnavailableError
from .emit import _selected


class LivingSpec:
    """Read the latest supported spec without copying or accumulating decorators.

    ``session.spec`` always returns the same object. ``apply()`` connects it to
    the target class; subsequent diagrams resolve its current rules. Explicit
    ``diagram(obj, spec=spec)`` calls need no class binding. ``snapshot()`` makes
    an independent editable draft when a fixed version is wanted.
    """

    def __init__(self, session):
        self._session = session

    @property
    def cls(self):
        return self._session.cls

    @property
    def result(self):
        """Current status, contributing candidates, support, and conflicts."""
        self._session.wait()
        with self._session._operation_lock:
            return self._session._resolve(generated=True)[0]

    @property
    def status(self):
        return self.result["status"]

    def snapshot(self):
        """Return a supported, checked draft without pausing the session."""
        return self._explained()[0]

    @property
    def provenance(self):
        """Each emitted rule and the accepted prompts/interpretations supporting it."""
        return self._explained()[1]

    def _explained(self):
        self._session.wait()
        with self._session._operation_lock:
            result, draft = self._session._resolve(generated=True)
            if result["status"] != "supported":
                raise SpecUnavailableError(result["message"])
            presentation = {
                s.dedup_key() for s in self._session._presentation.enabled()
            }
            sources = {}
            for requirement in self._session._requirements:
                for candidate in requirement.accepted:
                    for suggestion in candidate.draft.enabled():
                        key = suggestion.dedup_key()
                        if key not in presentation:
                            sources.setdefault(key, []).append(
                                {
                                    "requirement_id": requirement.id,
                                    "prompt": requirement.prompt,
                                    "revision": requirement.revision,
                                    "candidate_id": candidate.id,
                                    "interpretation": candidate.summary,
                                    "prompt_fragments": list(
                                        candidate.prompt_fragments.get(
                                            key, [requirement.prompt]
                                        )
                                    ),
                                }
                            )
            provenance = []
            for suggestion in _selected(draft, True):
                origins = sources.get(suggestion.dedup_key(), [])
                suggestion.rationale = (
                    "; ".join(
                        f"Requirement {source['prompt']!r} (revision {source['revision']}): "
                        f"{source['interpretation']!r}"
                        + (
                            f"; words {source['prompt_fragments']!r}"
                            if source["prompt_fragments"] != [source["prompt"]]
                            else ""
                        )
                        for source in origins
                    )
                    if origins
                    else "Presentation inferred from Python data"
                )
                provenance.append(
                    {
                        "rule": {
                            suggestion.directive: (
                                suggestion.kwargs.get("name")
                                if suggestion.directive == "flag"
                                else dict(suggestion.kwargs)
                            )
                        },
                        "origin": "requirement" if origins else "presentation",
                        "sources": origins,
                    }
                )
            return draft, provenance

    def to_registry(self):
        return self.snapshot().to_registry()

    def to_source(self, *, with_comments=True):
        return self.snapshot().to_source(with_comments=with_comments)

    @property
    def applied(self):
        return self.cls.__dict__.get(LIVE_SPEC_ATTR) is self

    def apply(self):
        """Use this living spec for later diagrams of the class; return self.

        Ordinary class and instance annotations remain in place. Applying
        another living spec replaces this binding, not the ordinary annotations.
        """
        self.snapshot()  # Check before changing the class binding.
        setattr(self.cls, LIVE_SPEC_ATTR, self)
        return self

    def unapply(self):
        """Detach this binding, preserving annotations and any newer binding."""
        if self.applied:
            delattr(self.cls, LIVE_SPEC_ATTR)
        return self

    def __str__(self):
        """Print the current accepted source with its prompting provenance."""
        return self.to_source()

    def __repr__(self):
        return f"<LivingSpec {self.cls.__name__}; applied={self.applied}>"
