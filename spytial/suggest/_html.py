"""Rich ``_repr_html_`` for a SpecDraft — the propose/edit panel in a notebook.

Self-contained inline styles (no external CSS), readable on Jupyter's surface.
"""

from __future__ import annotations

import html as _html

from ._model import SpecDraft

_DOT = {"high": "#1d9e75", "medium": "#ef9f27", "low": "#b4b2a9"}


def _esc(text: object) -> str:
    return _html.escape(str(text))


def _row(suggestion, dim: bool = False) -> str:
    color = _DOT.get(suggestion.confidence, "#b4b2a9")
    opacity = "0.55" if dim else "1"
    state = "off" if dim or not suggestion.enabled_by_default else "on"
    badge_bg = "#e6f1fb" if state == "on" else "transparent"
    badge_fg = "#0c447c" if state == "on" else "#888780"
    badge_border = "none" if state == "on" else "0.5px solid #b4b2a9"
    kwargs = ", ".join(f"{k}={v!r}" for k, v in suggestion.kwargs.items())
    return (
        f'<div style="display:flex;align-items:center;gap:10px;padding:8px 10px;'
        f'border:0.5px solid #e3e1d9;border-radius:8px;opacity:{opacity};margin-bottom:6px;">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:{color};flex:none;"></span>'
        f'<div style="flex:1;min-width:0;font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#2c2c2a;">'
        f"<div>@spytial.{_esc(suggestion.directive)}({_esc(kwargs)})</div>"
        f'<div style="font-family:inherit;font-size:11px;color:#5f5e5a;font-style:italic;">'
        f"{_esc(suggestion.rationale)}</div></div>"
        f'<span style="font-size:11px;color:{badge_fg};background:{badge_bg};'
        f'border:{badge_border};padding:2px 8px;border-radius:6px;flex:none;">{state}</span>'
        f"</div>"
    )


def render_html(draft: SpecDraft) -> str:
    cls_name = _esc(draft.cls.__name__)
    enabled = draft.enabled()
    speculative = [s for s in draft.suggestions if not s.enabled_by_default]

    parts = [
        '<div style="max-width:680px;border:0.5px solid #d3d1c7;border-radius:12px;'
        'padding:16px 18px;font-family:-apple-system,Segoe UI,sans-serif;background:#fbfaf7;">',
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:2px;">'
        f'<span style="font-family:ui-monospace,Menlo,monospace;font-size:14px;color:#2c2c2a;">'
        f"spytial.suggest({cls_name})</span>"
        f'<span style="font-size:11px;color:#888780;">analysis only · no model</span></div>',
        f'<div style="font-size:12px;color:#5f5e5a;margin-bottom:14px;">'
        f"{len(draft.suggestions)} proposed · "
        f"{len(enabled)} on by default · edit, then copy or .apply()</div>",
    ]

    for s in enabled:
        parts.append(_row(s))
    for s in speculative:
        parts.append(_row(s, dim=True))

    if draft.alternatives:
        parts.append(
            '<div style="font-size:11px;color:#888780;margin:10px 0 4px;">Alternatives</div>'
        )
        for s in draft.alternatives:
            parts.append(_row(s, dim=True))

    source = _esc(draft.to_source())
    parts.append(
        '<div style="margin-top:12px;background:#f1efe8;border:0.5px solid #d3d1c7;'
        "border-radius:8px;padding:10px 12px;font-family:ui-monospace,Menlo,monospace;"
        f'font-size:12px;color:#2c2c2a;white-space:pre;overflow-x:auto;">{source}</div>'
    )

    for note in draft.notes:
        parts.append(
            f'<div style="font-size:11px;color:#888780;margin-top:8px;">ⓘ {_esc(note)}</div>'
        )

    parts.append("</div>")
    return "".join(parts)
