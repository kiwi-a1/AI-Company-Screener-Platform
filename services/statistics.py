"""Key-statistics groups (spec §4.3), defined once and shared by the UI and the AI tools.

Each metric: (label, info_key, kind). Kinds map to utils.formatting.fmt_value:
large | money | price | pct (ratio 0.12 -> 12%) | pct_points (already percent) | ratio | int | date | text
"""
from __future__ import annotations

from typing import Any

from utils.formatting import fmt_value
from utils.normalization import clean_number

STAT_GROUPS: dict[str, list[tuple[str, str, str]]] = {
    "Valuation Measures": [
        ("Market Cap", "marketCap", "large"),
        ("Enterprise Value", "enterpriseValue", "large"),
        ("Trailing P/E", "trailingPE", "ratio"),
        ("Forward P/E", "forwardPE", "ratio"),
        ("PEG Ratio (5yr expected)", "trailingPegRatio", "ratio"),
        ("Price/Sales (ttm)", "priceToSalesTrailing12Months", "ratio"),
        ("Price/Book (mrq)", "priceToBook", "ratio"),
        ("Enterprise Value/Revenue", "enterpriseToRevenue", "ratio"),
        ("Enterprise Value/EBITDA", "enterpriseToEbitda", "ratio"),
        ("Trailing EPS (ttm)", "trailingEps", "price"),
        ("Forward EPS", "forwardEps", "price"),
    ],
    "Profitability": [
        ("Profit Margin", "profitMargins", "pct"),
        ("Gross Margin", "grossMargins", "pct"),
        ("Operating Margin (ttm)", "operatingMargins", "pct"),
        ("EBITDA Margin", "ebitdaMargins", "pct"),
    ],
    "Management Effectiveness": [
        ("Return on Assets (ttm)", "returnOnAssets", "pct"),
        ("Return on Equity (ttm)", "returnOnEquity", "pct"),
    ],
    "Financial Highlights": [
        ("Fiscal Year Ends", "lastFiscalYearEnd", "date"),
        ("Most Recent Quarter (mrq)", "mostRecentQuarter", "date"),
        ("Revenue (ttm)", "totalRevenue", "large"),
        ("Revenue Per Share (ttm)", "revenuePerShare", "price"),
        ("Quarterly Revenue Growth (yoy)", "revenueGrowth", "pct"),
        ("Gross Profit (ttm)", "grossProfits", "large"),
        ("EBITDA", "ebitda", "large"),
        ("Net Income to Common (ttm)", "netIncomeToCommon", "large"),
        ("Diluted EPS (ttm)", "trailingEps", "price"),
        ("Quarterly Earnings Growth (yoy)", "earningsQuarterlyGrowth", "pct"),
        ("Operating Cash Flow (ttm)", "operatingCashflow", "large"),
        ("Levered Free Cash Flow (ttm)", "freeCashflow", "large"),
    ],
    "Balance Sheet Health": [
        ("Total Cash (mrq)", "totalCash", "large"),
        ("Total Cash Per Share (mrq)", "totalCashPerShare", "price"),
        ("Total Debt (mrq)", "totalDebt", "large"),
        ("Total Debt/Equity (mrq)", "debtToEquity", "pct_points"),
        ("Current Ratio (mrq)", "currentRatio", "ratio"),
        ("Quick Ratio (mrq)", "quickRatio", "ratio"),
        ("Book Value Per Share (mrq)", "bookValue", "price"),
    ],
    "Trading Information": [
        ("Beta (5Y Monthly)", "beta", "ratio"),
        ("52-Week Change", "52WeekChange", "pct"),
        ("S&P 500 52-Week Change", "SandP52WeekChange", "pct"),
        ("52-Week High", "fiftyTwoWeekHigh", "price"),
        ("52-Week Low", "fiftyTwoWeekLow", "price"),
        ("50-Day Moving Average", "fiftyDayAverage", "price"),
        ("200-Day Moving Average", "twoHundredDayAverage", "price"),
        ("Avg Vol (3 month)", "averageVolume", "large"),
        ("Avg Vol (10 day)", "averageVolume10days", "large"),
        ("Volume", "regularMarketVolume", "large"),
    ],
    "Share Statistics": [
        ("Shares Outstanding", "sharesOutstanding", "large"),
        ("Implied Shares Outstanding", "impliedSharesOutstanding", "large"),
        ("Float", "floatShares", "large"),
        ("% Held by Insiders", "heldPercentInsiders", "pct"),
        ("% Held by Institutions", "heldPercentInstitutions", "pct"),
        ("Shares Short", "sharesShort", "large"),
        ("Short Interest Date", "dateShortInterest", "date"),
        ("Shares Short (prior month)", "sharesShortPriorMonth", "large"),
        ("Short Ratio", "shortRatio", "ratio"),
        ("Short % of Float", "shortPercentOfFloat", "pct"),
        ("Short % of Shares Outstanding", "sharesPercentSharesOut", "pct"),
    ],
    "Dividends & Splits": [
        ("Forward Annual Dividend Rate", "dividendRate", "price"),
        ("Forward Annual Dividend Yield", "dividendYield", "pct_points"),
        ("Trailing Annual Dividend Rate", "trailingAnnualDividendRate", "price"),
        ("Trailing Annual Dividend Yield", "trailingAnnualDividendYield", "pct"),
        ("5 Year Average Dividend Yield", "fiveYearAvgDividendYield", "pct_points"),
        ("Payout Ratio", "payoutRatio", "pct"),
        ("Dividend Date", "dividendDate", "date"),
        ("Ex-Dividend Date", "exDividendDate", "date"),
        ("Last Split Factor", "lastSplitFactor", "text"),
        ("Last Split Date", "lastSplitDate", "date"),
    ],
}


def group_rows(info: dict, group: str) -> list[dict[str, Any]]:
    """Rows with label, raw value (None if unavailable), formatted text and kind."""
    rows = []
    for label, key, kind in STAT_GROUPS[group]:
        raw = info.get(key)
        if kind not in ("date", "text"):
            raw = clean_number(raw)
        rows.append({"label": label, "key": key, "kind": kind, "value": raw, "display": fmt_value(raw, kind)})
    return rows


def group_values_for_ai(info: dict, group: str) -> dict[str, Any]:
    """Compact {label: value} with explicit None for unavailable fields and unit hints."""
    out = {}
    for row in group_rows(info, group):
        v = row["value"]
        if hasattr(v, "isoformat"):
            v = v.date().isoformat() if hasattr(v, "date") else v.isoformat()
        elif isinstance(v, float):
            v = round(v, 6)
        unit = {"pct": " (ratio, 0.10 = 10%)", "pct_points": " (percent)"}.get(row["kind"], "")
        out[row["label"] + unit] = v
    return out
