"""The rule as its author wrote it, for spytial-core's ``source`` block.

Spec language 2026-08-25 (spytial-core 5.4.3) lets every block-bodied item
carry a ``source`` block::

    orientation:
      selector: '{ x : Node, y : Node | x.left = y }'
      directions: [below, left]
      source:
        text: "@spytial.orientation(selector=LEFT_EDGE, directions=['below', 'left'])"
        location: tree.py:12

A conflict report cites that text in place of the engine's own rendering of
the rule. That is the difference between being told an orientation constraint
over a binary selector could not be satisfied, and being shown the line to go
and edit.

The manifest calls the block generator-only: hand-written YAML needs none,
because there the YAML *is* what the author wrote. spytial is a generator, so
it stamps one on everything that accepts one.

There are two ways to say what the author wrote, tried in this order:

1. The decorator's own text, read back out of the file it was written in.
   ``@spytial.orientation(selector=LEFT_EDGE, ...)`` comes back with
   ``LEFT_EDGE`` unexpanded -- what is on the page, which is what the reader
   will be looking at when they follow the location.
2. Failing that, the call rebuilt from its arguments. This covers a REPL, an
   ``exec``, a module whose source is no longer beside its bytecode, and the
   authoring paths that are a call rather than a decorator (``annotate_*`` on
   an instance, ``annotate_type_alias``, ``Annotated[...]``).

``location`` is a basename and a line, ``tree.py:12``, the shape the manifest
documents. Deliberately not an absolute path: a spec travels inside a
self-contained HTML file that gets mailed around and committed, and the
author's home directory has no business in it.

Set ``SPYTIAL_NO_SOURCE=1`` to stamp nothing. Specs then emit exactly as they
did before 5.4.3, which is also what makes the difference testable.
"""

import ast
import functools
import inspect
import linecache
import os

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))


def enabled():
    """Whether to stamp source blocks at all (``SPYTIAL_NO_SOURCE`` turns it off)."""
    return not os.environ.get("SPYTIAL_NO_SOURCE")


def _mtime(filename):
    try:
        return os.stat(filename).st_mtime
    except OSError:
        return None


@functools.lru_cache(maxsize=128)
def _decorator_spans(filename, _stamp):
    """Every decorator expression in one file, as ``(start, end, text)``.

    Parsing a whole module to recover one line is only worth it once per file,
    hence the cache; ``_stamp`` is the file's mtime, so a module edited and
    reimported in the same process is not answered from a stale parse.

    A file that will not parse yields nothing rather than raising. By the time
    a decorator is running the module has plainly compiled, so this only comes
    up when the name in the frame is not the source that produced it -- in
    which case the reconstructed form is the honest answer anyway.
    """
    linecache.checkcache(filename)
    lines = linecache.getlines(filename)
    if not lines:
        return ()
    try:
        tree = ast.parse("".join(lines), filename)
    except (SyntaxError, ValueError):
        return ()

    # Sliced here rather than through ast.get_source_segment, which re-splits
    # the whole file on every call: that is quadratic in the number of
    # decorators, and a module with a few hundred of them spent most of its
    # import doing it. Column offsets are utf-8 byte offsets, which is the part
    # get_source_segment was being used for, so the lines are encoded once and
    # sliced as bytes.
    encoded = [line.encode("utf-8") for line in lines]

    spans = []
    for node in ast.walk(tree):
        for decorator in getattr(node, "decorator_list", ()):
            end = getattr(decorator, "end_lineno", None)
            if end is None or end > len(encoded):
                continue
            text = _slice(encoded, decorator, end)
            if text:
                spans.append((decorator.lineno, end, "@" + text))
    return tuple(spans)


def _slice(encoded, node, end):
    """The source text of one node, from utf-8 lines and byte column offsets."""
    first, last = node.lineno - 1, end - 1
    try:
        if first == last:
            return encoded[first][node.col_offset : node.end_col_offset].decode("utf-8")
        return b"".join(
            [
                encoded[first][node.col_offset :],
                *encoded[first + 1 : last],
                encoded[last][: node.end_col_offset],
            ]
        ).decode("utf-8")
    except (IndexError, UnicodeDecodeError):
        return None


def _decorator_text(filename, lineno):
    """The decorator expression covering ``lineno``, ``@`` included, or None.

    A decorator written across several lines is returned whole, which is the
    point of going through the AST rather than reading the one line the frame
    reports.
    """
    best = None
    for start, end, text in _decorator_spans(filename, _mtime(filename)):
        if start <= lineno <= end and (best is None or end - start < best[0]):
            best = (end - start, text)
    return best[1] if best else None


def _authoring_frame():
    """The innermost frame outside spytial itself: where the rule was written.

    Walking out to the package boundary rather than counting frames is what
    lets every authoring path share one implementation -- decorator on a class,
    decorator on an instance, ``annotate_*``, ``annotate_type_alias``,
    ``Annotated[...]`` -- when each reaches here at a different depth. It also
    does the right thing for a user-side helper that wraps spytial: the first
    frame that is not ours is the line someone can actually go and change.
    """
    frame = inspect.currentframe()
    try:
        while frame is not None:
            filename = frame.f_code.co_filename
            if not os.path.abspath(filename).startswith(_PACKAGE_DIR + os.sep):
                return filename, frame.f_lineno
            frame = frame.f_back
        return None, None
    finally:
        # Break the local reference into the stack we just walked.
        del frame


def render_call(name, kwargs):
    """A rule rebuilt from its arguments, for when the real text is unavailable."""
    arguments = ", ".join(f"{key}={value!r}" for key, value in kwargs.items())
    return f"{name}({arguments})"


def describe(annotation_type, kwargs, fallback=None):
    """The ``source`` block for a rule being registered, or None to omit it.

    Call from the authoring path itself, while the author's frame is still on
    the stack. ``kwargs`` should be what the author passed, before any
    deprecated-form rewriting or self-selector substitution: the block is a
    record of what was written, not of what it became.
    """
    if not enabled():
        return None

    filename, lineno = _authoring_frame()
    text = None
    location = None
    if filename:
        # A synthetic filename -- '<stdin>', '<string>' -- names no file to
        # read or to send anyone to, so neither half applies.
        if not filename.startswith("<"):
            text = _decorator_text(filename, lineno)
            location = f"{os.path.basename(filename)}:{lineno}"

    if text is None:
        text = fallback or render_call(f"spytial.{annotation_type}", kwargs)
    if not text.strip():
        # Core ignores a source block whose text is empty, so emitting one
        # would only be noise in the spec.
        return None

    block = {"text": text}
    if location:
        block["location"] = location
    return block
