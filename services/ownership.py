"""Ownership records: major holders breakdown, top institutional and mutual-fund holders.

These are periodic filings with a 'Date Reported' — never real-time transactions.
"""
from __future__ import annotations

import yfinance as yf

import config
from services.cache import DataResult, fetch
from utils.normalization import normalize_holder_table, normalize_major_holders
from utils.validation import normalize_symbol


def get_holders(symbol: str) -> DataResult:
    """Data: {'major': dict, 'institutional': DataFrame, 'mutualfund': DataFrame}."""
    symbol = normalize_symbol(symbol)

    def load() -> dict:
        t = yf.Ticker(symbol)
        return {
            "major": normalize_major_holders(t.get_major_holders()),
            "institutional": normalize_holder_table(t.get_institutional_holders()),
            "mutualfund": normalize_holder_table(t.get_mutualfund_holders()),
        }

    return fetch(f"holders:{symbol}", config.TTL["holders"], load)
