# Playground

Try sPyTial without installing anything. The editor below runs **entirely in your
browser** (via [Pyodide](https://pyodide.org)) — `pip install` happens in a sandbox,
your code never leaves the page, and the diagram renders live.

Edit the code and press **Run ▶** (or <kbd>Ctrl</kbd>/<kbd>⌘</kbd> +
<kbd>Enter</kbd>). The first run takes a few seconds while the Python runtime
downloads; after that it is instant.

<iframe
  src="../assets/playground.html"
  title="sPyTial playground"
  loading="lazy"
  style="width: 100%; height: 760px; border: 1px solid var(--md-default-fg-color--lightest, #d9e0e7); border-radius: 8px;">
  The playground needs JavaScript and network access to download the Python
  runtime. If it doesn't load, follow <a href="../getting-started/">Getting
  Started</a> to <code>pip install spytial-diagramming</code> and run the
  examples locally.
</iframe>

!!! tip "Same code, your machine"
    Everything in the playground is ordinary sPyTial. Copy any example into a
    `.py` file or a notebook, `pip install spytial-diagramming`, and it runs the
    same way — opening the diagram in a browser tab (script) or inline (notebook).

Want to understand what each decorator does? See
[Getting Started](getting-started.md) for the annotated walkthrough and
[Operations](operations.md) for the full list of layout constraints and drawing
directives.
