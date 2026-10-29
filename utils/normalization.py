"""Normalize raw yfinance payloads into stable, typed structures."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from utils.formatting import is_missing, to_datetime


def clean_number(value: Any) -> float | None:
    """Return a finite float, or None for missing/non-numeric values ('Infinity', NaN, '')."""
    if is_missing(value) or isinstance(value, bool):
        return None
    if isinstance(value, dict):  # Yahoo raw/fmt objects
        value = value.get("raw")
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def camel_to_title(key: str) -> str:
    """'TotalRevenue' -> 'Total Revenue'; keeps acronyms like 'EBITDA' and 'PPE'."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", key)
    return spaced[:1].upper() + spaced[1:]


def safe_url(url: Any) -> str | None:
    """Only allow http(s) links from external content."""
    if isinstance(url, str) and re.match(r"^https?://", url.strip(), flags=re.I):
        return url.strip()
    return None


# --------------------------------------------------------------------------------------
# Company info / quote
# --------------------------------------------------------------------------------------

NUMERIC_INFO_FIELDS = {
    "currentPrice", "regularMarketPrice", "regularMarketChange", "regularMarketChangePercent",
    "previousClose", "regularMarketPreviousClose", "open", "regularMarketOpen", "dayLow", "dayHigh",
    "regularMarketDayLow", "regularMarketDayHigh", "fiftyTwoWeekLow", "fiftyTwoWeekHigh",
    "volume", "regularMarketVolume", "averageVolume", "averageVolume10days", "averageDailyVolume10Day",
    "bid", "ask", "bidSize", "askSize", "preMarketPrice", "preMarketChange", "preMarketChangePercent",
    "postMarketPrice", "postMarketChange", "postMarketChangePercent",
    "marketCap", "enterpriseValue", "trailingPE", "forwardPE", "pegRatio", "trailingPegRatio",
    "priceToSalesTrailing12Months", "priceToBook", "enterpriseToRevenue", "enterpriseToEbitda",
    "trailingEps", "forwardEps", "epsCurrentYear", "dividendRate", "dividendYield",
    "trailingAnnualDividendRate", "trailingAnnualDividendYield", "fiveYearAvgDividendYield", "payoutRatio",
    "profitMargins", "grossMargins", "operatingMargins", "ebitdaMargins",
    "returnOnAssets", "returnOnEquity", "totalRevenue", "revenuePerShare", "grossProfits", "ebitda",
    "netIncomeToCommon", "revenueGrowth", "earningsGrowth", "earningsQuarterlyGrowth",
    "totalCash", "totalCashPerShare", "totalDebt", "debtToEquity", "currentRatio", "quickRatio", "bookValue",
    "operatingCashflow", "freeCashflow",
    "52WeekChange", "SandP52WeekChange", "fiftyDayAverage", "twoHundredDayAverage", "beta",
    "sharesOutstanding", "floatShares", "impliedSharesOutstanding", "heldPercentInsiders",
    "heldPercentInstitutions", "sharesShort", "sharesShortPriorMonth", "shortRatio", "shortPercentOfFloat",
    "sharesPercentSharesOut", "fullTimeEmployees", "targetMeanPrice", "targetHighPrice", "targetLowPrice",
    "numberOfAnalystOpinions", "recommendationMean",
}

EPOCH_INFO_FIELDS = {
    "exDividendDate", "dividendDate", "lastDividendDate", "earningsTimestamp", "earningsTimestampStart",
    "earningsTimestampEnd", "lastFiscalYearEnd", "nextFiscalYearEnd", "mostRecentQuarter",
    "lastSplitDate", "regularMarketTime", "preMarketTime", "postMarketTime", "dateShortInterest",
    "firstTradeDateMilliseconds",
}


