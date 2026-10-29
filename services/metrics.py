"""Deterministic financial calculations shared by the UI and the AI analyst's tools.

Rules: missing inputs -> None; zero/negative denominators where meaningless -> None.
Never return 0 as a stand-in for "unknown".
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable

import pandas as pd

from utils.normalization import Statement, clean_number


def safe_div(numerator: Any, denominator: Any) -> float | None:
    n, d = clean_number(numerator), clean_number(denominator)
    if n is None or d is None or d == 0:
        return None
    return n / d


def pct_change(current: Any, previous: Any) -> float | None:
    """Growth as a ratio (0.10 = +10%). Uses |previous| so growth from a negative base keeps direction."""
    c, p = clean_number(current), clean_number(previous)
    if c is None or p is None or p == 0:
        return None
    return (c - p) / abs(p)


def cagr(end_value: Any, start_value: Any, years: float) -> float | None:
    e, s = clean_number(end_value), clean_number(start_value)
    if e is None or s is None or years <= 0 or s <= 0 or e <= 0:
        return None
    return (e / s) ** (1 / years) - 1


def margin(part: Any, revenue: Any) -> float | None:
    r = clean_number(revenue)
    if r is None or r <= 0:
        return None
    return safe_div(part, r)


# --------------------------------------------------------------------------------------
# Price-based metrics
# --------------------------------------------------------------------------------------


def _price_series(history: pd.DataFrame, prefer_adjusted: bool = True) -> pd.Series:
    if history is None or history.empty:
        return pd.Series(dtype="float64")
    col = "Adj Close" if prefer_adjusted and "Adj Close" in history and history["Adj Close"].notna().any() else "Close"
    s = pd.to_numeric(history[col], errors="coerce").dropna()
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    return s.sort_index()


def period_return(history: pd.DataFrame, start: date, end: date | None = None) -> float | None:
    """Total return between the last close on/before `start` and the last close on/before `end`.

    Returns None if history does not reach back to `start` (no partial-period answers).
    """
    s = _price_series(history)
    if s.empty:
        return None
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) if end else s.index[-1]
    if s.index[0] > start_ts + pd.Timedelta(days=5):  # history doesn't cover the period
        return None
    base = s[s.index <= start_ts]
    base_value = base.iloc[-1] if not base.empty else s.iloc[0]
    last = s[s.index <= end_ts]
    if last.empty:
        return None
    return pct_change(last.iloc[-1], base_value)


def performance_table(
    history: pd.DataFrame, benchmark: pd.DataFrame | None, today: date | None = None
) -> list[dict]:
    """YTD / 1Y / 3Y / 5Y returns for the stock vs. benchmark (adjusted closes when available)."""
    today = today or date.today()
    s = _price_series(history)
    as_of = s.index[-1].date() if not s.empty else today
    periods = {
        "YTD": date(as_of.year, 1, 1) - timedelta(days=1),
        "1Y": as_of - timedelta(days=365),
        "3Y": as_of - timedelta(days=3 * 365),
        "5Y": as_of - timedelta(days=5 * 365),
    }
    rows = []
    for label, start in periods.items():
        stock = period_return(history, start, as_of)
        bench = period_return(benchmark, start, as_of) if benchmark is not None else None
        rows.append(
            {
                "period": label,
                "stock_return": stock,
                "benchmark_return": bench,
                "excess_return": (stock - bench) if stock is not None and bench is not None else None,
                "as_of": as_of,
            }
        )
    return rows


def moving_average(history: pd.DataFrame, window: int) -> pd.Series:
    s = _price_series(history, prefer_adjusted=False)
    return s.rolling(window, min_periods=window).mean()


def annualized_volatility(history: pd.DataFrame, periods_per_year: int = 252) -> float | None:
    s = _price_series(history)
    if len(s) < 20:
        return None
    return float(s.pct_change().dropna().std() * (periods_per_year**0.5))


def max_drawdown(history: pd.DataFrame) -> float | None:
    s = _price_series(history)
    if len(s) < 2:
        return None
    return float((s / s.cummax() - 1).min())


def price_summary(history: pd.DataFrame) -> dict:
    s = _price_series(history)
    if s.empty:
        return {"available": False}
    return {
        "available": True,
        "start_date": s.index[0].date().isoformat(),
        "end_date": s.index[-1].date().isoformat(),
        "start_price": round(float(s.iloc[0]), 4),
        "end_price": round(float(s.iloc[-1]), 4),
        "high": round(float(s.max()), 4),
        "low": round(float(s.min()), 4),
        "total_return": pct_change(s.iloc[-1], s.iloc[0]),
        "annualized_volatility": annualized_volatility(history),
        "max_drawdown": max_drawdown(history),
        "observations": int(len(s)),
        "price_basis": "Adj Close" if "Adj Close" in history and history["Adj Close"].notna().any() else "Close",
    }


# --------------------------------------------------------------------------------------
# Statement-based metrics
# --------------------------------------------------------------------------------------


def statement_growth(stmt: Statement, key: str) -> pd.Series:
    """Period-over-period growth for one line item, aligned to the statement's periods (newest first)."""
    s = stmt.series(key)
    if s.empty:
        return s
    values = list(s.values)
    growth = [pct_change(values[i], values[i + 1]) if i + 1 < len(values) else None for i in range(len(values))]
    return pd.Series(growth, index=s.index, dtype="float64")


