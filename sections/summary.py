"""Summary: identity, quote, trading, valuation, other metrics, overview, sparkline, peers, comparison."""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from components.data_states import source_caption
from components.financial_chart import sparkline
from components.metric_table import data_table
from components.quote_cards import metric_cards, section_title
from components.search import select_symbol
from services import history, market_data, metrics
from services.market_data import get_related
from utils.formatting import (UNAVAILABLE, fmt_date, fmt_int, fmt_large, fmt_number, fmt_pct, fmt_price, fmt_value,
                              is_missing)
from utils.validation import is_valid_symbol, normalize_symbol

SPARK_PERIODS = {"1M": "1mo", "6M": "6mo", "YTD": "ytd", "1Y": "1y", "5Y": "5y"}


def _range(low, high) -> str:
    if is_missing(low) or is_missing(high):
        return UNAVAILABLE
    return f"{fmt_price(low)} – {fmt_price(high)}"


def _bid_ask(price, size) -> str:
    if is_missing(price) or price == 0:  # Yahoo uses 0 for "no quote"
        return UNAVAILABLE
    return f"{fmt_price(price)}" + (f" × {fmt_int(size)}" if not is_missing(size) and size else "")


def _earnings_date(info: dict) -> str:
    start, end = info.get("earningsTimestampStart"), info.get("earningsTimestampEnd")
    if start and end and start.date() != end.date():
        return f"{fmt_date(start)} – {fmt_date(end)}"
    return fmt_date(info.get("earningsTimestamp") or start)


def _dividend(info: dict) -> str:
    rate, yld = info.get("dividendRate"), info.get("dividendYield")
    if is_missing(rate) and is_missing(yld):
        return UNAVAILABLE
    return f"{fmt_price(rate)} ({fmt_pct(yld, ratio=False)})"


def render(symbol: str, info: dict, info_result) -> dict:
    left, right = st.columns([3, 2], gap="large")

    quote_items = [
        ("Previous Close", fmt_price(info.get("prev_close"))),
        ("Open", fmt_price(info.get("regularMarketOpen") or info.get("open"))),
        ("Day's Range", _range(info.get("regularMarketDayLow") or info.get("dayLow"), info.get("regularMarketDayHigh") or info.get("dayHigh"))),
        ("52-Week Range", _range(info.get("fiftyTwoWeekLow"), info.get("fiftyTwoWeekHigh"))),
        ("Volume", fmt_int(info.get("regularMarketVolume") or info.get("volume"))),
        ("Avg. Volume (3M)", fmt_int(info.get("averageVolume"))),
        ("Bid", _bid_ask(info.get("bid"), info.get("bidSize"))),
        ("Ask", _bid_ask(info.get("ask"), info.get("askSize"))),
    ]
    valuation_items = [
        ("Market Cap", fmt_large(info.get("marketCap"))),
        ("Enterprise Value", fmt_large(info.get("enterpriseValue"))),
        ("P/E (TTM)", fmt_number(info.get("trailingPE"))),
        ("Forward P/E", fmt_number(info.get("forwardPE"))),
        ("PEG Ratio", fmt_number(info.get("trailingPegRatio") or info.get("pegRatio"))),
        ("Price/Sales (TTM)", fmt_number(info.get("priceToSalesTrailing12Months"))),
        ("Price/Book", fmt_number(info.get("priceToBook"))),
        ("EV/Revenue", fmt_number(info.get("enterpriseToRevenue"))),
        ("EV/EBITDA", fmt_number(info.get("enterpriseToEbitda"))),
    ]
    other_items = [
        ("EPS (TTM)", fmt_price(info.get("trailingEps"))),
        ("Forward EPS", fmt_price(info.get("forwardEps"))),
        ("Earnings Date", _earnings_date(info)),
        ("Fwd. Dividend & Yield", _dividend(info)),
        ("Ex-Dividend Date", fmt_date(info.get("exDividendDate"))),
        ("Beta (5Y Monthly)", fmt_number(info.get("beta"))),
        ("1Y Target Est. (mean)", fmt_price(info.get("targetMeanPrice"))),
        ("Analyst Rating", (info.get("recommendationKey") or UNAVAILABLE).replace("_", " ").title() if info.get("recommendationKey") else UNAVAILABLE),
    ]

    with left:
        section_title("Quote & trading")
        metric_cards(quote_items, columns=4)
        section_title("Valuation")
        metric_cards(valuation_items, columns=3)
        section_title("Earnings, dividends & other")
        metric_cards(other_items, columns=4)
        source_caption(info_result)

    with right:
        section_title("Price")
        choice = st.segmented_control("Sparkline period", list(SPARK_PERIODS), default="1Y", key="spark_period",
                                      label_visibility="collapsed") or "1Y"
        res = history.get_history_period(symbol, SPARK_PERIODS[choice], "1d" if choice != "5Y" else "1wk")
        if res.has_data:
            ret = metrics.pct_change(res.data["Close"].dropna().iloc[-1], res.data["Close"].dropna().iloc[0])
            st.plotly_chart(sparkline(res.data, height=170), config={"displayModeBar": False}, key="spark")
            st.caption(f"{choice} change (unadjusted close): **{fmt_pct(ret, signed=True)}**")
        else:
            st.info("Price history unavailable for this period.", icon="ℹ️")

        section_title("Business overview")
        profile = [
            ("Sector", info.get("sector")),
            ("Industry", info.get("industry")),
            ("Country", info.get("country")),
            ("Employees", fmt_int(info.get("fullTimeEmployees")) if info.get("fullTimeEmployees") else None),
            ("Type", info.get("quoteType")),
        ]
        metric_cards([(k, v or UNAVAILABLE) for k, v in profile], columns=2)
        website = info.get("website")
        if website and website.startswith("http"):
            st.markdown(f"🌐 [{escape(website)}]({website})")
        summary = info.get("longBusinessSummary")
        if summary:
            with st.expander("Company description", expanded=False):
                st.write(summary.replace("$", "\\$"))
        else:
            st.caption("No business description available.")

        related = get_related(info)
        if related.has_data:
            section_title("Related companies", "same-industry search results")
            cols = st.columns(3)
            for i, r in enumerate(related.data):
                if cols[i % 3].button(r["symbol"], key=f"rel_{r['symbol']}", help=r["name"], width="stretch"):
                    select_symbol(r["symbol"])
                    st.rerun()

    _compare_panel(symbol, info)

    visible = {label: value for label, value in quote_items + valuation_items + other_items}
    return {"section": "Summary", "filters": {"sparkline_period": choice}, "visible": visible}


