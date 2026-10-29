"""Historical Data: range presets/custom dates, intervals within source limits, chart, table, CSV."""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from components.data_states import require, source_caption
from components.financial_chart import price_chart
from components.metric_table import csv_download, data_table
from services import history, metrics
from utils.formatting import fmt_date, fmt_pct, fmt_price
from utils.validation import INTERVALS, INTRADAY_MAX_DAYS, preset_range, validate_history_request

PRESETS = ["1M", "3M", "6M", "YTD", "1Y", "5Y", "Max", "Custom"]


def render(symbol: str, info: dict, info_result) -> dict:
    currency = info.get("currency")
    today = date.today()

    c1, c2, c3 = st.columns([4, 2, 2], vertical_alignment="bottom")
    preset = c1.segmented_control("Range", PRESETS, default="1Y", key="hist_preset") or "1Y"
    interval_label = c2.selectbox("Interval", list(INTERVALS), index=list(INTERVALS).index("Daily"), key="hist_interval")
    chart_kind = c3.segmented_control("Chart", ["Line", "Candlestick"], default="Line", key="hist_chart") or "Line"
    interval = INTERVALS[interval_label]

    if preset == "Custom":
        d1, d2, _ = st.columns([2, 2, 4])
        start = d1.date_input("Start", value=today - timedelta(days=365), max_value=today, key="hist_start")
        end = d2.date_input("End", value=today, max_value=today, key="hist_end")
    else:
        start, end = preset_range(preset, today)

    if start is None and interval in INTRADAY_MAX_DAYS:
        start = today - timedelta(days=INTRADAY_MAX_DAYS[interval])
    if start is not None:
        req = validate_history_request(start, end, interval, today)
        start, end = req.start, req.end
        if req.warning:
            st.warning(req.warning, icon="⏱️")

    res = history.get_history(symbol, start, end, interval)
    filters = {"range": preset, "start": str(start or "max"), "end": str(end), "interval": interval_label}
    if not require(res, "price history for this range", f"history:{symbol}", "hist"):
        return {"section": "Historical Data", "filters": filters, "visible": {}}

    df = res.data
    use_adj = st.toggle("Plot adjusted close (dividend & split adjusted)", value=False, key="hist_adj",
                        disabled=chart_kind == "Candlestick")
    st.plotly_chart(price_chart(df, chart_kind, show_ma=True, currency=currency, use_adjusted=use_adj),
                    config={"displaylogo": False}, key="hist_chart_fig")

    summary = metrics.price_summary(df)
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Period return", fmt_pct(summary.get("total_return"), signed=True), help=f"Based on {summary.get('price_basis')}")
    s2.metric("High", fmt_price(df["High"].max() if "High" in df else None))
    s3.metric("Low", fmt_price(df["Low"].min() if "Low" in df else None))
    s4.metric("Volatility (ann.)", fmt_pct(summary.get("annualized_volatility")) if interval == "1d" else "—",
              help="Annualized standard deviation of daily returns (daily interval only)")
    s5.metric("Max drawdown", fmt_pct(summary.get("max_drawdown")))

    table = df.sort_index(ascending=False).reset_index()
    intraday = interval in INTRADAY_MAX_DAYS
    date_fmt = "YYYY-MM-DD HH:mm" if intraday else "YYYY-MM-DD"
    if getattr(table["Date"].dt, "tz", None) is not None and not intraday:
        table["Date"] = table["Date"].dt.tz_localize(None)
    cur = f" ({currency})" if currency else ""
    column_config = {
        "Date": st.column_config.DatetimeColumn("Date", format=date_fmt),
        "Open": st.column_config.NumberColumn(f"Open{cur}", format="%.2f"),
        "High": st.column_config.NumberColumn(f"High{cur}", format="%.2f"),
        "Low": st.column_config.NumberColumn(f"Low{cur}", format="%.2f"),
        "Close": st.column_config.NumberColumn(f"Close{cur}", format="%.2f", help="Unadjusted close as traded"),
        "Adj Close": st.column_config.NumberColumn(f"Adj Close{cur}", format="%.2f",
                                                    help="Close adjusted for splits and dividends"),
        "Volume": st.column_config.NumberColumn("Volume", format="localized"),
    }
    st.caption(f"{len(table):,} rows · {fmt_date(df.index.min())} → {fmt_date(df.index.max())} · "
               "**Close** = unadjusted traded price · **Adj Close** = adjusted for splits & dividends · "
               "Open/High/Low are unadjusted. Click a column header to sort.")
    data_table(table, column_config=column_config, height=420, key="hist_table")
    csv_download(table, f"{symbol}_{interval}_{start or 'max'}_{end}.csv", index=False, key="hist_csv")
    source_caption(res)

    visible = {k: summary.get(k) for k in ("start_date", "end_date", "start_price", "end_price", "total_return",
                                           "annualized_volatility", "max_drawdown", "price_basis")}
    return {"section": "Historical Data", "filters": filters, "visible": visible}
