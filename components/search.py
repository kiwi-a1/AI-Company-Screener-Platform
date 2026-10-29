"""Global company search: by ticker or company name."""
from __future__ import annotations

import streamlit as st

from services.market_data import search_symbols
from utils.validation import is_valid_symbol, normalize_symbol


def select_symbol(symbol: str) -> None:
    symbol = normalize_symbol(symbol)
    st.session_state.symbol = symbol
    recent = [s for s in st.session_state.get("recent", []) if s != symbol]
    st.session_state.recent = [symbol, *recent][:8]
    st.session_state.search_results = None


def search_bar() -> None:
    with st.form("search_form", clear_on_submit=True, border=False):
        c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
        query = c1.text_input(
            "Search company or ticker",
            placeholder="Search by company name or ticker — e.g. Apple, MSFT, RELIANCE.NS",
            label_visibility="collapsed",
        )
        submitted = c2.form_submit_button("Search", icon="🔍", width="stretch")
    if submitted and query.strip():
        res = search_symbols(query)
        results = res.data or []
        exact = [r for r in results if r["symbol"] == normalize_symbol(query)]
        if exact:
            select_symbol(exact[0]["symbol"])
            st.rerun()
        if results:
            st.session_state.search_results = results
        elif is_valid_symbol(query):
            # Search unavailable or no match: try the text as a ticker directly.
            select_symbol(query)
            st.rerun()
        else:
            st.session_state.search_results = []
            st.warning(f"No matches for “{query}”. {res.error or ''}")

    results = st.session_state.get("search_results")
    if results:
        st.caption("Select a result:")
        cols = st.columns(min(4, len(results)))
        for i, r in enumerate(results):
            label = f"{r['symbol']} · {r['name'][:28]}" + (f" ({r['exchange']})" if r.get("exchange") else "")
            if cols[i % len(cols)].button(label, key=f"res_{r['symbol']}_{i}", width="stretch",
                                          help=f"{r.get('type') or ''} {r.get('industry') or ''}".strip() or None):
                select_symbol(r["symbol"])
                st.rerun()
        if st.button("Clear results", key="clear_results", type="tertiary"):
            st.session_state.search_results = None
            st.rerun()

    recent = [s for s in st.session_state.get("recent", []) if s != st.session_state.get("symbol")]
    if recent:
        choice = st.pills("Recent", recent, key=f"recent_pills_{st.session_state.get('symbol')}", label_visibility="collapsed")
        if choice:
            select_symbol(choice)
            st.rerun()
