"""Central configuration, read from environment variables (.env supported)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    # Streamlit Cloud exposes secrets via st.secrets; fall back to it when present.
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return default


ANALYST_MODEL = _get("ANALYST_MODEL", "claude-opus-5-5")
ANALYST_EFFORT = _get("ANALYST_EFFORT", "medium")
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-flash-latest")
QUOTE_REFRESH_SECONDS = int(_get("QUOTE_REFRESH_SECONDS", "30"))
BENCHMARK_SYMBOL = _get("BENCHMARK_SYMBOL", "^GSPC")
DEFAULT_SYMBOL = _get("DEFAULT_SYMBOL", "AAPL")
SOURCE_NAME = "Yahoo Finance (via yfinance)"

# Cache time-to-live per data type, in seconds.
TTL = {
    "quote": QUOTE_REFRESH_SECONDS,
    "search": 3600,
    "history": 15 * 60,
    "news": 10 * 60,
    "statements": 6 * 3600,
    "holders": 6 * 3600,
    "actions": 6 * 3600,
}


def anthropic_api_key() -> str | None:
    return _get("ANTHROPIC_API_KEY", "") or None


def gemini_api_key() -> str | None:
    return _get("GEMINI_API_KEY", "") or _get("GOOGLE_API_KEY", "") or None


def analyst_provider() -> str | None:
    """Claude if an Anthropic key is set, otherwise Gemini, otherwise None (chat disabled)."""
    if anthropic_api_key():
        return "anthropic"
    if gemini_api_key():
        return "gemini"
    return None
