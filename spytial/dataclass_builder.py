"""
sPyTial DataClassBuilder

* :class:`DataClassBuilder` – visual editor that renders a
  ``<structured-input-graph>`` inside an inline ``srcdoc`` iframe
  (same mechanism as :func:`diagram`).  Works in any IPython kernel.
  Use the built-in *Export* button to copy out constructor code.

* :func:`dataclass_builder` – standalone HTML page displayed via
  inline iframe or browser tab.  No kernel needed – works in
  **pyodide** and other lightweight environments.
"""

import html as html_mod
import http.server
import json
import os
import socket
import tempfile
import threading
import webbrowser
import yaml
from dataclasses import fields, is_dataclass
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, get_type_hints

from .provider_system import CnDDataInstanceBuilder
from .annotations import collect_decorators
from .core_assets import get_template_asset_context
from .utils import default_method

try:
    from IPython.display import display, HTML

    HAS_IPYTHON = True
except ImportError:
    HAS_IPYTHON = False

try:
    from jinja2 import Environment, FileSystemLoader

    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False

try:
    import anywidget
    import traitlets

    HAS_ANYWIDGET = True
except ImportError:
    HAS_ANYWIDGET = False


# ---------------------------------------------------------------------------
# Dataclass type introspection helpers
# ---------------------------------------------------------------------------


def _extract_inner_types(tp: Any) -> List[Any]:
    """Extract concrete types from generic aliases (Optional, List, Union, etc.)."""
    args = getattr(tp, "__args__", None)
    if args:
        result = []
        for arg in args:
            if arg is type(None):
                continue
            result.append(arg)
            result.extend(_extract_inner_types(arg))
        return result
    return []


def _collect_dataclass_types(
    dc_type: Type, visited: Optional[Set[Type]] = None
) -> Set[Type]:
    """Walk type annotations to find all reachable dataclass types."""
    if visited is None:
        visited = set()
    if dc_type in visited or not is_dataclass(dc_type):
        return visited

    visited.add(dc_type)

    try:
        hints = get_type_hints(dc_type)
    except Exception:
        hints = {f.name: f.type for f in fields(dc_type)}

    for field_type in hints.values():
        candidates = [field_type] + _extract_inner_types(field_type)
        for t in candidates:
            if isinstance(t, type) and is_dataclass(t) and t not in visited:
                _collect_dataclass_types(t, visited)

    return visited


def _make_dataclass_reifier(dc_type: Type):
    """Create a reifier function that constructs an actual dataclass instance."""

    def reifier(atom: Dict, relations: Dict, reify_atom):
        kwargs = {}
        for field_name, target_ids in relations.items():
            if len(target_ids) == 1:
                kwargs[field_name] = reify_atom(target_ids[0])
            else:
                kwargs[field_name] = [reify_atom(tid) for tid in target_ids]
        return dc_type(**kwargs)

    return reifier


# ---------------------------------------------------------------------------
# CnD spec helper
# ---------------------------------------------------------------------------


def _generate_cnd_spec(instance: Any) -> str:
    """Generate Spytial-Core spec in YAML format from dataclass instance annotations."""
    if not is_dataclass(instance):
        raise ValueError(f"{instance} is not a dataclass instance")

    annotations = collect_decorators(instance)
    spec = {
        "constraints": annotations.get("constraints", []),
        "directives": annotations.get("directives", []),
    }
    return yaml.dump(spec, default_flow_style=False)


# ---------------------------------------------------------------------------
# Template-based HTML generation (used by input_template.html)
# ---------------------------------------------------------------------------


def _generate_dataclass_builder_html(
    initial_data: Dict,
    cnd_spec: str,
    dataclass_name: str,
) -> str:
    """Generate HTML for the interactive dataclass builder (template-based)."""
    if not HAS_JINJA2:
        raise ImportError(
            "Jinja2 is required for HTML generation. Install with: pip install jinja2"
        )

    current_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(current_dir))

    try:
        template = env.get_template("input_template.html")
    except Exception as e:
        raise FileNotFoundError(f"input_template.html not found in {current_dir}: {e}")

    return template.render(
        python_data=json.dumps(initial_data),
        cnd_spec=cnd_spec,
        dataclass_name=dataclass_name,
        title=f"{dataclass_name} Builder",
        **get_template_asset_context(),
    )


