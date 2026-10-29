"""Company profile, quote fields and symbol search."""
from __future__ import annotations

import yfinance as yf

import config
from services.cache import DataResult, fetch
from utils.normalization import normalize_info
from utils.validation import normalize_symbol


class SymbolNotFound(Exception):
    pass


# fast_info attribute -> Ticker.info key. fast_info uses Yahoo's chart endpoint, which keeps working
# when the detailed quoteSummary endpoint (Ticker.info) is blocked for cloud servers.
_FAST_INFO_MAP = {
    "last_price": "regularMarketPrice",
    "previous_close": "regularMarketPreviousClose",
    "open": "regularMarketOpen",
    "day_high": "regularMarketDayHigh",
    "day_low": "regularMarketDayLow",
    "last_volume": "regularMarketVolume",
    "year_high": "fiftyTwoWeekHigh",
    "year_low": "fiftyTwoWeekLow",
    "market_cap": "marketCap",
    "currency": "currency",
    "exchange": "exchange",
    "quote_type": "quoteType",
    "three_month_average_volume": "averageVolume",
    "ten_day_average_volume": "averageVolume10days",
    "fifty_day_average": "fiftyDayAverage",
    "two_hundred_day_average": "twoHundredDayAverage",
    "shares": "sharesOutstanding",
}


def _fast_info_fields(ticker) -> dict:
    out = {}
    try:
        fi = getattr(ticker, "fast_info", None)
    except Exception:
        return out
    if fi is None:
        return out
    for attr, key in _FAST_INFO_MAP.items():
        try:
            value = getattr(fi, attr, None)
        except Exception:  # each fast_info field may trigger its own request
            continue
        if value is not None:
            out[key] = value
    return out


def _load_info(symbol: str) -> dict:
    ticker = yf.Ticker(symbol)
    raw, info_error = {}, None
    try:
        raw = ticker.get_info() or {}
    except Exception as exc:
        info_error = exc
    info = normalize_info(raw)
    partial = False
    if info.get("price") is None:
        extra = _fast_info_fields(ticker)
        if extra:
            info = normalize_info({**extra, **{k: v for k, v in raw.items() if v is not None}, "symbol": symbol})
            partial = True
    # Yahoo returns a near-empty dict for unknown symbols.
    if not info or (info.get("price") is None and not info.get("name") and not info.get("quoteType")):
        if info_error is not None:
            raise info_error
        raise SymbolNotFound(f"No quote data returned for '{symbol}'")
    info["symbol"] = info.get("symbol") or symbol
    info["_partial"] = partial
    return info


def get_info(symbol: str) -> DataResult:
    """Profile + quote + key statistics (Ticker.info), cached for the live-quote TTL."""
    symbol = normalize_symbol(symbol)
    return fetch(f"info:{symbol}", config.TTL["quote"], lambda: _load_info(symbol))


def _load_search(query: str, max_results: int) -> list[dict]:
    quotes = yf.Search(query, max_results=max_results, news_count=0, lists_count=0).quotes or []
    results = []
    for q in quotes:
        symbol = q.get("symbol")
        if not symbol:
            continue
        results.append(
            {
                "symbol": symbol.upper(),
                "name": q.get("longname") or q.get("shortname") or symbol,
                "exchange": q.get("exchDisp") or q.get("exchange"),
                "type": q.get("typeDisp") or q.get("quoteType"),
                "sector": q.get("sectorDisp") or q.get("sector"),
                "industry": q.get("industryDisp") or q.get("industry"),
            }
        )
    return results


def search_symbols(query: str, max_results: int = 8) -> DataResult:
    query = (query or "").strip()
    if not query:
        return DataResult(data=[], fetched_at=None)
    return fetch(f"search:{query.lower()}:{max_results}", config.TTL["search"], lambda: _load_search(query, max_results))


def get_related(info: dict, limit: int = 6) -> DataResult:
    """Peers: search Yahoo by the company's industry and keep other equities."""
    industry = info.get("industry")
    symbol = info.get("symbol")
    if not industry:
        return DataResult(data=[], fetched_at=None)
    res = search_symbols(industry, max_results=15)
    if not res.has_data:
        return res
    peers = [r for r in res.data if r["symbol"] != symbol and (r.get("type") or "").lower() in ("equity", "")]
    return DataResult(data=peers[:limit], fetched_at=res.fetched_at, stale=res.stale, error=res.error, cached=res.cached)
