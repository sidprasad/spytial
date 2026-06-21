"""
sPyTial structured input — visual editing of any value.

Two paths for visually editing a structured value:

* **Widget path** – :class:`Editor` is an ``anywidget``-based Jupyter widget
  with live two-way sync via traitlets.  Requires an IPython kernel (standard
  Jupyter).  :func:`edit` is the convenience verb that returns one.

* **HTML path** – :func:`edit_html` renders standalone HTML via
  ``input_template.html`` and displays it with an inline iframe or
  browser tab, exactly like :func:`diagram`.  No kernel needed – works
  in **pyodide** and other lightweight environments.
"""

import json
import tempfile
import webbrowser
import yaml
from dataclasses import MISSING, fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, get_type_hints

from .provider_system import CnDDataInstanceBuilder
from .annotations import collect_decorators
from ._edit_server import _EditServer
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
    """Create a reifier that reconstructs an instance of ``dc_type``.

    Allocates the instance with ``object.__new__`` and populates fields
    directly — this lets cyclic structures (self-loops, A↔B) reify by
    registering the partially-constructed instance *before* recursing into
    children, and also works for frozen dataclasses. Fields with no relation
    in the data instance fall back to their declared default.

    Note: ``__post_init__`` is intentionally not invoked (matches pickle's
    behaviour). Post-init validation can't safely run against a half-built
    cyclic instance; callers that need it can re-run it themselves.
    """

    field_defs = fields(dc_type)

    def _apply_defaults(obj: Any) -> None:
        for f in field_defs:
            if f.default is not MISSING:
                object.__setattr__(obj, f.name, f.default)
            elif f.default_factory is not MISSING:  # type: ignore[misc]
                object.__setattr__(obj, f.name, f.default_factory())

    def reifier(atom: Dict, relations: Dict, reify_atom, register=None):
        obj = object.__new__(dc_type)
        if register is not None:
            register(obj)
        _apply_defaults(obj)
        for field_name, target_ids in relations.items():
            if len(target_ids) == 1:
                value = reify_atom(target_ids[0])
            else:
                value = [reify_atom(tid) for tid in target_ids]
            object.__setattr__(obj, field_name, value)
        return obj

    return reifier


# ---------------------------------------------------------------------------
# CnD spec helper
# ---------------------------------------------------------------------------


def _generate_cnd_spec(instance: Any) -> str:
    """Generate a Spytial-Core spec (YAML) from any value's annotations.

    Works for any object — dataclasses, builtins, or plain instances.
    ``collect_decorators`` walks the class MRO and instance annotations, so a
    value with no spytial annotations simply yields an empty spec.
    """
    annotations = collect_decorators(instance)
    spec = {
        "constraints": annotations.get("constraints", []),
        "directives": annotations.get("directives", []),
    }
    return yaml.dump(spec, default_flow_style=False)


# ---------------------------------------------------------------------------
# Template-based HTML generation (used by input_template.html)
# ---------------------------------------------------------------------------


