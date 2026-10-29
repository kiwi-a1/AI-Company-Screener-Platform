"""Financials: income / balance / cash flow, annual or quarterly, with synced chart, ratios and CSV."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.data_states import require, source_caption
from components.financial_chart import statement_chart
from components.metric_table import csv_download, data_table
from components.quote_cards import section_title
from services import financials, metrics
from utils.formatting import UNIT_DIVISORS, fmt_number, fmt_pct
from utils.normalization import STATEMENT_LABELS

DEFAULT_CHART_ITEMS = {
    "income": ["TotalRevenue", "GrossProfit", "OperatingIncome", "NetIncome"],
    "balance": ["TotalAssets", "TotalLiabilitiesNetMinorityInterest", "StockholdersEquity", "TotalDebt"],
    "cashflow": ["OperatingCashFlow", "CapitalExpenditure", "FreeCashFlow"],
}


def _period_label(p: pd.Timestamp, frequency: str) -> str:
    if frequency == "quarterly":
        return f"Q/E {p.strftime('%Y-%m-%d')}"
    return f"FY {p.strftime('%Y-%m-%d')}"


def render(symbol: str, info: dict, info_result) -> dict:
    c1, c2, c3 = st.columns([4, 2, 2], vertical_alignment="bottom")
    kind = c1.segmented_control("Statement", list(STATEMENT_LABELS), default="income",
                                format_func=STATEMENT_LABELS.get, key="fin_kind") or "income"
    frequency = c2.segmented_control("Frequency", ["annual", "quarterly"], default="annual",
                                     format_func=str.title, key="fin_freq") or "annual"
    units = c3.selectbox("Units", list(UNIT_DIVISORS), index=2, key="fin_units")
    divisor = UNIT_DIVISORS[units]
    currency = info.get("financialCurrency") or info.get("currency")

    res = financials.get_statement(symbol, kind, frequency)
    filters = {"statement": STATEMENT_LABELS[kind], "frequency": frequency, "units": units}
    if not require(res, f"{frequency} {STATEMENT_LABELS[kind].lower()} data", f"stmt:{symbol}:{kind}:{frequency}", "fin"):
        return {"section": "Financials", "filters": filters, "visible": {}}
    stmt = res.data
    if stmt.empty:
        st.info("Yahoo Finance returned an empty statement for this symbol.", icon="ℹ️")
        return {"section": "Financials", "filters": filters, "visible": {}}

    o1, o2, o3 = st.columns([2, 2, 2], vertical_alignment="bottom")
    n_periods = len(stmt.periods)
    shown = o1.slider("Periods shown", 1, n_periods, n_periods, key=f"fin_periods_{kind}_{frequency}") if n_periods > 1 else 1
    oldest_first = o2.toggle("Oldest period first", value=False, key="fin_order")
    show_all = o3.toggle("Show all line items", value=False, key="fin_all",
                         help="Key items follow the spec's line-item list; 'all' adds every item Yahoo reports.")

    periods = stmt.periods[:shown]
    if oldest_first:
        periods = list(reversed(periods))
    keys = list(stmt.values.index) if show_all else stmt.key_items

    def fmt_cell(key: str, value) -> str:
        kind_ = stmt.value_kinds.get(key, "money")
        if kind_ == "per_share":
            return fmt_number(value)
        return fmt_number(None if pd.isna(value) else value / divisor, 2 if divisor > 1 else 0)

    display = pd.DataFrame(
        {_period_label(p, frequency): [fmt_cell(k, stmt.values.at[k, p]) for k in keys] for p in periods}
    )
    display.insert(0, "Line item", [stmt.labels.get(k, k) for k in keys])
    unit_note = f"{currency or ''} {units.lower() if divisor > 1 else ''}".strip()
    st.caption(f"Values in **{unit_note or 'reporting currency'}** (EPS in {currency or 'currency'} per share; "
               f"share counts use the same unit scale). “—” = not reported. Yahoo provides ~4 annual or ~5 quarterly periods.")
    data_table(display, height=min(38 * (len(display) + 1), 700), key=f"fin_table_{kind}")

    raw = stmt.values.loc[keys, periods].copy()
    raw.index = [stmt.labels.get(k, k) for k in keys]
    raw.columns = [p.date().isoformat() for p in periods]
    csv_download(raw, f"{symbol}_{kind}_{frequency}.csv", label="Download CSV (raw values)", key="fin_csv")
    source_caption(res)

    section_title("Chart", "synced with statement, frequency and periods above")
    options = list(stmt.values.index)
    defaults = [k for k in DEFAULT_CHART_ITEMS[kind] if k in options] or options[:2]
    m1, m2 = st.columns([5, 1], vertical_alignment="bottom")
    selected = m1.multiselect("Metrics", options, default=defaults, format_func=lambda k: stmt.labels.get(k, k),
                              key=f"fin_metrics_{kind}_{frequency}")
    chart_type = m2.segmented_control("Type", ["Bar", "Line"], default="Bar", key="fin_chart_type") or "Bar"
    if selected:
        series = {k: stmt.values.loc[k, stmt.periods[:shown]].astype("float64") for k in selected}
        per_share = all(stmt.value_kinds.get(k) == "per_share" for k in selected)
        st.plotly_chart(
            statement_chart(series, stmt.labels, chart_type, unit_label=f"{currency or ''}" + ("" if per_share else f" ({units})"),
                            divisor=1.0 if per_share else divisor),
            config={"displaylogo": False}, key="fin_chart",
        )
    else:
        st.caption("Select one or more metrics to chart.")

    visible = {}
    if kind == "income":
        _ratios(symbol, stmt, frequency, shown)
    latest = stmt.periods[0]
    visible = {
        "latest_period": latest.date().isoformat(),
        **{stmt.labels.get(k, k): stmt.get(k, latest) for k in stmt.key_items[:15]},
    }
    return {"section": "Financials", "filters": filters | {"periods_shown": shown, "charted": selected}, "visible": visible}


def _ratios(symbol: str, income, frequency: str, shown: int) -> None:
    section_title("Calculated margins & growth", "computed from the reported statements")
    bal = financials.get_statement(symbol, "balance", frequency)
    ratios = metrics.statement_ratios(income, bal.data if bal.has_data else None)
    if ratios.empty:
        return
    growth_label = "QoQ" if frequency == "quarterly" else "YoY"
    for key, label in (("TotalRevenue", "Revenue Growth"), ("NetIncome", "Net Income Growth"), ("DilutedEPS", "Diluted EPS Growth")):
        g = metrics.statement_growth(income, key)
        if not g.empty:
            ratios.loc[f"{label} ({growth_label})"] = g
    periods = income.periods[:shown]
    ratios = ratios[[p for p in periods if p in ratios.columns]]
    display = pd.DataFrame({_period_label(p, frequency): [fmt_pct(v) if not ("Debt / Equity" in idx or "Current Ratio" in idx)
                                                          else fmt_number(v) for idx, v in ratios[p].items()]
                            for p in ratios.columns})
    display.insert(0, "Metric", list(ratios.index))
    data_table(display, key="fin_ratios")
    st.caption("Calculated values (not reported by the company). ROE/ROA use period-end balances and are only shown "
               "where a balance sheet exists for the same period. Quarterly growth is sequential (vs prior quarter).")
