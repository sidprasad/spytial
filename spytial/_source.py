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
import dataclasses
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
    """``(line count, spans)`` for one file; the count is 0 when it cannot be read.

    The two halves of a source block fail independently, so the caller has to
    be able to tell them apart. No spans covering a line means the rule was
    written as a call rather than a decorator, and the location is still good.
    No readable file at all means there is nowhere to send anyone, and the
    location has to be dropped rather than cite a path that is not there.

    Each span is ``(start, end, text)``.

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
        return 0, ()
    try:
        tree = ast.parse("".join(lines), filename)
    except (SyntaxError, ValueError):
        # Readable but not parseable: the file is still there to be opened, so
        # the location stands even though no decorator text can be recovered.
        return len(lines), ()

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
    return len(lines), tuple(spans)


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


def _read(filename, lineno):
    """``(text, is_real_line)`` for one authoring site.

    ``text`` is the decorator expression covering ``lineno``, ``@`` included,
    or None where the rule is not a decorator or the file cannot be read. A
    decorator written across several lines is returned whole, which is the
    point of going through the AST rather than reading the one line the frame
    reports.

    ``is_real_line`` says whether the file is readable and long enough to
    contain ``lineno`` -- whether, that is, there is anything at the location
    to go and look at.
    """
    line_count, spans = _decorator_spans(filename, _mtime(filename))
    best = None
    for start, end, text in spans:
        if start <= lineno <= end and (best is None or end - start < best[0]):
            best = (end - start, text)
    return (best[1] if best else None), 0 < lineno <= line_count


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


def _render_value(value):
    """One argument, as its author would have written it.

    A style block is a frozen dataclass whose optional fields default to None,
    and whose generated repr spells every one of them. Quoting that back gives
    `GroupEdge(points='togroup', lineStyle=None, textStyle=None)` for a call
    that read `GroupEdge(points='togroup')` -- text that is not on the page the
    location points at. Only the fields actually set are rendered, and nested
    blocks the same way.

    A Python selector is a function, whose repr carries a memory address. That
    address would differ on every run, in a spec meant to be committed and
    mailed around, and it is not what the author wrote either: the page says
    `selector=child_edges`. So a callable is rendered by its name.
    """
    if callable(value) and not isinstance(value, type):
        return getattr(value, "__name__", None) or repr(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        set_fields = ", ".join(
            f"{field.name}={_render_value(getattr(value, field.name))}"
            for field in dataclasses.fields(value)
            if getattr(value, field.name) is not None
        )
        return f"{type(value).__name__}({set_fields})"
    return repr(value)


def render_call(name, kwargs):
    """A rule rebuilt from its arguments, for when the real text is unavailable."""
    arguments = ", ".join(
        f"{key}={_render_value(value)}" for key, value in kwargs.items()
    )
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
    if filename and not filename.startswith("<"):
        # A synthetic filename -- '<stdin>', '<string>' -- names no file at
        # all. A real-looking one still might not be there: a module can run
        # from bytecode whose .py has been moved or deleted, and a location
        # citing it would send the reader to a file that does not exist. Only
        # a line that can actually be opened earns one.
        text, real_line = _read(filename, lineno)
        if real_line:
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
