"""Annual / quarterly income statement, balance sheet and cash flow."""
from __future__ import annotations

import yfinance as yf

import config
from services.cache import DataResult, fetch
from utils.normalization import Statement, normalize_statement
from utils.validation import normalize_symbol

_LOADERS = {
    "income": "get_income_stmt",
    "balance": "get_balance_sheet",
    "cashflow": "get_cash_flow",
}
FREQUENCIES = {"annual": "yearly", "quarterly": "quarterly"}


def get_statement(symbol: str, kind: str, frequency: str = "annual") -> DataResult:
    """kind: income|balance|cashflow; frequency: annual|quarterly. Data is a Statement."""
    if kind not in _LOADERS:
        raise ValueError(f"Unknown statement kind: {kind}")
    if frequency not in FREQUENCIES:
        raise ValueError(f"Unknown frequency: {frequency}")
    symbol = normalize_symbol(symbol)

    def load() -> Statement:
        ticker = yf.Ticker(symbol)
        df = getattr(ticker, _LOADERS[kind])(pretty=False, freq=FREQUENCIES[frequency])
        return normalize_statement(df, kind, frequency)

    return fetch(f"stmt:{symbol}:{kind}:{frequency}", config.TTL["statements"], load)
