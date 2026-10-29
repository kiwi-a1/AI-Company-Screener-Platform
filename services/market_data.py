"""Company profile, quote fields and symbol search."""
from __future__ import annotations

import yfinance as yf

import config
from services.cache import DataResult, fetch
from utils.normalization import normalize_info
from utils.validation import normalize_symbol


class SymbolNotFound(Exception):
    pass


def _load_info(symbol: str) -> dict:
    raw = yf.Ticker(symbol).get_info()
    info = normalize_info(raw)
    # Yahoo returns a near-empty dict for unknown symbols.
    if not info or (info.get("price") is None and not info.get("name") and not info.get("quoteType")):
        raise SymbolNotFound(f"No quote data returned for '{symbol}'")
    info["symbol"] = info.get("symbol") or symbol
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
