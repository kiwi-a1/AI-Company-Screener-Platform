"""Multi-Company Stock & Corporate Financial Analysis Platform — Streamlit entry point.

Run:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

import config
from components.global_header import live_header
from components.search import search_bar, select_symbol
from components.sidebar import render_sidebar
from sections import financials, historical_data, holders, news, statistics, summary
from services.cache import invalidate
from services.market_data import get_info
from utils.validation import is_valid_symbol, normalize_symbol

st.set_page_config(page_title="Equity Research Workspace", page_icon="📈", layout="wide",
                   initial_sidebar_state="expanded")

SECTIONS = {
    "Summary": summary,
    "News": news,
    "Statistics": statistics,
    "Historical Data": historical_data,
    "Financials": financials,
    "Holders": holders,
}
SECTION_ICONS = {"Summary": "🏠", "News": "📰", "Statistics": "📐", "Historical Data": "🕰️", "Financials": "🧾", "Holders": "👥"}

CSS = """
<style>
section[data-testid="stSidebar"] { width: 440px !important; }
section[data-testid="stSidebar"] [data-testid="stChatMessage"] { padding: .5rem .6rem; }
.block-container { padding-top: 3.2rem; padding-bottom: 2rem; }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], [data-testid="stToolbarActions"], [data-testid="stAppDeployButton"],
[data-testid="stMainMenu"], [data-testid="stStatusWidget"] { display: none !important; }
.market-header { display:flex; justify-content:space-between; align-items:flex-end; gap:1rem; flex-wrap:wrap;
  padding:.9rem 1.1rem; border-radius:12px; background:linear-gradient(135deg,#161B26,#1B2333);
  border:1px solid #263043; margin:.4rem 0 .6rem 0; }
.mh-name { font-size:1.55rem; font-weight:700; line-height:1.2; }
.mh-ident { color:#9AA4B2; font-size:.9rem; margin-top:.15rem; }
.mh-right { text-align:right; }
.mh-price { font-size:2rem; font-weight:700; margin-right:.5rem; }
.mh-change { font-size:1.1rem; font-weight:600; }
.up { color:#26A69A; } .down { color:#EF5350; } .flat { color:#9AA4B2; }
.ext-quote { font-size:.88rem; color:#C9D1DC; } .ext-label { color:#9AA4B2; } .ext-time { color:#6B7585; font-size:.78rem; }
.mh-time { color:#6B7585; font-size:.78rem; margin-top:.2rem; }
.state { padding:1px 7px; border-radius:9px; font-size:.75rem; }
.state.open { background:rgba(38,166,154,.18); color:#26A69A; } .state.ext { background:rgba(245,166,35,.18); color:#F5A623; }
.state.closed { background:rgba(154,164,178,.15); color:#9AA4B2; }
.card-grid { display:grid; grid-template-columns:repeat(var(--cols), minmax(0,1fr)); gap:.5rem; margin-bottom:.8rem; }
@media (max-width: 900px) { .card-grid { grid-template-columns:repeat(2, minmax(0,1fr)); } }
.card { background:#161B26; border:1px solid #232B3A; border-radius:10px; padding:.55rem .7rem; }
.card-label { color:#9AA4B2; font-size:.75rem; text-transform:uppercase; letter-spacing:.02em; }
.card-value { font-size:1.02rem; font-weight:600; margin-top:.1rem; word-break:break-word; }
.na { color:#6B7585 !important; cursor:help; }
.section-title { font-size:1.05rem; font-weight:650; margin:.4rem 0 .45rem 0; }
.section-sub { color:#7D8796; font-weight:400; font-size:.8rem; margin-left:.5rem; }
.stat-table { background:#161B26; border:1px solid #232B3A; border-radius:10px; padding:.6rem .8rem; margin-bottom:.9rem; }
.stat-title { font-weight:650; margin-bottom:.3rem; }
.stat-table table { width:100%; border-collapse:collapse; font-size:.9rem; }
.stat-table td { padding:.32rem 0; border-bottom:1px solid #222A38; }
.stat-table tr:last-child td { border-bottom:none; }
.stat-table td:last-child { text-align:right; font-weight:600; }
.news-card { display:flex; gap:.8rem; padding:.7rem 0; border-bottom:1px solid #222A38; }
.news-thumb { width:110px; height:74px; object-fit:cover; border-radius:8px; flex-shrink:0; background:#1B2333; }
.news-title a, .news-title { color:#E6EAF2; font-weight:600; text-decoration:none; font-size:.98rem; }
.news-title a:hover { color:#4C9AFF; }
.news-meta { color:#8A94A3; font-size:.8rem; margin:.2rem 0; }
.news-summary { color:#B5BDC9; font-size:.85rem; }
.tag { background:#22304A; color:#8FB8FF; padding:0 6px; border-radius:6px; font-size:.72rem; }
.ticker { background:#1F2633; color:#C9D1DC; padding:0 6px; border-radius:6px; font-size:.72rem; margin-right:4px; }
.news-tickers { margin-top:.25rem; }
.ctx-badge { font-size:.8rem; color:#9AA4B2; background:#161B26; border:1px solid #232B3A; border-radius:8px;
  padding:.3rem .6rem; margin-bottom:.6rem; }
.skeleton { height:14px; border-radius:6px; margin:6px 0; background:linear-gradient(90deg,#1B2333 25%,#232D40 50%,#1B2333 75%);
  background-size:200% 100%; animation:sk 1.2s infinite; }
@keyframes sk { 0% { background-position:200% 0 } 100% { background-position:-200% 0 } }
.footer { color:#6B7585; font-size:.75rem; margin-top:2rem; }
</style>
"""


def _init_state() -> None:
    params = st.query_params
    if "symbol" not in st.session_state:
        candidate = normalize_symbol(params.get("s", config.DEFAULT_SYMBOL))
        select_symbol(candidate if is_valid_symbol(candidate) else config.DEFAULT_SYMBOL)
    if "section" not in st.session_state:
        tab = params.get("tab")
        st.session_state.section = tab if tab in SECTIONS else "Summary"
    st.session_state.setdefault("live_quotes", True)


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    _init_state()

    top_left, top_right = st.columns([6, 2], vertical_alignment="top")
    with top_left:
        search_bar()
    with top_right:
        c1, c2 = st.columns(2, vertical_alignment="center")
        c1.toggle("Live", key="live_quotes", help=f"Live quote: refresh the header every {config.QUOTE_REFRESH_SECONDS}s")
        if c2.button("Refresh", icon="🔄", help="Clear cached data for this company", width="stretch"):
            invalidate(f"info:{st.session_state.symbol}")
            for prefix in ("history", "news", "stmt", "holders", "dividends", "splits"):
                invalidate(f"{prefix}:{st.session_state.symbol}")
            st.rerun()

    symbol = st.session_state.symbol
    live_header(symbol, st.session_state.live_quotes)

    info_result = get_info(symbol)
    section = st.segmented_control(
        "Section", list(SECTIONS), key="section", format_func=lambda s: f"{SECTION_ICONS[s]} {s}",
        label_visibility="collapsed",
    ) or "Summary"
    st.query_params.update({"s": symbol, "tab": section})

    page_context = {"section": section, "filters": {}, "visible": {}}
    info = info_result.data if info_result.has_data else None
    if info is None:
        st.error(
            f"No data is available for **{symbol}**. Check the ticker (Yahoo format, e.g. `BRK-B`, `RELIANCE.NS`, `^GSPC`) "
            f"or try again later." + (f"\n\nDetails: `{info_result.error}`" if info_result.error else ""),
            icon="🚫",
        )
    else:
        if info.get("_partial"):
            st.warning("Yahoo Finance returned limited data for this company right now (detailed profile and "
                       "valuation fields were unavailable), so some values show “—”. Use **Refresh** to try again.",
                       icon="⚠️")
        try:
            page_context = SECTIONS[section].render(symbol, info, info_result) or page_context
        except Exception as exc:  # never let one section take down the app or the chat
            st.error(f"Something went wrong rendering {section}: {type(exc).__name__}: {exc}", icon="💥")
            with st.expander("Technical details"):
                st.exception(exc)

    st.markdown(
        '<div class="footer">Data: Yahoo Finance via the unofficial yfinance library — quotes may be delayed and '
        "fields vary by ticker; check Yahoo's terms before redistributing data. Calculated metrics are derived "
        "from reported values. Nothing here is investment advice.</div>",
        unsafe_allow_html=True,
    )

    render_sidebar(symbol, info, page_context)


main()
