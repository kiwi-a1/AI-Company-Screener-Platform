"""Display formatting. Every formatter returns UNAVAILABLE for missing values, never "0"."""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any

UNAVAILABLE = "—"

_SUFFIXES = [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]

UNIT_DIVISORS = {"Raw": 1.0, "Thousands": 1e3, "Millions": 1e6, "Billions": 1e9}


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return True
    try:
        import pandas as pd

        if value is pd.NaT or (not isinstance(value, (str, bytes)) and pd.isna(value)):
            return True
    except (TypeError, ValueError):
        pass
    return False


def fmt_large(value: Any, prefix: str = "", decimals: int = 2) -> str:
    """1234567 -> '1.23M'. Negative values keep their sign."""
    if is_missing(value):
        return UNAVAILABLE
    v = float(value)
    sign = "-" if v < 0 else ""
    a = abs(v)
    for threshold, suffix in _SUFFIXES:
        if a >= threshold:
            return f"{sign}{prefix}{a / threshold:,.{decimals}f}{suffix}"
    return f"{sign}{prefix}{a:,.{decimals}f}"


def fmt_number(value: Any, decimals: int = 2) -> str:
    if is_missing(value):
        return UNAVAILABLE
    return f"{float(value):,.{decimals}f}"


def fmt_int(value: Any) -> str:
    if is_missing(value):
        return UNAVAILABLE
    return f"{int(round(float(value))):,}"


def fmt_pct(value: Any, decimals: int = 2, ratio: bool = True, signed: bool = False) -> str:
    """Format a percentage. `ratio=True` means 0.123 -> 12.30%."""
    if is_missing(value):
        return UNAVAILABLE
    v = float(value) * (100 if ratio else 1)
    return f"{v:+,.{decimals}f}%" if signed else f"{v:,.{decimals}f}%"


def fmt_price(value: Any, currency: str | None = None, decimals: int = 2) -> str:
    if is_missing(value):
        return UNAVAILABLE
    text = f"{float(value):,.{decimals}f}"
    return f"{text} {currency}" if currency else text


def fmt_change(change: Any, pct: Any) -> str:
    """'+1.23 (+0.45%)' where pct is already in percent units."""
    if is_missing(change) and is_missing(pct):
        return UNAVAILABLE
    parts = []
    if not is_missing(change):
        parts.append(f"{float(change):+,.2f}")
    if not is_missing(pct):
        parts.append(f"({float(pct):+,.2f}%)")
    return " ".join(parts)


def to_datetime(value: Any) -> datetime | None:
    """Accept epoch seconds, ISO strings, datetime/date/Timestamp; return aware UTC datetime."""
    if is_missing(value):
        return None
    try:
        import pandas as pd

        if isinstance(value, (int, float)):
            # Yahoo uses epoch seconds; guard against milliseconds.
            seconds = float(value) / 1000 if float(value) > 1e11 else float(value)
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        ts = pd.Timestamp(value)
        if ts is pd.NaT:
            return None
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts.to_pydatetime()
    except (ValueError, TypeError, OverflowError):
        return None


def fmt_date(value: Any, with_time: bool = False) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%b %d, %Y")
    dt = to_datetime(value)
    if dt is None:
        return UNAVAILABLE
    return dt.strftime("%b %d, %Y %H:%M UTC") if with_time else dt.strftime("%b %d, %Y")


def fmt_age(dt: datetime | None, now: datetime | None = None) -> str:
    """Human 'x min ago' label for data timestamps."""
    if dt is None:
        return "unknown time"
    now = now or datetime.now(timezone.utc)
    seconds = max(0, int((now - dt).total_seconds()))
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return f"{seconds // 86400} d ago"


def fmt_value(value: Any, kind: str, currency: str | None = None) -> str:
    """Dispatch by metric kind: large, price, pct, ratio, int, date, text."""
    if kind == "large":
        return fmt_large(value)
    if kind == "money":
        return fmt_large(value, decimals=2) + (f" {currency}" if currency and not is_missing(value) else "")
    if kind == "price":
        return fmt_price(value)
    if kind == "pct":
        return fmt_pct(value)
    if kind == "pct_points":
        return fmt_pct(value, ratio=False)
    if kind == "ratio":
        return fmt_number(value)
    if kind == "int":
        return fmt_int(value)
    if kind == "date":
        return fmt_date(value)
    if is_missing(value) or value == "":
        return UNAVAILABLE
    return str(value)