def normalize_info(raw: dict | None) -> dict:
    """Clean a Ticker.info dict: numbers become float|None, epochs become datetimes."""
    if not raw:
        return {}
    info: dict[str, Any] = {}
    for key, value in raw.items():
        if key in NUMERIC_INFO_FIELDS:
            info[key] = clean_number(value)
        elif key in EPOCH_INFO_FIELDS:
            info[key] = to_datetime(value) if clean_number(value) is not None else None
        elif isinstance(value, str):
            info[key] = value.strip() or None
        else:
            info[key] = value
    info["symbol"] = (raw.get("symbol") or "").upper() or None
    info["name"] = raw.get("longName") or raw.get("shortName") or raw.get("displayName")
    info["price"] = first_number(info, "regularMarketPrice", "currentPrice")
    info["prev_close"] = first_number(info, "regularMarketPreviousClose", "previousClose")
    change = info.get("regularMarketChange")
    if change is None and info["price"] is not None and info["prev_close"] is not None:
        change = info["price"] - info["prev_close"]
    info["change"] = change
    pct = info.get("regularMarketChangePercent")
    if pct is None and change is not None and info["prev_close"]:
        pct = change / info["prev_close"] * 100
    info["change_pct"] = pct
    return info


def first_number(d: dict, *keys: str) -> float | None:
    for k in keys:
        v = clean_number(d.get(k))
        if v is not None:
            return v
    return None


# --------------------------------------------------------------------------------------
# News
# --------------------------------------------------------------------------------------


def normalize_news_item(raw: dict, category: str = "News") -> dict | None:
    """Handle both the current ('content' wrapper) and legacy yfinance news schemas."""
    if not isinstance(raw, dict):
        return None
    c = raw.get("content") if isinstance(raw.get("content"), dict) else raw
    title = c.get("title")
    if not title:
        return None
    provider = c.get("provider")
    publisher = provider.get("displayName") if isinstance(provider, dict) else c.get("publisher")
    url = None
    for candidate in (c.get("canonicalUrl"), c.get("clickThroughUrl"), c.get("link")):
        url = safe_url(candidate.get("url") if isinstance(candidate, dict) else candidate)
        if url:
            break
    published = to_datetime(c.get("pubDate") or c.get("displayTime") or c.get("providerPublishTime"))
    thumb = None
    thumbnail = c.get("thumbnail")
    if isinstance(thumbnail, dict):
        resolutions = thumbnail.get("resolutions") or []
        smallest = sorted(
            (r for r in resolutions if isinstance(r, dict) and safe_url(r.get("url"))),
            key=lambda r: r.get("width") or 10_000,
        )
        thumb = safe_url(smallest[0]["url"]) if smallest else safe_url(thumbnail.get("originalUrl"))
    tickers = raw.get("relatedTickers") or []
    finance = c.get("finance") if isinstance(c.get("finance"), dict) else {}
    for t in finance.get("stockTickers") or []:
        if isinstance(t, dict) and t.get("symbol"):
            tickers.append(t["symbol"])
    content_type = (c.get("contentType") or c.get("type") or "STORY").upper()
    return {
        "id": raw.get("id") or c.get("id") or raw.get("uuid") or url or title,
        "title": str(title).strip(),
        "summary": (c.get("summary") or c.get("description") or "").strip() or None,
        "publisher": publisher,
        "url": url,
        "published": published,
        "thumbnail": thumb,
        "tickers": sorted(set(tickers)),
        "content_type": content_type,
        "category": "Video" if content_type == "VIDEO" else category,
    }


def normalize_news(raw_items: list | None, category: str = "News") -> list[dict]:
    items = [normalize_news_item(r, category) for r in (raw_items or [])]
    return [i for i in items if i]


# --------------------------------------------------------------------------------------
# Financial statements
# --------------------------------------------------------------------------------------