def statement_ratios(income: Statement | None, balance: Statement | None = None) -> pd.DataFrame:
    """Per-period margins and returns computed from reported statements.

    Balance-sheet ratios only use a balance period that matches the income period exactly
    (no mixing of incompatible periods).
    """
    if income is None or income.empty:
        return pd.DataFrame()
    rows = {}
    for period in income.periods:
        rev = income.get("TotalRevenue", period)
        ni = income.get("NetIncome", period)
        row = {
            "Gross Margin": margin(income.get("GrossProfit", period), rev),
            "Operating Margin": margin(income.get("OperatingIncome", period), rev),
            "EBITDA Margin": margin(income.get("EBITDA", period), rev),
            "Net Margin": margin(ni, rev),
            "Effective Tax Rate": safe_div(income.get("TaxProvision", period), income.get("PretaxIncome", period)),
            "R&D % of Revenue": margin(income.get("ResearchAndDevelopment", period), rev),
        }
        if balance is not None and not balance.empty and period in balance.periods:
            equity = balance.get("StockholdersEquity", period)
            assets = balance.get("TotalAssets", period)
            row["ROE (period-end equity)"] = safe_div(ni, equity) if (clean_number(equity) or 0) > 0 else None
            row["ROA (period-end assets)"] = safe_div(ni, assets)
            row["Debt / Equity"] = safe_div(balance.get("TotalDebt", period), equity) if (clean_number(equity) or 0) > 0 else None
            row["Current Ratio"] = safe_div(balance.get("CurrentAssets", period), balance.get("CurrentLiabilities", period))
        rows[period] = row
    return pd.DataFrame(rows)


def free_cash_flow(cashflow: Statement, period: pd.Timestamp | None = None) -> float | None:
    reported = cashflow.get("FreeCashFlow", period)
    if reported is not None:
        return reported
    ocf, capex = cashflow.get("OperatingCashFlow", period), cashflow.get("CapitalExpenditure", period)
    if ocf is None or capex is None:
        return None
    return ocf + capex if capex < 0 else ocf - capex  # Yahoo reports capex as negative


# --------------------------------------------------------------------------------------
# Multi-company comparison
# --------------------------------------------------------------------------------------

COMPARISON_FIELDS: dict[str, tuple[str, str]] = {
    # metric name -> (info key, kind)
    "Market Cap": ("marketCap", "large"),
    "Enterprise Value": ("enterpriseValue", "large"),
    "Trailing P/E": ("trailingPE", "ratio"),
    "Forward P/E": ("forwardPE", "ratio"),
    "PEG Ratio": ("trailingPegRatio", "ratio"),
    "Price/Sales": ("priceToSalesTrailing12Months", "ratio"),
    "Price/Book": ("priceToBook", "ratio"),
    "EV/Revenue": ("enterpriseToRevenue", "ratio"),
    "EV/EBITDA": ("enterpriseToEbitda", "ratio"),
    "Gross Margin": ("grossMargins", "pct"),
    "Operating Margin": ("operatingMargins", "pct"),
    "Profit Margin": ("profitMargins", "pct"),
    "ROE": ("returnOnEquity", "pct"),
    "ROA": ("returnOnAssets", "pct"),
    "Revenue Growth (YoY, qtr)": ("revenueGrowth", "pct"),
    "Earnings Growth (YoY, qtr)": ("earningsGrowth", "pct"),
    "Debt/Equity (%)": ("debtToEquity", "ratio"),
    "Current Ratio": ("currentRatio", "ratio"),
    "Dividend Yield": ("dividendYield", "pct_points"),
    "Beta": ("beta", "ratio"),
    "52-Week Change": ("52WeekChange", "pct"),
}


def compare(infos: dict[str, dict], metrics: Iterable[str] | None = None) -> pd.DataFrame:
    """Rows = metrics, columns = symbols; values straight from each company's normalized info."""
    names = list(metrics) if metrics else list(COMPARISON_FIELDS)
    data = {}
    for symbol, info in infos.items():
        data[symbol] = {m: clean_number(info.get(COMPARISON_FIELDS[m][0])) for m in names if m in COMPARISON_FIELDS}
    return pd.DataFrame(data)
