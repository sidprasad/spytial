"""A stable, usable reference to a session's evolving specification."""

from ..annotations import LIVE_SPEC_ATTR, SpecUnavailableError


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
        self._session.wait()
        with self._session._operation_lock:
            result, draft = self._session._resolve(generated=True)
            if result["status"] != "supported":
                raise SpecUnavailableError(result["message"])
            return draft

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
        """Print the current accepted Python Spytial source."""
        return self.to_source(with_comments=False)

    def __repr__(self):
        return f"<LivingSpec {self.cls.__name__}; applied={self.applied}>"