# (yfinance key, display label, is_key_item, value_kind)
INCOME_ITEMS = [
    ("TotalRevenue", "Total Revenue", True, "money"),
    ("OperatingRevenue", "Operating Revenue", False, "money"),
    ("CostOfRevenue", "Cost of Revenue", True, "money"),
    ("GrossProfit", "Gross Profit", True, "money"),
    ("OperatingExpense", "Operating Expenses", True, "money"),
    ("ResearchAndDevelopment", "Research & Development", True, "money"),
    ("SellingGeneralAndAdministration", "Selling, General & Administrative", True, "money"),
    ("OperatingIncome", "Operating Income", True, "money"),
    ("NetNonOperatingInterestIncomeExpense", "Net Non-Operating Interest Income/Expense", True, "money"),
    ("InterestIncome", "Interest Income", False, "money"),
    ("InterestExpense", "Interest Expense", False, "money"),
    ("OtherIncomeExpense", "Other Income/Expense", True, "money"),
    ("PretaxIncome", "Pretax Income", True, "money"),
    ("TaxProvision", "Tax Provision", True, "money"),
    ("NetIncome", "Net Income", True, "money"),
    ("NetIncomeCommonStockholders", "Net Income to Common Stockholders", False, "money"),
    ("BasicEPS", "Basic EPS", True, "per_share"),
    ("DilutedEPS", "Diluted EPS", True, "per_share"),
    ("BasicAverageShares", "Basic Weighted Avg. Shares", True, "shares"),
    ("DilutedAverageShares", "Diluted Weighted Avg. Shares", True, "shares"),
    ("EBIT", "EBIT", False, "money"),
    ("EBITDA", "EBITDA", True, "money"),
    ("NormalizedEBITDA", "Normalized EBITDA", False, "money"),
    ("TotalExpenses", "Total Expenses", False, "money"),
]

BALANCE_ITEMS = [
    ("CashAndCashEquivalents", "Cash & Cash Equivalents", True, "money"),
    ("OtherShortTermInvestments", "Short-Term Investments", True, "money"),
    ("CashCashEquivalentsAndShortTermInvestments", "Cash, Equivalents & ST Investments", False, "money"),
    ("AccountsReceivable", "Accounts Receivable", True, "money"),
    ("Receivables", "Total Receivables", False, "money"),
    ("Inventory", "Inventory", True, "money"),
    ("CurrentAssets", "Total Current Assets", True, "money"),
    ("NetPPE", "Net PP&E", True, "money"),
    ("GoodwillAndOtherIntangibleAssets", "Goodwill & Intangibles", True, "money"),
    ("Goodwill", "Goodwill", False, "money"),
    ("OtherIntangibleAssets", "Other Intangible Assets", False, "money"),
    ("TotalNonCurrentAssets", "Total Non-Current Assets", False, "money"),
    ("TotalAssets", "Total Assets", True, "money"),
    ("AccountsPayable", "Accounts Payable", True, "money"),
    ("Payables", "Total Payables", False, "money"),
    ("CurrentLiabilities", "Total Current Liabilities", True, "money"),
    ("CurrentDebt", "Short-Term Debt", True, "money"),
    ("LongTermDebt", "Long-Term Debt", True, "money"),
    ("TotalDebt", "Total Debt", True, "money"),
    ("TotalLiabilitiesNetMinorityInterest", "Total Liabilities", True, "money"),
    ("StockholdersEquity", "Stockholders' Equity", True, "money"),
    ("TotalEquityGrossMinorityInterest", "Total Equity incl. Minority Interest", False, "money"),
    ("RetainedEarnings", "Retained Earnings", True, "money"),
    ("WorkingCapital", "Working Capital", False, "money"),
    ("NetDebt", "Net Debt", False, "money"),
    ("OrdinarySharesNumber", "Ordinary Shares Outstanding", False, "shares"),
]

CASHFLOW_ITEMS = [
    ("NetIncomeFromContinuingOperations", "Net Income (Continuing Ops)", True, "money"),
    ("DepreciationAndAmortization", "Depreciation & Amortization", True, "money"),
    ("StockBasedCompensation", "Stock-Based Compensation", True, "money"),
    ("ChangeInWorkingCapital", "Change in Working Capital", True, "money"),
    ("OperatingCashFlow", "Operating Cash Flow", True, "money"),
    ("CapitalExpenditure", "Capital Expenditure", True, "money"),
    ("InvestingCashFlow", "Investing Cash Flow", True, "money"),
    ("IssuanceOfDebt", "Debt Issuance", True, "money"),
    ("RepaymentOfDebt", "Debt Repayment", True, "money"),
    ("RepurchaseOfCapitalStock", "Share Repurchases", True, "money"),
    ("CashDividendsPaid", "Dividends Paid", True, "money"),
    ("FinancingCashFlow", "Financing Cash Flow", True, "money"),
    ("ChangesInCash", "Net Change in Cash", True, "money"),
    ("EndCashPosition", "End Cash Position", False, "money"),
    ("FreeCashFlow", "Free Cash Flow", True, "money"),
]

