"""News cards: thumbnail, headline link, publisher, time, summary, related tickers."""
from __future__ import annotations

from html import escape

import streamlit as st

from utils.formatting import fmt_age, fmt_date


def news_card(item: dict) -> str:
    title = escape(item["title"])
    headline = f'<a href="{escape(item["url"])}" target="_blank" rel="noopener noreferrer">{title}</a>' if item.get("url") else title
    thumb = f'<img class="news-thumb" src="{escape(item["thumbnail"])}" alt="" loading="lazy"/>' if item.get("thumbnail") else '<div class="news-thumb empty"></div>'
    meta = [escape(item.get("publisher") or "Unknown publisher")]
    if item.get("published"):
        meta.append(f'<span title="{escape(fmt_date(item["published"], with_time=True))}">{escape(fmt_age(item["published"]))}</span>')
    meta.append(f'<span class="tag">{escape(item.get("category") or "News")}</span>')
    tickers = "".join(f'<span class="ticker">{escape(t)}</span>' for t in item.get("tickers", [])[:6])
    summary = f'<div class="news-summary">{escape(item["summary"][:280])}{"…" if len(item["summary"]) > 280 else ""}</div>' if item.get("summary") else ""
    return (
        f'<div class="news-card">{thumb}<div class="news-body">'
        f'<div class="news-title">{headline}</div>'
        f'<div class="news-meta">{" · ".join(meta)}</div>{summary}'
        f'{f"<div class=news-tickers>{tickers}</div>" if tickers else ""}</div></div>'
    )


def news_feed(items: list[dict]) -> None:
    st.markdown("".join(news_card(i) for i in items), unsafe_allow_html=True)
