"""Holders: major holders breakdown, top institutional and mutual-fund holders (with report dates)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.data_states import require, source_caption
from components.financial_chart import ownership_donut
from components.metric_table import csv_download, data_table
from components.quote_cards import metric_cards, section_title
from services import ownership
from utils.formatting import fmt_date, fmt_int, fmt_pct
from utils.normalization import MAJOR_HOLDER_LABELS


def _holder_table(df: pd.DataFrame, name_label: str, key: str, symbol: str) -> None:
    if df.empty:
        st.info(f"No {name_label.lower()} records available from Yahoo Finance.", icon="ℹ️")
        return
    reported = df["Date Reported"].dropna()
    if not reported.empty:
        lo, hi = reported.min(), reported.max()
        st.caption(f"Reporting dates: {fmt_date(lo)}" + (f" – {fmt_date(hi)}" if hi != lo else ""))
    table = df.rename(columns={"Holder": name_label})
    column_config = {
        "Shares": st.column_config.NumberColumn("Shares", format="localized"),
        "Date Reported": st.column_config.DateColumn("Date Reported", format="YYYY-MM-DD"),
        "% Out": st.column_config.NumberColumn("% Out", format="percent", help="Percent of shares outstanding"),
        "Value": st.column_config.NumberColumn("Value", format="compact", help="Position value at the report date"),
        "% Change": st.column_config.NumberColumn("% Change", format="percent", help="Change in position vs prior filing"),
    }
    data_table(table, column_config=column_config, key=f"holders_{key}")
    csv_download(table, f"{symbol}_{key}_holders.csv", index=False, key=f"csv_{key}")


def render(symbol: str, info: dict, info_result) -> dict:
    st.info("Ownership data comes from periodic regulatory filings (e.g. 13F, fund reports). Each record is as of "
            "its **Date Reported** — these are not real-time transactions.", icon="🗓️")
    res = ownership.get_holders(symbol)
    if not require(res, "ownership data", f"holders:{symbol}", "holders"):
        return {"section": "Holders", "filters": {}, "visible": {}}
    major = res.data["major"]

    left, right = st.columns([3, 2], gap="large")
    with left:
        section_title("Major holders")
        cards = []
        for key, label in MAJOR_HOLDER_LABELS.items():
            v = major.get(key)
            cards.append((label, fmt_int(v) if key == "institutionsCount" else fmt_pct(v)))
        metric_cards(cards, columns=2)
    with right:
        fig = ownership_donut(major)
        if fig is not None:
            st.plotly_chart(fig, config={"displayModeBar": False}, key="own_donut")
            st.caption("“Other / Retail” is the remainder after insider and institutional holdings.")

    tab_inst, tab_fund = st.tabs(["🏦 Top institutional holders", "📈 Top mutual fund holders"])
    with tab_inst:
        _holder_table(res.data["institutional"], "Institution", "institutional", symbol)
    with tab_fund:
        _holder_table(res.data["mutualfund"], "Fund", "mutualfund", symbol)
    source_caption(res)

    top = res.data["institutional"].head(5)
    visible = {
        "major_holders": {MAJOR_HOLDER_LABELS[k]: v for k, v in major.items()},
        "top_institutions": [
            {"holder": r["Holder"], "pct_out": r["% Out"], "date_reported": fmt_date(r["Date Reported"])}
            for _, r in top.iterrows()
        ],
    }
    return {"section": "Holders", "filters": {}, "visible": visible}
