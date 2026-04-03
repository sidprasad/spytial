"""
sPyTial DataClassBuilder

Two paths for visual dataclass editing:

* **Widget path** – :class:`DataClassBuilder` is an ``anywidget``-based
  Jupyter widget with live two-way sync via traitlets.  Requires an
  IPython kernel (standard Jupyter).

* **HTML path** – :func:`dataclass_builder` renders standalone HTML via
  ``input_template.html`` and displays it with an inline iframe or
  browser tab, exactly like :func:`diagram`.  No kernel needed – works
  in **pyodide** and other lightweight environments.
"""

import json
import tempfile
import webbrowser
import yaml
from dataclasses import fields, is_dataclass
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
# postMessage bridge (injected into HTML for the widget iframe)
# ---------------------------------------------------------------------------

_POSTMESSAGE_BRIDGE = """
<script>
// Bridge: forward data-instance changes from the structured-input-graph
// to the parent anywidget ESM via postMessage.
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
    """Inject the postMessage bridge script before </body> in the HTML."""
    return html.replace("</body>", _POSTMESSAGE_BRIDGE + "</body>")


# ---------------------------------------------------------------------------
# ESM module for the anywidget frontend
# ---------------------------------------------------------------------------


_ESM = """
// Thin anywidget ESM: renders the full HTML page inside an iframe
// and syncs data changes back to Python via postMessage.

export function render({ model, el }) {
    const iframe = document.createElement('iframe');
    iframe.style.cssText = 'width:100%; min-height:550px; border:1px solid #e1e5e9; border-radius:6px;';
    iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin');

    // The full HTML page is passed as a model trait (generated by the
    // same template that powers the working browser path).
    iframe.srcdoc = model.get('_html');
    el.appendChild(iframe);

    // Listen for data-change messages posted by the bridge script
    // that we inject into the HTML template.
    window.addEventListener('message', (event) => {
        if (event.source !== iframe.contentWindow) return;
        if (event.data?.type === 'spytial-data-changed') {
            model.set('_data_instance', event.data.payload);
            model.save_changes();
        }
    });
}
"""

_CSS = """
.widget-dataclass-builder {
    width: 100%;
}
"""


# ---------------------------------------------------------------------------
# DataClassBuilder widget
# ---------------------------------------------------------------------------


def _ensure_anywidget():
    if not HAS_ANYWIDGET:
        raise ImportError(
            "DataClassBuilder requires the 'anywidget' package.\n"
            "Install it with:  pip install anywidget"
        )


if HAS_ANYWIDGET:

    class DataClassBuilder(anywidget.AnyWidget):
        """
        Widget-based visual editor for dataclass instances.

        Renders a ``<structured-input-graph>`` editor inline in Jupyter and
        syncs every edit back to Python.  Access the current state as a
        reified Python object via the ``.value`` property.

        Example::

            builder = DataClassBuilder(TreeNode(value=1))
            builder   # displays inline in Jupyter

            # user edits visually …

            result = builder.value   # TreeNode(value=42, left=TreeNode(…))

        As a context manager::

            with DataClassBuilder(TreeNode()) as builder:
                display(builder)
                # … edit visually …
            result = builder.value

        With change callbacks::

            builder.on_change(lambda tree: print("valid?", is_valid_bst(tree)))
        """

        _esm = _ESM
        _css = _CSS

        # Synced traits
        _data_instance = traitlets.Dict({}).tag(sync=True)
        _html = traitlets.Unicode("").tag(sync=True)

        def __init__(self, instance: Any, **kwargs):
            if not is_dataclass(instance):
                raise ValueError(
                    f"{instance} is not a dataclass instance. "
                    "Pass an instance like: DataClassBuilder(MyClass())"
                )

            dc_type = type(instance)

            # Build the initial data instance
            inst_builder = CnDDataInstanceBuilder()
            initial_data = inst_builder.build_instance(instance)

            # CnD spec
            cnd_spec = _generate_cnd_spec(instance)

            # Generate the full HTML page (same path as the browser version)
            html = _generate_dataclass_builder_html(
                initial_data=initial_data,
                cnd_spec=cnd_spec,
                dataclass_name=dc_type.__name__,
            )
            # Inject a postMessage bridge so data changes flow back to Python
            html = _inject_postmessage_bridge(html)

            super().__init__(
                _data_instance=initial_data,
                _html=html,
                **kwargs,
            )

            # Store type info for reification (not synced to frontend)
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
            """Register a callback that fires with the reified value on every edit.

            Args:
                callback: A callable that receives the reified Python object.

            Returns:
                self, for chaining.

            Example::

                builder.on_change(lambda tree: print("updated:", tree))
            """

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
    # Fallback: provide a helpful error when anywidget is not installed
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
