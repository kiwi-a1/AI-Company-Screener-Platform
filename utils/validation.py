"""Input validation for symbols and history requests (Yahoo interval limits)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

# Yahoo symbols: letters/digits plus . - ^ = (e.g. BRK-B, RELIANCE.NS, ^GSPC, EURUSD=X)
_SYMBOL_RE = re.compile(r"^[A-Z0-9^][A-Z0-9.\-=^]{0,19}$")

INTERVALS = {
    "1 minute": "1m",
    "5 minutes": "5m",
    "15 minutes": "15m",
    "30 minutes": "30m",
    "1 hour": "1h",
    "Daily": "1d",
    "Weekly": "1wk",
    "Monthly": "1mo",
}

# Maximum lookback (days from today) Yahoo serves for intraday intervals.
INTRADAY_MAX_DAYS = {"1m": 7, "2m": 59, "5m": 59, "15m": 59, "30m": 59, "60m": 729, "90m": 59, "1h": 729}


def normalize_symbol(symbol: str | None) -> str:
    return (symbol or "").strip().upper()


def is_valid_symbol(symbol: str | None) -> bool:
    return bool(_SYMBOL_RE.match(normalize_symbol(symbol)))


@dataclass
class HistoryRequest:
    start: date
    end: date
    interval: str
    warning: str | None = None


def validate_history_request(start: date, end: date, interval: str, today: date | None = None) -> HistoryRequest:
    """Clamp a requested range to what the source can serve and explain any change."""
    today = today or date.today()
    if interval not in set(INTERVALS.values()):
        raise ValueError(f"Unsupported interval: {interval}")
    warning = None
    if end > today:
        end = today
    if start > end:
        start, end = end, start
        warning = "Start date was after end date; the range was swapped."
    max_days = INTRADAY_MAX_DAYS.get(interval)
    if max_days is not None:
        earliest = today - timedelta(days=max_days)
        if start < earliest:
            start = earliest
            warning = (
                f"Yahoo only provides {interval} data for roughly the last {max_days} days; "
                f"the start date was moved to {earliest.isoformat()}."
            )
    return HistoryRequest(start=start, end=end, interval=interval, warning=warning)


def preset_range(preset: str, today: date | None = None) -> tuple[date | None, date]:
    """Return (start, end) for a preset. start=None means 'max available'."""
    today = today or date.today()
    days = {"1D": 1, "5D": 5, "1M": 30, "3M": 91, "6M": 182, "1Y": 365, "2Y": 730, "5Y": 1826, "10Y": 3652}
    if preset == "YTD":
        return date(today.year, 1, 1), today
    if preset == "Max":
        return None, today
    if preset not in days:
        raise ValueError(f"Unknown preset: {preset}")
    return today - timedelta(days=days[preset]), today
