"""Compact metric cards (label + value), rendered as an escaped HTML grid."""
from __future__ import annotations

from html import escape

import streamlit as st

from utils.formatting import UNAVAILABLE


def metric_cards(items: list[tuple[str, str]], columns: int = 4, help_unavailable: bool = True) -> None:
    """items: (label, formatted value). Unavailable values get a tooltip, never a zero."""
    cells = []
    for label, value in items:
        unavailable = value == UNAVAILABLE
        title = ' title="Not provided by the data source for this symbol"' if unavailable and help_unavailable else ""
        cls = "card-value na" if unavailable else "card-value"
        cells.append(
            f'<div class="card"><div class="card-label">{escape(label)}</div>'
            f'<div class="{cls}"{title}>{escape(value)}</div></div>'
        )
    st.markdown(
        f'<div class="card-grid" style="--cols:{columns}">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def section_title(text: str, subtitle: str | None = None) -> None:
    sub = f'<span class="section-sub">{escape(subtitle)}</span>' if subtitle else ""
    st.markdown(f'<div class="section-title">{escape(text)}{sub}</div>', unsafe_allow_html=True)