# ---------------------------------------------------------------------------
# Local asset server (serves HTML from temp dir on a random port)
# ---------------------------------------------------------------------------

class _SilentHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that serves from a given directory with CORS and no logs."""

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # silence


_server_port: Optional[int] = None


def _ensure_asset_server() -> int:
    """Start a localhost HTTP server (once) that serves temp HTML files."""
    global _server_port
    if _server_port is not None:
        return _server_port

    handler = partial(_SilentHandler, directory=tempfile.gettempdir())
    # Bind to a random free port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = http.server.HTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    _server_port = port
    return port


# ---------------------------------------------------------------------------
# postMessage bridge (injected into iframe HTML)
# ---------------------------------------------------------------------------

_POSTMESSAGE_BRIDGE = """
<script>
(function() {
    var graph = document.getElementById('structured-graph');
    if (!graph) return;

    var events = [
        'data-changed', 'atom-added', 'atom-removed', 'atom-updated',
        'edge-creation-requested', 'edge-removed', 'edge-reconnected',
    ];

    function postData() {
        if (typeof graph.getDataInstance !== 'function') return;
        var data = graph.getDataInstance();
        if (data) {
            window.parent.postMessage({
                type: 'spytial-data-changed',
                payload: JSON.parse(JSON.stringify(data))
            }, '*');
        }
    }

    events.forEach(function(evt) {
        graph.addEventListener(evt, postData);
    });
})();
</script>
"""


def _inject_postmessage_bridge(html: str) -> str:
    """Inject the postMessage bridge script before </body>."""
    return html.replace("</body>", _POSTMESSAGE_BRIDGE + "</body>")


# ---------------------------------------------------------------------------
# ESM + widget class
# ---------------------------------------------------------------------------

# The ESM loads the HTML from a localhost URL (tiny trait) instead of
# syncing 3.6 MB of inlined JS through the anywidget comm channel.
_ESM = """
export function render({ model, el }) {
    const url = model.get('_iframe_url');

    const iframe = document.createElement('iframe');
    iframe.style.cssText = 'width:100%; min-height:550px; border:1px solid #e1e5e9; border-radius:6px;';
    iframe.src = url;
    el.appendChild(iframe);

    const handler = (event) => {
        if (event.source !== iframe.contentWindow) return;
        if (event.data && event.data.type === 'spytial-data-changed') {
            model.set('_data_instance', event.data.payload);
            model.save_changes();
        }
    };
    window.addEventListener('message', handler);

    return () => { window.removeEventListener('message', handler); };
}
"""

_CSS = ""


def _ensure_anywidget():
    if not HAS_ANYWIDGET:
        raise ImportError(
            "DataClassBuilder requires the 'anywidget' package.\n"
            "Install it with:  pip install anywidget"
        )


if HAS_ANYWIDGET:

    class DataClassBuilder(anywidget.AnyWidget):
        """
        Visual editor for dataclass instances.

        Renders a ``<structured-input-graph>`` editor inline in Jupyter
        and syncs every edit back to Python via postMessage + traitlets.

        Example::

            builder = DataClassBuilder(TreeNode(value=1))
            builder   # displays inline in Jupyter
            result = builder.value
        """

        _esm = _ESM
        _css = _CSS

        _data_instance = traitlets.Dict({}).tag(sync=True)
        _iframe_url = traitlets.Unicode("").tag(sync=True)

        def __init__(self, instance: Any, **kwargs):
            if not is_dataclass(instance):
                raise ValueError(
                    f"{instance} is not a dataclass instance. "
                    "Pass an instance like: DataClassBuilder(MyClass())"
                )

            dc_type = type(instance)

            inst_builder = CnDDataInstanceBuilder()
            initial_data = inst_builder.build_instance(instance)
            cnd_spec = _generate_cnd_spec(instance)

            html = _generate_dataclass_builder_html(
                initial_data=initial_data,
                cnd_spec=cnd_spec,
                dataclass_name=dc_type.__name__,
            )
            html = _inject_postmessage_bridge(html)

            # Write HTML to a temp file and serve it via localhost
            port = _ensure_asset_server()
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".html",
                delete=False,
                encoding="utf-8",
                dir=tempfile.gettempdir(),
            ) as f:
                f.write(html)
                fname = os.path.basename(f.name)

            iframe_url = f"http://127.0.0.1:{port}/{fname}"

            super().__init__(
                _data_instance=initial_data,
                _iframe_url=iframe_url,
                **kwargs,
            )

            self._dataclass_type: Type = dc_type
            self._dc_types: Set[Type] = _collect_dataclass_types(dc_type)

        @property
        def value(self) -> Any:
            """The current editor state as a reified Python object."""
            reifier = CnDDataInstanceBuilder()
            for dc_type in self._dc_types:
                reifier.register_reifier(
                    dc_type.__name__, _make_dataclass_reifier(dc_type)
                )
            return reifier.reify(self._data_instance)

        @property
        def data_instance(self) -> Dict:
            """The raw data-instance dict last synced from the editor."""
            return self._data_instance

        def on_change(self, callback):
            """Register a callback that fires with the reified value on every edit."""

            def _handler(change):
                callback(self.value)

            self.observe(_handler, names=["_data_instance"])
            return self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def __repr__(self) -> str:
            return f"DataClassBuilder({self._dataclass_type.__name__})"

else:

    class DataClassBuilder:  # type: ignore[no-redef]
        """Placeholder that raises on instantiation when anywidget is missing."""

        def __init__(self, *args, **kwargs):
            _ensure_anywidget()


# ---------------------------------------------------------------------------
# HTML delivery (mirrors visualizer._deliver_html_content)
# ---------------------------------------------------------------------------


def _deliver_html_content(
    html_content: str,
    method: str,
    auto_open: bool,
    height: int,
) -> Optional[str]:
    """Display or persist already-rendered builder HTML."""
    if method == "inline":
        if HAS_IPYTHON:
            try:
                import html as html_mod

                escaped = html_mod.escape(html_content, quote=True)
                iframe_html = (
                    '<div style="border: 2px solid #007acc; border-radius: 8px; '
                    'overflow: hidden;">'
                    f'<iframe srcdoc="{escaped}" '
                    f'width="100%" height="{height + 50}px" frameborder="0" '
                    'style="display: block;"></iframe></div>'
                )
                display(HTML(iframe_html))
                return None
            except Exception:
                pass

        return _deliver_html_content(
            html_content, method="browser", auto_open=auto_open, height=height
        )

    if method == "browser":
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html_content)
            temp_path = f.name

        if auto_open:
            webbrowser.open(f"file://{temp_path}")
        return temp_path

    raise ValueError(f"Unknown display method: {method}")


# ---------------------------------------------------------------------------
# Convenience function (HTML path – pyodide compatible)
# ---------------------------------------------------------------------------


def dataclass_builder(
    instance: Any,
    *,
    method: Optional[str] = None,
    auto_open: bool = True,
    height: int = 500,
) -> Optional[str]:
    """
    Render a visual dataclass builder as standalone HTML.

    This is the **pyodide-compatible** path.  It generates a full HTML page
    with the ``<structured-input-graph>`` editor and displays it via an
    inline iframe (in notebooks) or a browser tab.  Use the built-in
    *Export* button to copy the resulting Python constructor code.

    For live two-way sync in Jupyter, use :class:`DataClassBuilder` instead.

    Args:
        instance: A dataclass instance to start editing from.
        method: ``"inline"`` (default in notebooks), ``"browser"``, or
            ``None`` (auto-detect).
        auto_open: Open the browser tab automatically (only for
            ``method="browser"``).
        height: Pixel height of the inline iframe.

    Returns:
        ``None`` when displayed inline, or the path to the temp HTML file
        when displayed in a browser.

    Example::

        spytial.dataclass_builder(TreeNode(value=1))
    """
    if not is_dataclass(instance):
        raise ValueError(
            f"{instance} is not a dataclass instance. "
            "Pass an instance like: dataclass_builder(MyClass())"
        )

    inst_builder = CnDDataInstanceBuilder()
    initial_data = inst_builder.build_instance(instance)
    cnd_spec = _generate_cnd_spec(instance)

    html = _generate_dataclass_builder_html(
        initial_data=initial_data,
        cnd_spec=cnd_spec,
        dataclass_name=type(instance).__name__,
    )

    if method is None:
        method = default_method()

    return _deliver_html_content(
        html, method=method, auto_open=auto_open, height=height
    )
