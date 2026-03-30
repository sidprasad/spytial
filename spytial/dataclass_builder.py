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
from .core_assets import (
    SPYTIAL_CORE_BROWSER_BUNDLE_URL,
    SPYTIAL_CORE_COMPONENTS_BUNDLE_URL,
    SPYTIAL_CORE_COMPONENTS_CSS_URL,
    get_template_asset_context,
)
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
# ESM module for the anywidget frontend
# ---------------------------------------------------------------------------


_ESM = """
// ---- helpers ----

function loadScript(url) {
    return new Promise((resolve, reject) => {
        if (document.querySelector(`script[src="${url}"]`)) { resolve(); return; }
        const s = document.createElement('script');
        s.src = url;
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
    });
}

function loadCSS(url) {
    if (document.querySelector(`link[href="${url}"]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = url;
    document.head.appendChild(link);
}

function getSpytialCore() {
    const candidates = [window.spytialcore, window.CndCore, window.CnDCore];
    return candidates.find(
        c => c && typeof c.JSONDataInstance === 'function' && typeof c.parseLayoutSpec === 'function'
    );
}

// ---- widget render ----

export async function render({ model, el }) {
    const coreBundleUrl     = model.get('_core_bundle_url');
    const componentsBundleUrl = model.get('_components_bundle_url');
    const componentsCssUrl  = model.get('_components_css_url');

    // Load spytial-core browser bundles
    await loadScript(coreBundleUrl);
    await loadScript(componentsBundleUrl);
    loadCSS(componentsCssUrl);

    const core = getSpytialCore();
    if (!core) {
        el.innerHTML = '<div style="color:red;padding:10px;">Failed to load spytial-core. Check your network connection.</div>';
        return;
    }

    // Mount error-message modal if available
    const errorDiv = document.createElement('div');
    errorDiv.id = 'error-core-' + Math.random().toString(36).slice(2);
    el.appendChild(errorDiv);
    if (window.mountErrorMessageModal) {
        window.mountErrorMessageModal(errorDiv.id);
    }

    // Container
    const container = document.createElement('div');
    container.style.cssText = `
        width: 100%; min-height: 500px; position: relative;
        border: 1px solid #e1e5e9; border-radius: 6px;
        overflow: hidden; background: white; display: flex; flex-direction: column;
    `;
    el.appendChild(container);

    // Create structured-input-graph web component
    const graph = document.createElement('structured-input-graph');
    graph.setAttribute('show-export', 'true');
    graph.style.cssText = 'width: 100%; flex: 1; min-height: 450px; display: block;';
    container.appendChild(graph);

    // Wait for custom element registration
    if (customElements.get('structured-input-graph') === undefined) {
        await customElements.whenDefined('structured-input-graph');
    }

    // Set initial data
    const initialData = model.get('_data_instance');
    const cndSpec     = model.get('_cnd_spec');

    const dataInstance = new core.JSONDataInstance(initialData);
    graph.setCnDSpec(cndSpec);
    graph.setDataInstance(dataInstance);

    // Sync changes back to Python model
    let syncing = false;
    function syncToPython() {
        if (syncing) return;
        syncing = true;
        try {
            if (typeof graph.getDataInstance !== 'function') return;
            const currentData = graph.getDataInstance();
            if (currentData) {
                model.set('_data_instance', JSON.parse(JSON.stringify(currentData)));
                model.save_changes();
            }
        } finally {
            syncing = false;
        }
    }

    const dataEvents = [
        'data-changed', 'atom-added', 'atom-removed', 'atom-updated',
        'edge-creation-requested', 'edge-removed', 'edge-reconnected',
    ];
    for (const evt of dataEvents) {
        graph.addEventListener(evt, syncToPython);
    }

    // Handle layout errors
    graph.addEventListener('layout-complete', (event) => {
        if (event.detail?.layoutResult?.error) {
            const err = event.detail.layoutResult.error;
            if (err.errorMessages && window.showPositionalError) {
                window.showPositionalError(err.errorMessages);
            } else if (window.showGeneralError) {
                window.showGeneralError('Layout error: ' + err.message);
            }
            graph.setAttribute('unsat', '');
        } else {
            graph.removeAttribute('unsat');
            if (window.clearAllErrors) window.clearAllErrors();
        }
    });

    graph.addEventListener('layout-error', (event) => {
        if (window.showGeneralError) {
            window.showGeneralError('Layout error: ' + (event.detail?.message || 'Unknown'));
        }
        graph.setAttribute('unsat', '');
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
        _cnd_spec = traitlets.Unicode("").tag(sync=True)
        _dataclass_name = traitlets.Unicode("").tag(sync=True)
        _core_bundle_url = traitlets.Unicode("").tag(sync=True)
        _components_bundle_url = traitlets.Unicode("").tag(sync=True)
        _components_css_url = traitlets.Unicode("").tag(sync=True)

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

            super().__init__(
                _data_instance=initial_data,
                _cnd_spec=cnd_spec,
                _dataclass_name=dc_type.__name__,
                _core_bundle_url=SPYTIAL_CORE_BROWSER_BUNDLE_URL,
                _components_bundle_url=SPYTIAL_CORE_COMPONENTS_BUNDLE_URL,
                _components_css_url=SPYTIAL_CORE_COMPONENTS_CSS_URL,
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
                import base64

                encoded_html = base64.b64encode(
                    html_content.encode("utf-8")
                ).decode("utf-8")
                iframe_html = (
                    '<div style="border: 2px solid #007acc; border-radius: 8px; '
                    'overflow: hidden;">'
                    f'<iframe src="data:text/html;base64,{encoded_html}" '
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
