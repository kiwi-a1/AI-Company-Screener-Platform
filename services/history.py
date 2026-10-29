"""Historical OHLCV prices, dividends and splits."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import yfinance as yf

import config
from services.cache import DataResult, fetch
from utils.validation import normalize_symbol

HISTORY_COLUMNS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]


def _clean_history(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    data = df.copy()
    if "Adj Close" not in data.columns and "Close" in data.columns:
        data["Adj Close"] = pd.NA  # unadjusted request without adj column -> explicit unavailable
    keep = [c for c in HISTORY_COLUMNS if c in data.columns]
    data = data[keep]
    data.index = pd.to_datetime(data.index)
    data.index.name = "Date"
    return data.dropna(how="all", subset=[c for c in ["Open", "High", "Low", "Close"] if c in data.columns])


def get_history(symbol: str, start: date | None, end: date, interval: str = "1d") -> DataResult:
    """Unadjusted OHLC plus 'Adj Close' (auto_adjust=False). start=None means max history."""
    symbol = normalize_symbol(symbol)
    # yfinance's `end` is exclusive; include the end date.
    end_exclusive = end + timedelta(days=1)

    def load() -> pd.DataFrame:
        t = yf.Ticker(symbol)
        if start is None:
            df = t.history(period="max", interval=interval, auto_adjust=False, actions=False)
        else:
            df = t.history(start=start, end=end_exclusive, interval=interval, auto_adjust=False, actions=False)
        return _clean_history(df)

    return fetch(f"history:{symbol}:{start}:{end}:{interval}", config.TTL["history"], load)


def get_history_period(symbol: str, period: str = "1y", interval: str = "1d") -> DataResult:
    symbol = normalize_symbol(symbol)

    def load() -> pd.DataFrame:
        return _clean_history(yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False, actions=False))

    return fetch(f"history_p:{symbol}:{period}:{interval}", config.TTL["history"], load)


def get_dividends(symbol: str) -> DataResult:
    symbol = normalize_symbol(symbol)

    def load() -> pd.Series:
        s = yf.Ticker(symbol).get_dividends(period="max")
        return s if s is not None else pd.Series(dtype="float64")

    return fetch(f"dividends:{symbol}", config.TTL["actions"], load)


def get_splits(symbol: str) -> DataResult:
    symbol = normalize_symbol(symbol)

    def load() -> pd.Series:
        s = yf.Ticker(symbol).get_splits(period="max")
        return s if s is not None else pd.Series(dtype="float64")

    return fetch(f"splits:{symbol}", config.TTL["actions"], load)