def _compare_panel(symbol: str, info: dict) -> None:
    with st.expander("📊 Compare with other companies", expanded=bool(st.session_state.get("compare_symbols"))):
        raw = st.text_input("Tickers to compare (comma-separated, up to 5)", key="compare_input",
                            placeholder="e.g. MSFT, GOOGL, AMZN")
        others = [normalize_symbol(s) for s in raw.split(",") if s.strip()]
        invalid = [s for s in others if not is_valid_symbol(s)]
        others = [s for s in others if is_valid_symbol(s) and s != symbol][:5]
        st.session_state.compare_symbols = others
        if invalid:
            st.warning("Ignored invalid tickers: " + ", ".join(invalid))
        if not others:
            st.caption("Enter one or more tickers to see a side-by-side comparison.")
            return
        infos = {symbol: info}
        failed = []
        for s in others:
            res = market_data.get_info(s)
            if res.has_data:
                infos[s] = res.data
            else:
                failed.append(s)
        if failed:
            st.warning("No data for: " + ", ".join(failed))
        table = metrics.compare(infos)
        display = pd.DataFrame(
            {s: [fmt_value(table.at[m, s], metrics.COMPARISON_FIELDS[m][1]) for m in table.index] for s in table.columns},
            index=table.index,
        )
        display.insert(0, "Metric", display.index)
        data_table(display, height=min(36 * (len(display) + 1), 760))
        currencies = {s: i.get("currency") for s, i in infos.items()}
        if len(set(c for c in currencies.values() if c)) > 1:
            st.warning("Companies report in different currencies: " + ", ".join(f"{s}: {c}" for s, c in currencies.items()) +
                       ". Absolute values are not directly comparable.")
        if st.button("Ask the AI analyst to compare these", icon="🤖", key="ai_compare"):
            from components.sidebar import ask

            ask(f"Compare {symbol} with {', '.join(others)} on valuation, profitability, growth and balance-sheet strength.")
