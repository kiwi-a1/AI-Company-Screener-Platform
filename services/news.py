"""Company news from Yahoo Finance (news + press releases tabs)."""
from __future__ import annotations

import yfinance as yf

import config
from services.cache import DataResult, fetch
from utils.normalization import normalize_news
from utils.validation import normalize_symbol

TABS = {"news": "News", "press releases": "Press Release"}


def _load_news(symbol: str, count: int) -> list[dict]:
    items: dict[str, dict] = {}
    errors = []
    for tab, category in TABS.items():
        try:
            raw = yf.Ticker(symbol).get_news(count=count, tab=tab)  # fresh Ticker: get_news memoizes per object
        except Exception as exc:  # one tab failing should not hide the other
            errors.append(exc)
            continue
        for item in normalize_news(raw, category):
            # Press-release tab wins when an article appears in both.
            if item["id"] not in items or category == "Press Release":
                items[item["id"]] = item
    if errors and not items:
        raise errors[0]
    return sorted(items.values(), key=lambda i: (i["published"] is not None, i["published"]), reverse=True)


def get_news(symbol: str, count: int = 25) -> DataResult:
    symbol = normalize_symbol(symbol)
    return fetch(f"news:{symbol}:{count}", config.TTL["news"], lambda: _load_news(symbol, count))
