"""Persistent market header: identity + live quote, refreshed on a timer via st.fragment."""
from __future__ import annotations

from html import escape

import streamlit as st

import config
from services.market_data import get_info
from utils.formatting import UNAVAILABLE, fmt_age, fmt_change, fmt_date, fmt_price, is_missing

MARKET_STATES = {
    "REGULAR": ("Market open", "open"),
    "PRE": ("Pre-market", "ext"),
    "PREPRE": ("Pre-market", "ext"),
    "POST": ("After hours", "ext"),
    "POSTPOST": ("Market closed", "closed"),
    "CLOSED": ("Market closed", "closed"),
}


def _change_class(change) -> str:
    if is_missing(change) or change == 0:
        return "flat"
    return "up" if change > 0 else "down"


def header_html(info: dict, retrieved_label: str) -> str:
    currency = info.get("currency")
    state_label, state_cls = MARKET_STATES.get((info.get("marketState") or "").upper(), ("", "closed"))
    exchange = info.get("fullExchangeName") or info.get("exchange") or ""
    ident = " · ".join(escape(x) for x in [info.get("symbol") or "", exchange, currency or ""] if x)

    ext_html = ""
    for key, label in (("preMarketPrice", "Pre-market"), ("postMarketPrice", "After hours")):
        price = info.get(key)
        if is_missing(price):
            continue
        prefix = "preMarket" if key.startswith("pre") else "postMarket"
        chg, pct = info.get(f"{prefix}Change"), info.get(f"{prefix}ChangePercent")
        t = info.get(f"{prefix}Time")
        ext_html += (
            f'<div class="ext-quote"><span class="ext-label">{label}</span> '
            f'<span class="ext-price">{escape(fmt_price(price))}</span> '
            f'<span class="{_change_class(chg)}">{escape(fmt_change(chg, pct))}</span>'
            f'{f" <span class=ext-time>{escape(fmt_date(t, with_time=True))}</span>" if t else ""}</div>'
        )

    market_time = info.get("regularMarketTime")
    as_of = f"As of {fmt_date(market_time, with_time=True)}" if market_time else ""
    return f"""
<div class="market-header">
  <div class="mh-left">
    <div class="mh-name">{escape(info.get("name") or info.get("symbol") or "")}</div>
    <div class="mh-ident">{ident}{f' · <span class="state {state_cls}">{state_label}</span>' if state_label else ''}</div>
  </div>
  <div class="mh-right">
    <div class="mh-quote">
      <span class="mh-price">{escape(fmt_price(info.get("price")))}</span>
      <span class="mh-change {_change_class(info.get("change"))}">{escape(fmt_change(info.get("change"), info.get("change_pct")))}</span>
    </div>
    {ext_html}
    <div class="mh-time">{escape(as_of)}{" · " if as_of else ""}{escape(retrieved_label)}</div>
  </div>
</div>"""


def render_header(symbol: str) -> dict | None:
    res = get_info(symbol)
    if not res.has_data:
        st.error(f"Could not load a quote for **{symbol}**. {res.error or ''}", icon="🚫")
        return None
    label = f"Retrieved {fmt_age(res.fetched_at)} · Yahoo Finance quotes may be delayed"
    if res.stale:
        label += " · refresh failed, showing last good data"
    st.markdown(header_html(res.data, label), unsafe_allow_html=True)
    return res.data


def live_header(symbol: str, live: bool) -> None:
    """Re-render only the header every QUOTE_REFRESH_SECONDS when live updates are on."""
    if live:
        @st.fragment(run_every=config.QUOTE_REFRESH_SECONDS)
        def _live():
            render_header(symbol)

        _live()
    else:
        render_header(symbol)


__all__ = ["live_header", "render_header", "header_html", "UNAVAILABLE"]
