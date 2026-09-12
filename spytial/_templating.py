"""One Jinja environment for the HTML templates, with a JS-literal filter.

Every template embeds server-side strings -- the layout spec above all -- in a
``<script>``. They used to be interpolated raw into JavaScript *template
literals*::

    const cndSpec = `{{ cnd_spec | safe }}`;

which is not a quoting context that leaves text alone. Inside backticks a
backslash escapes the next character, ``${`` opens an interpolation, and a
backtick ends the string. A spec is YAML, and PyYAML writes a multi-line
string as a double-quoted scalar with ``\n`` escapes in it -- two characters
that JavaScript turns back into a real newline before the YAML parser ever
runs. The result is a spec that is valid when Python writes it, corrupt when
the browser reads it, and a diagram that fails to lay out with a YAML error
pointing at a line the author never wrote.

Nothing in a spec used to contain a backslash, so this sat harmless until
`source` blocks started carrying decorators exactly as written, newlines and
all. The fix is to stop hand-rolling a quoting context: ``| js`` emits a
complete JavaScript string literal, quotes included, so a template says::

    const cndSpec = {{ cnd_spec | js }};

and there is no longer any character a value can contain that changes the
meaning of the page.
"""

import json

from jinja2 import Environment, FileSystemLoader


def _inert(encoded):
    """Neutralize the one character JavaScript syntax cannot protect.

    ``</script>`` ends the element wherever it appears, string literal or not:
    the HTML parser finds it before any JavaScript runs. ``<`` never occurs in
    JSON outside a string, and ``\\u003c`` inside one denotes the same
    character, so escaping every one of them is meaning-preserving in both
    filters below.
    """
    return encoded.replace("<", "\\u003c")


def js_literal(value):
    """A complete JavaScript string literal for ``value``, quotes included.

    JSON string syntax is a subset of JavaScript's, and ``json.dumps`` escapes
    every backslash, quote, control character and non-ASCII codepoint, which
    covers U+2028 and U+2029 -- legal in JSON but line terminators in older
    JavaScript.
    """
    return _inert(json.dumps("" if value is None else str(value)))


def js_json(value):
    """``value`` as a JavaScript literal: an object, array, number or string.

    For the structured payloads -- the data instance, a sequence of them, the
    frame labels. Takes the Python value rather than JSON text, so that
    serializing and making it safe to embed are one step that a caller cannot
    do half of.
    """
    return _inert(json.dumps(value))


def template_environment(directory):
    """The Jinja environment the templates are rendered with."""
    env = Environment(loader=FileSystemLoader(directory))
    env.filters["js"] = js_literal
    env.filters["js_json"] = js_json
    return env
