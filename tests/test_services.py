"""Data services with yfinance mocked: caching, retries, stale fallback, missing data."""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from services import cache, financials, history, market_data, news, ownership


@pytest.fixture(autouse=True)
def _clear_cache(monkeypatch):
    cache.invalidate()
    monkeypatch.setattr(cache.time, "sleep", lambda s: None)
    yield
    cache.invalidate()


def test_fetch_caches_and_retries():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("boom")
        return 42

    r = cache.fetch("k", 60, flaky, sleep=lambda s: None)
    assert r.data == 42 and r.error is None and calls["n"] == 2
    r2 = cache.fetch("k", 60, flaky)
    assert r2.cached and calls["n"] == 2


def test_fetch_stale_fallback_and_error():
    cache.fetch("s", 60, lambda: "good")
    cache._store["s"].stored_at -= 1000  # expire
    r = cache.fetch("s", 60, lambda: (_ for _ in ()).throw(TimeoutError("slow")), sleep=lambda s: None)
    assert r.data == "good" and r.stale and "TimeoutError" in r.error and r.ok
    r = cache.fetch("never", 60, lambda: (_ for _ in ()).throw(ValueError("x")), retries=0)
    assert r.data is None and not r.ok and not r.has_data


def _ticker(**attrs):
    t = MagicMock()
    for k, v in attrs.items():
        getattr(t, k).return_value = v
    return t


def test_get_info_unknown_symbol(monkeypatch):
    monkeypatch.setattr(market_data.yf, "Ticker", lambda s: _ticker(get_info={"trailingPegRatio": None}))
    r = market_data.get_info("zzzz")
    assert r.data is None and "SymbolNotFound" in r.error


def test_get_info_ok(monkeypatch):
    monkeypatch.setattr(market_data.yf, "Ticker",
                        lambda s: _ticker(get_info={"symbol": "AAPL", "longName": "Apple", "regularMarketPrice": 200,
                                                    "regularMarketPreviousClose": 190}))
    r = market_data.get_info("aapl")
    assert r.data["name"] == "Apple" and r.data["change"] == 10


def test_history_adds_adjusted_column(monkeypatch):
    idx = pd.date_range("2025-01-01", periods=3)
    df = pd.DataFrame({"Open": [1, 2, 3], "High": [1, 2, 3], "Low": [1, 2, 3], "Close": [1, 2, 3],
                       "Adj Close": [0.9, 1.9, 2.9], "Volume": [10, 20, 30], "Dividends": [0, 0, 0]}, index=idx)
    monkeypatch.setattr(history.yf, "Ticker", lambda s: _ticker(history=df))
    r = history.get_history_period("AAPL", "1mo")
    assert list(r.data.columns) == history.HISTORY_COLUMNS and r.data.index.name == "Date"


def test_news_merges_tabs(monkeypatch):
    def get_news(count, tab):
        if tab == "news":
            return [{"id": "1", "content": {"title": "A", "pubDate": "2025-01-02T00:00:00Z"}}]
        return [{"id": "2", "content": {"title": "PR", "pubDate": "2025-01-03T00:00:00Z"}},
                {"id": "1", "content": {"title": "A", "pubDate": "2025-01-02T00:00:00Z"}}]

    t = MagicMock()
    t.get_news.side_effect = get_news
    monkeypatch.setattr(news.yf, "Ticker", lambda s: t)
    items = news.get_news("AAPL").data
    assert [i["title"] for i in items] == ["PR", "A"]
    assert {i["category"] for i in items} == {"Press Release"}


def test_news_one_tab_failing(monkeypatch):
    t = MagicMock()
    t.get_news.side_effect = lambda count, tab: [{"id": "1", "content": {"title": "A"}}] if tab == "news" else (_ for _ in ()).throw(RuntimeError())
    monkeypatch.setattr(news.yf, "Ticker", lambda s: t)
    assert len(news.get_news("AAPL").data) == 1


def test_statement_and_holders(monkeypatch):
    df = pd.DataFrame({pd.Timestamp("2024-12-31"): [100.0]}, index=["TotalRevenue"])
    t = _ticker(get_income_stmt=df, get_major_holders=pd.DataFrame(), get_institutional_holders=None,
                get_mutualfund_holders=pd.DataFrame())
    monkeypatch.setattr(financials.yf, "Ticker", lambda s: t)
    monkeypatch.setattr(ownership.yf, "Ticker", lambda s: t)
    stmt = financials.get_statement("AAPL", "income", "annual").data
    assert stmt.get("TotalRevenue") == 100.0
    h = ownership.get_holders("AAPL").data
    assert h["institutional"].empty and h["major"]["insidersPercentHeld"] is None
    with pytest.raises(ValueError):
        financials.get_statement("AAPL", "bogus")
