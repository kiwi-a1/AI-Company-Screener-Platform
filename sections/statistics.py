"""Statistics: eight metric groups (spec §4.3) plus dividend and split history."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.data_states import source_caption
from components.financial_chart import bar_series
from components.metric_table import csv_download, data_table, label_value_table
from components.quote_cards import section_title
from services import history
from services.statistics import STAT_GROUPS, group_rows

LEFT = ["Valuation Measures", "Profitability", "Management Effectiveness", "Financial Highlights"]
RIGHT = ["Balance Sheet Health", "Trading Information", "Share Statistics", "Dividends & Splits"]


def render(symbol: str, info: dict, info_result) -> dict:
    currency = info.get("currency")
    fin_currency = info.get("financialCurrency")
    st.caption(
        f"Trading currency: **{currency or '—'}**"
        + (f" · Financials reported in **{fin_currency}**" if fin_currency and fin_currency != currency else "")
        + " · ttm = trailing twelve months, mrq = most recent quarter. “—” = not provided by Yahoo Finance."
    )
    visible = {}
    left, right = st.columns(2, gap="large")
    for col, groups in ((left, LEFT), (right, RIGHT)):
        with col:
            for group in groups:
                rows = group_rows(info, group)
                label_value_table(group, rows)
                visible[group] = {r["label"]: r["display"] for r in rows}
    source_caption(info_result)

    section_title("Dividend & split history")
    div_col, split_col = st.columns([3, 2], gap="large")
    with div_col:
        res = history.get_dividends(symbol)
        if res.has_data and len(res.data) > 0:
            s = res.data.copy()
            s.index = pd.to_datetime(s.index)
            yearly = s.groupby(s.index.year).sum()
            yearly.index = yearly.index.astype(str)
            st.plotly_chart(bar_series(yearly, f"Dividends per share by calendar year ({currency or ''})"),
                            config={"displayModeBar": False}, key="div_chart")
            table = pd.DataFrame({"Ex-Date": s.index.date, "Dividend": s.values}).sort_values("Ex-Date", ascending=False)
            with st.expander(f"All dividend payments ({len(table)})"):
                data_table(table, column_config={"Dividend": st.column_config.NumberColumn(format="%.4f")}, height=300)
                csv_download(table, f"{symbol}_dividends.csv", index=False, key="div_csv")
            st.caption("Per-share amounts as reported, adjusted by Yahoo for later splits.")
        elif res.error and not res.has_data:
            st.error(f"Could not load dividends: {res.error}")
        else:
            st.info("No dividend history reported for this symbol.", icon="ℹ️")
    with split_col:
        res = history.get_splits(symbol)
        if res.has_data and len(res.data) > 0:
            s = res.data
            table = pd.DataFrame({"Date": pd.to_datetime(s.index).date, "Split ratio": [f"{v:g}:1" if v >= 1 else f"1:{1 / v:g}" for v in s.values]})
            data_table(table.sort_values("Date", ascending=False), height=min(300, 36 * (len(table) + 1)))
        elif res.error and not res.has_data:
            st.error(f"Could not load splits: {res.error}")
        else:
            st.info("No stock splits reported for this symbol.", icon="ℹ️")

    return {"section": "Statistics", "filters": {}, "visible": {k: visible[k] for k in list(STAT_GROUPS)[:4]}}