STATEMENT_ITEMS = {"income": INCOME_ITEMS, "balance": BALANCE_ITEMS, "cashflow": CASHFLOW_ITEMS}
STATEMENT_LABELS = {"income": "Income Statement", "balance": "Balance Sheet", "cashflow": "Cash Flow"}


@dataclass
class Statement:
    """A normalized statement: rows are yfinance keys, columns are period-end Timestamps (newest first)."""

    kind: str
    frequency: str
    values: pd.DataFrame
    labels: dict[str, str] = field(default_factory=dict)
    key_items: list[str] = field(default_factory=list)
    value_kinds: dict[str, str] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return self.values.empty

    @property
    def periods(self) -> list[pd.Timestamp]:
        return list(self.values.columns)

    def get(self, key: str, period: pd.Timestamp | None = None) -> float | None:
        if key not in self.values.index or self.values.empty:
            return None
        period = period if period is not None else self.values.columns[0]
        return clean_number(self.values.at[key, period])

    def series(self, key: str) -> pd.Series:
        if key not in self.values.index:
            return pd.Series(dtype="float64")
        return self.values.loc[key].astype("float64")


def normalize_statement(df: pd.DataFrame | None, kind: str, frequency: str) -> Statement:
    """Order rows by the canonical list (unknown rows appended), sort periods newest first,
    drop all-empty periods. Missing values stay NaN (rendered as unavailable)."""
    if df is None or df.empty:
        return Statement(kind, frequency, pd.DataFrame())
    data = df.copy()
    data.columns = pd.to_datetime(data.columns, errors="coerce")
    data = data.loc[:, data.columns.notna()]
    data = data.apply(pd.to_numeric, errors="coerce")
    data = data.dropna(axis=1, how="all")
    data = data[sorted(data.columns, reverse=True)]
    data = data[~data.index.duplicated()]

    canonical = STATEMENT_ITEMS[kind]
    ordered = [k for k, *_ in canonical if k in data.index]
    extras = sorted(k for k in data.index if k not in set(ordered))
    data = data.loc[ordered + extras]

    labels = {k: label for k, label, *_ in canonical}
    kinds = {k: vk for k, _, _, vk in canonical}
    for k in extras:
        labels[k] = camel_to_title(str(k))
        kinds[k] = "per_share" if "EPS" in str(k) else "shares" if "Shares" in str(k) else "money"
    key_items = [k for k, _, is_key, _ in canonical if is_key and k in data.index]
    return Statement(kind, frequency, data, labels, key_items, kinds)


# --------------------------------------------------------------------------------------
# Holders
# --------------------------------------------------------------------------------------

MAJOR_HOLDER_LABELS = {
    "insidersPercentHeld": "% of Shares Held by Insiders",
    "institutionsPercentHeld": "% of Shares Held by Institutions",
    "institutionsFloatPercentHeld": "% of Float Held by Institutions",
    "institutionsCount": "Number of Institutions Holding Shares",
}


def normalize_major_holders(df: pd.DataFrame | None) -> dict[str, float | None]:
    out = {k: None for k in MAJOR_HOLDER_LABELS}
    if df is None or df.empty:
        return out
    col = "Value" if "Value" in df.columns else df.columns[0]
    for key in MAJOR_HOLDER_LABELS:
        if key in df.index:
            out[key] = clean_number(df.at[key, col])
    return out


def normalize_holder_table(df: pd.DataFrame | None) -> pd.DataFrame:
    """Standard columns: Holder, Shares, Date Reported, % Out, Value, % Change."""
    columns = ["Holder", "Shares", "Date Reported", "% Out", "Value", "% Change"]
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)
    data = df.rename(columns={"pctHeld": "% Out", "pctChange": "% Change", "organization": "Holder",
                              "position": "Shares", "reportDate": "Date Reported", "value": "Value"})
    for col in columns:
        if col not in data.columns:
            data[col] = pd.NA
    data = data[columns].copy()
    data["Date Reported"] = pd.to_datetime(data["Date Reported"], errors="coerce")
    for col in ["Shares", "% Out", "Value", "% Change"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    return data.sort_values("Shares", ascending=False, na_position="last").reset_index(drop=True)
