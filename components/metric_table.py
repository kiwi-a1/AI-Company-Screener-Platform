"""Two-column label/value tables (Statistics groups) and sortable data tables."""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from utils.formatting import UNAVAILABLE


def label_value_table(title: str, rows: list[dict]) -> None:
    """rows: dicts with 'label' and 'display'."""
    body = "".join(
        f'<tr><td>{escape(r["label"])}</td>'
        f'<td class="{"na" if r["display"] == UNAVAILABLE else ""}">{escape(r["display"])}</td></tr>'
        for r in rows
    )
    st.markdown(
        f'<div class="stat-table"><div class="stat-title">{escape(title)}</div>'
        f"<table>{body}</table></div>",
        unsafe_allow_html=True,
    )


def data_table(df: pd.DataFrame, column_config: dict | None = None, height: int | str = "auto", key: str | None = None) -> None:
    """Sortable, virtualized table."""
    st.dataframe(df, column_config=column_config, hide_index=True, width="stretch", height=height, key=key)


def csv_download(df: pd.DataFrame, filename: str, label: str = "Download CSV", key: str | None = None, index: bool = True) -> None:
    st.download_button(
        label,
        data=df.to_csv(index=index).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        icon="⬇️",
        key=key,
    )
