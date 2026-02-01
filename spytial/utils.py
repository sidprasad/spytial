"""
Shared utilities for sPyTial.
"""

from typing import Any

try:
    from IPython.display import display, HTML

    HAS_IPYTHON = True
except ImportError:
    HAS_IPYTHON = False


def is_notebook() -> bool:
    """
    Detect if we're running in a Jupyter notebook environment.
    Returns True if in a notebook, False otherwise.
    """
    if not HAS_IPYTHON:
        return False

    try:
        from IPython import get_ipython

        ipython = get_ipython()
        if ipython is None:
            return False
        # Check if we're in a notebook (IPython kernel has 'IPKernelApp')
        return "IPKernelApp" in ipython.config
    except Exception:
        return False


def default_method() -> str:
    """
    Return the default display method based on environment.
    Returns 'inline' in notebooks, 'browser' otherwise.
    """
    return "inline" if is_notebook() else "browser"


class Typed:
    """
    A wrapper that preserves type hint information for values.

    Use this when you want to pass annotated type information to diagram()
    without explicitly passing type_hint=.

    Example:
        Graph = Annotated[Dict[int, List[int]], Orientation(...)]
        g = {0: [1], 1: [2]}
        diagram(Typed(g, Graph))  # Annotations from Graph will be applied
    """

    def __init__(self, value: Any, type_hint: Any) -> None:
        self.value = value
        self.type_hint = type_hint

    def __repr__(self) -> str:
        return f"Typed({self.value!r}, {self.type_hint})"


class AnnotatedType:
    """
    A callable type alias that preserves spytial annotations.

    This provides a clean syntax for reusable annotated types:

        # Define once
        Graph = AnnotatedType(Dict[int, List[int]],
            InferredEdge(selector=EDGE_SEL, name=" "))

        # Use naturally - Graph() wraps the value with type info
        g = Graph({0: [1], 1: [2], 2: []})
        diagram(g)  # Annotations applied automatically!

    The AnnotatedType acts as both:
    - A type hint (for documentation/type checkers)
    - A constructor (wraps values with the type info)
    """

    def __init__(self, base_type: Any, *annotations: Any) -> None:
        """
        Create an annotated type alias.

        Args:
            base_type: The underlying type (e.g., Dict[int, List[int]])
            *annotations: SpytialAnnotation instances (Orientation, InferredEdge, etc.)
        """
        from typing import Annotated, get_origin, get_args

        self.base_type = base_type
        self.annotations = annotations

        # Build the Annotated type for compatibility
        if annotations:
            self._annotated = Annotated[(base_type, *annotations)]
        else:
            self._annotated = base_type

    def __call__(self, value: Any) -> "Typed":
        """
        Wrap a value with this type's annotations.

        Args:
            value: The value to wrap

        Returns:
            Typed: A wrapper that diagram() will recognize
        """
        return Typed(value, self._annotated)

    def __repr__(self) -> str:
        ann_str = ", ".join(repr(a) for a in self.annotations)
        return f"AnnotatedType({self.base_type}, {ann_str})"

    # For type checker compatibility
    def __class_getitem__(cls, item):
        return cls
