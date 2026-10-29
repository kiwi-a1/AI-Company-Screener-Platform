"""Loading, empty, error and data-freshness states shared by every section."""
from __future__ import annotations

import streamlit as st

from services.cache import DataResult, invalidate
from utils.formatting import fmt_age


def source_caption(result: DataResult | None, extra: str = "") -> None:
    """'Source · retrieved 12:01 UTC (3 min ago) · cached' + stale warning if a refresh failed."""
    if result is None or result.fetched_at is None:
        return
    parts = [f"Source: {result.source}", f"retrieved {result.fetched_at.strftime('%b %d %H:%M UTC')} ({fmt_age(result.fetched_at)})"]
    if result.cached:
        parts.append("cached")
    if extra:
        parts.append(extra)
    st.caption(" · ".join(parts))
    if result.stale:
        st.warning(f"Showing the last successfully retrieved data. The latest refresh failed: {result.error}", icon="⚠️")


def retry_button(cache_prefix: str, key: str) -> None:
    if st.button("Retry", key=f"retry_{key}", icon="🔄"):
        invalidate(cache_prefix)
        st.rerun()


def require(result: DataResult, what: str, cache_prefix: str, key: str) -> bool:
    """Render error/empty state when there's nothing to show. Returns True if data can be rendered."""
    if result.has_data:
        return True
    if result.error and not result.stale:
        st.error(f"Could not load {what} from Yahoo Finance. {result.error}", icon="🚫")
        retry_button(cache_prefix, key)
    else:
        empty_state(f"Yahoo Finance has no {what} available for this symbol.")
    return False


def empty_state(message: str) -> None:
    st.info(message, icon="ℹ️")


def skeleton(lines: int = 3) -> None:
    """Lightweight placeholder while data loads."""
    for _ in range(lines):
        st.markdown('<div class="skeleton"></div>', unsafe_allow_html=True)
