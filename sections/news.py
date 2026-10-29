"""News: article feed with populated-only category filters, performance vs benchmark, AI summary."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from components.data_states import require, source_caption
from components.financial_chart import performance_chart
from components.metric_table import data_table
from components.news_feed import news_feed
from components.quote_cards import section_title
from components.sidebar import ask
from services import history, metrics, news
from utils.formatting import fmt_date, fmt_pct


def render(symbol: str, info: dict, info_result) -> dict:
    feed_col, perf_col = st.columns([3, 2], gap="large")
    visible: dict = {}
    selected = None

    with feed_col:
        section_title("Latest news")
        res = news.get_news(symbol)
        if require(res, "news", f"news:{symbol}", "news"):
            items = res.data
            counts = pd.Series([i["category"] for i in items]).value_counts()
            options = ["All"] + list(counts.index)  # only categories that actually have articles
            selected = st.segmented_control(
                "Category", options, default="All", key=f"news_cat_{symbol}",
                format_func=lambda c: f"{c} ({len(items)})" if c == "All" else f"{c} ({counts[c]})",
                label_visibility="collapsed",
            ) or "All"
            shown = items if selected == "All" else [i for i in items if i["category"] == selected]
            c1, c2 = st.columns([3, 2], vertical_alignment="center")
            c1.caption("Categories reflect what Yahoo Finance returns for this symbol (news and press releases). "
                       "Filings and earnings documents are not provided by this feed — ask the AI analyst to search for them.")
            if c2.button("AI summary: catalysts & risks", icon="🤖", width="stretch", key="news_ai"):
                ask(f"Summarize the latest {symbol} news shown on the News page. Identify potential catalysts and "
                    "risks, cite each article with its link and date, and separate facts from interpretation.")
            news_feed(shown)
            source_caption(res)
            visible["headlines"] = [
                {"title": i["title"], "publisher": i["publisher"], "date": fmt_date(i["published"]), "url": i["url"]}
                for i in shown[:10]
            ]

    with perf_col:
        section_title("Performance overview", f"vs {config.BENCHMARK_SYMBOL}")
        stock = history.get_history_period(symbol, "10y", "1d")
        bench = history.get_history_period(config.BENCHMARK_SYMBOL, "10y", "1d")
        if require(stock, "price history", f"history_p:{symbol}", "perf"):
            rows = metrics.performance_table(stock.data, bench.data if bench.has_data else None)[:3]  # YTD, 1Y, 3Y
            st.plotly_chart(performance_chart(rows, symbol, config.BENCHMARK_SYMBOL), config={"displayModeBar": False},
                            key="perf_chart")
            table = pd.DataFrame(
                {
                    "Period": [r["period"] for r in rows],
                    symbol: [fmt_pct(r["stock_return"], signed=True) for r in rows],
                    config.BENCHMARK_SYMBOL: [fmt_pct(r["benchmark_return"], signed=True) for r in rows],
                    "Difference": [fmt_pct(r["excess_return"], signed=True) for r in rows],
                }
            )
            data_table(table)
            as_of = rows[0]["as_of"] if rows else None
            st.caption(f"Total returns on adjusted closes (dividends/splits reinvested) through {fmt_date(as_of)}. "
                       "“—” means the history does not cover the full period.")
            if not bench.has_data:
                st.warning(f"Benchmark {config.BENCHMARK_SYMBOL} unavailable: {bench.error or 'no data'}")
            visible["returns"] = {r["period"]: {"stock": r["stock_return"], "benchmark": r["benchmark_return"]} for r in rows}
            source_caption(stock)

    return {"section": "News", "filters": {"category": selected}, "visible": visible}
