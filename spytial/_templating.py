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


def js_literal(value):
    """A complete JavaScript string literal for ``value``, quotes included.

    JSON string syntax is a subset of JavaScript's, and ``json.dumps`` escapes
    every backslash, quote, control character and non-ASCII codepoint, which
    covers U+2028 and U+2029 -- legal in JSON but line terminators in older
    JavaScript. ``<`` is escaped on top of that: ``</script>`` inside a string
    still ends the element, whatever the string syntax says.
    """
    return json.dumps("" if value is None else str(value)).replace("<", "\\u003c")


def template_environment(directory):
    """The Jinja environment the templates are rendered with."""
    env = Environment(loader=FileSystemLoader(directory))
    env.filters["js"] = js_literal
    return env