def _generate_editor_html(
    initial_data: Dict,
    cnd_spec: str,
    dataclass_name: str,
    commit: bool = False,
) -> str:
    """Generate HTML for the interactive structured-input editor (template-based).

    When ``commit`` is true the page renders Done / Cancel buttons that POST the
    current data instance back to ``/commit`` (the :func:`edit` server flow);
    otherwise it renders the standalone *Export* path (:func:`edit_html`).
    """
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
        commit=commit,
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
    const coreBundleUrl       = model.get('_core_bundle_url');
    const componentsBundleUrl = model.get('_components_bundle_url');
    const componentsCssUrl    = model.get('_components_css_url');
    const height              = model.get('_height') || 550;

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

    // Outer wrapper with explicit pixel height — Jupyter cells have no
    // inherent height, so flex children collapse without one.
    const wrapper = document.createElement('div');
    wrapper.style.cssText =
        'border: 2px solid #007acc; border-radius: 8px; overflow: hidden;' +
        'width: 100%; height: ' + height + 'px;' +
        'display: flex; flex-direction: column; background: white;';
    el.appendChild(wrapper);

    // Create structured-input-graph web component, sized to fill the wrapper.
    const graph = document.createElement('structured-input-graph');
    graph.setAttribute('show-export', 'true');
    graph.style.cssText = 'width: 100%; height: 100%; flex: 1; min-height: 0;';
    wrapper.appendChild(graph);

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

    // ---- Sync: poll + event fast-path, dedupe by JSON content ----
    // Events alone don't fire reliably for label/value edits, so we poll
    // every 250 ms. The dedupe guard makes redundant fast-path event firings
    // free.
    const SYNC_INTERVAL_MS = 250;
    let lastSyncedJSON = null;

    function syncToPython() {
        if (typeof graph.getDataInstance !== 'function') return;
        try {
            const currentData = graph.getDataInstance();
            if (!currentData) return;
            const json = JSON.stringify(currentData);
            if (json === lastSyncedJSON) return;
            lastSyncedJSON = json;
            model.set('_data_instance', JSON.parse(json));
            model.save_changes();
        } catch (e) { /* next poll retries */ }
    }

    const syncTimer = setInterval(syncToPython, SYNC_INTERVAL_MS);

    const fastPathEvents = [
        'atom-added', 'atom-removed', 'atom-updated',
        'edge-creation-requested', 'edge-removed', 'edge-reconnected',
        'data-changed',
    ];
    for (const evt of fastPathEvents) {
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

    // Cleanup on unmount (cell re-run, widget close)
    return () => {
        clearInterval(syncTimer);
    };
}
"""

_CSS = """
.widget-spytial-editor {
    width: 100%;
}
"""


# ---------------------------------------------------------------------------
# Editor widget
# ---------------------------------------------------------------------------


def _ensure_anywidget():
    if not HAS_ANYWIDGET:
        raise ImportError(
            "Editor requires the 'anywidget' package.\n"
            "Install it with:  pip install anywidget"
        )


if HAS_ANYWIDGET:

    class Editor(anywidget.AnyWidget):
        """
        Widget-based visual editor for **any** structured value.

        Renders a ``<structured-input-graph>`` editor inline in Jupyter and
        syncs every edit back to Python.  Read the current editor state as a
        freshly reified Python object via the ``.value`` property — there is no
        commit step, and the value you passed in is never mutated.

        Works for dataclasses, dicts, lists, and arbitrary objects alike; when
        the seed is a dataclass, declared field defaults are filled for any
        field an edit may have dropped.

        Example::

            ed = Editor(TreeNode(value=1))   # or Editor({"a": 1}), Editor([1, 2])
            ed                               # displays inline in Jupyter

            # user edits visually …

            result = ed.value   # a new object reified from the current state

        As a context manager::

            with Editor(TreeNode()) as ed:
                display(ed)
                # … edit visually …
            result = ed.value

        With change callbacks::

            ed.on_change(lambda tree: print("valid?", is_valid_bst(tree)))
        """

        _esm = _ESM
        _css = _CSS

        # Synced traits
        _data_instance = traitlets.Dict({}).tag(sync=True)
        _cnd_spec = traitlets.Unicode("").tag(sync=True)
        _height = traitlets.Int(550).tag(sync=True)
        _core_bundle_url = traitlets.Unicode("").tag(sync=True)
        _components_bundle_url = traitlets.Unicode("").tag(sync=True)
        _components_css_url = traitlets.Unicode("").tag(sync=True)

        def __init__(self, instance: Any, *, height: int = 550, **kwargs):
            seed_type = type(instance)

            # Build the initial data instance (works for any value)
            inst_builder = CnDDataInstanceBuilder()
            initial_data = inst_builder.build_instance(instance)

            # CnD spec (empty for values without spytial annotations)
            cnd_spec = _generate_cnd_spec(instance)

            super().__init__(
                _data_instance=initial_data,
                _cnd_spec=cnd_spec,
                _height=height,
                _core_bundle_url=SPYTIAL_CORE_BROWSER_BUNDLE_URL,
                _components_bundle_url=SPYTIAL_CORE_COMPONENTS_BUNDLE_URL,
                _components_css_url=SPYTIAL_CORE_COMPONENTS_CSS_URL,
                **kwargs,
            )

            # Store type info for reification (not synced to frontend).
            self._seed_type: Type = seed_type
            # Dataclass types reachable from the seed; empty when the seed is
            # not a dataclass, in which case .value uses reify()'s general path.
            self._dc_types: Set[Type] = _collect_dataclass_types(seed_type)
            # Remember the root atom id from the initial build. spytial-core's
            # JSONDataInstance strips extra keys on round-trip, so rootId does
            # not survive frontend sync; we keep it Python-side as a fallback.
            self._root_atom_id: Optional[str] = initial_data.get("rootId")

        @property
        def value(self) -> Any:
            """The current editor state as a reified Python object."""
            reifier = CnDDataInstanceBuilder()
            for dc_type in self._dc_types:
                reifier.register_reifier(
                    dc_type.__name__, _make_dataclass_reifier(dc_type)
                )
            return reifier.reify(self._data_instance, root_id=self._root_atom_id)

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
            return f"Editor({self._seed_type.__name__})"

else:
    # Fallback: provide a helpful error when anywidget is not installed
    class Editor:  # type: ignore[no-redef]
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


class EditCancelled(Exception):
    """Raised by :func:`edit` when the editor is cancelled and ``on_cancel="raise"``."""


def _show(url: str, height: int) -> None:
    """Display the editor URL: an inline iframe in Jupyter, else a browser tab."""
    try:
        from IPython import get_ipython

        if get_ipython() is not None:
            from IPython.display import display, IFrame

            display(IFrame(url, width="100%", height=height))
            return
    except Exception:
        pass
    webbrowser.open(url)


def _is_cancel(payload: Optional[Dict]) -> bool:
    """A missing payload, an explicit cancel, or one with no data instance is a cancel."""
    return not payload or bool(payload.get("cancelled")) or "data_instance" not in payload


def _reify_committed(seed_type: Type, payload: Dict, initial_data: Dict):
    """Reconstruct the object from a (non-cancelled) committed payload.

    Registers dataclass reifiers so declared field defaults fill for any field
    the round-trip dropped; ``initial_data``'s ``rootId`` is the v1 root (the
    editor strips the top-level rootId, so we fall back to the initial build's).
    """
    reifier = CnDDataInstanceBuilder()
    for dc_type in _collect_dataclass_types(seed_type):
        reifier.register_reifier(dc_type.__name__, _make_dataclass_reifier(dc_type))
    return reifier.reify(payload["data_instance"], root_id=initial_data.get("rootId"))


def edit(
    instance: Any,
    *,
    on_cancel: str = "none",
    timeout: Optional[float] = None,
    height: int = 560,
) -> Any:
    """Open a structured editor for any value and return the reified result on **Done**.

    The interactive counterpart to :func:`spytial.diagram`. Serves the editor as
    a page from an ephemeral ``127.0.0.1`` server (shown inline in Jupyter, or in
    a browser tab from a script), **blocks** until you click **Done** or
    **Cancel**, then reconstructs a fresh Python object with :func:`reify` and
    returns it. ``instance`` itself is never mutated.

    Accepts any value (dataclasses, dicts, lists, arbitrary objects), mirroring
    :func:`spytial.diagram`. No Jupyter kernel comm and no ``anywidget`` needed —
    only the standard library and a browser. (v1 targets local scripts and a
    local Jupyter kernel; hosted notebooks such as Colab are a follow-up.)

    Args:
        instance: Any value to seed the editor with.
        on_cancel: What to return if the editor is cancelled / closed —
            ``"none"`` (return ``None``, default), ``"seed"`` (return the
            original ``instance`` unchanged), or ``"raise"`` (raise
            :class:`EditCancelled`).
        timeout: Optional seconds to wait before giving up (treated as cancel).
        height: Pixel height of the inline iframe in Jupyter.

    Returns:
        The reified Python object on Done; otherwise per ``on_cancel``.

    Example::

        result = spytial.edit(TreeNode(value=1))   # edit visually, click Done
    """
    seed_type = type(instance)
    initial_data = CnDDataInstanceBuilder().build_instance(instance)
    html = _generate_editor_html(
        initial_data, _generate_cnd_spec(instance), seed_type.__name__, commit=True
    )

    server = _EditServer(html)
    _show(server.url, height)
    payload = server.wait(timeout)

    if _is_cancel(payload):
        if on_cancel == "seed":
            return instance
        if on_cancel == "raise":
            raise EditCancelled("edit() was cancelled")
        return None
    return _reify_committed(seed_type, payload, initial_data)


def edit_html(
    instance: Any,
    *,
    method: Optional[str] = None,
    auto_open: bool = True,
    height: int = 500,
) -> Optional[str]:
    """
    Render a visual structured-value editor as standalone HTML.

    This is the **pyodide-compatible** path.  It generates a full HTML page
    with the ``<structured-input-graph>`` editor and displays it via an
    inline iframe (in notebooks) or a browser tab.  Use the built-in
    *Export* button to copy the resulting Python constructor code.

    Accepts any value (dataclasses, dicts, lists, arbitrary objects). For live
    two-way sync in Jupyter with a ``.value`` round-trip, use :func:`edit`
    (the :class:`Editor` widget) instead.

    Args:
        instance: Any value to start editing from.
        method: ``"inline"`` (default in notebooks), ``"browser"``, or
            ``None`` (auto-detect).
        auto_open: Open the browser tab automatically (only for
            ``method="browser"``).
        height: Pixel height of the inline iframe.

    Returns:
        ``None`` when displayed inline, or the path to the temp HTML file
        when displayed in a browser.

    Example::

        spytial.edit_html(TreeNode(value=1))   # or {"a": 1}, [1, 2], …
    """
    inst_builder = CnDDataInstanceBuilder()
    initial_data = inst_builder.build_instance(instance)
    cnd_spec = _generate_cnd_spec(instance)

    html = _generate_editor_html(
        initial_data=initial_data,
        cnd_spec=cnd_spec,
        dataclass_name=type(instance).__name__,
    )

    if method is None:
        method = default_method()

    return _deliver_html_content(
        html, method=method, auto_open=auto_open, height=height
    )
