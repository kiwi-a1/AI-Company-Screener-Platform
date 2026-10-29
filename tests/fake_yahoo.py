"""Synthetic stand-in for yfinance used ONLY by tests and offline UI smoke runs.

The numbers are generated, not real market data. `install()` patches yfinance.Ticker / yfinance.Search.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance

UNKNOWN = "ZZZZ"


def _info(symbol: str) -> dict:
    base = {"AAPL": 190.0, "MSFT": 410.0}.get(symbol, 100.0)
    now = int(pd.Timestamp.now(tz="UTC").timestamp())
    return {
        "symbol": symbol, "longName": f"{symbol} Test Corp", "quoteType": "EQUITY", "exchange": "NMS",
        "fullExchangeName": "NasdaqGS", "currency": "USD", "financialCurrency": "USD", "marketState": "POST",
        "sector": "Technology", "industry": "Consumer Electronics", "country": "United States",
        "website": "https://example.com", "fullTimeEmployees": 1000,
        "longBusinessSummary": f"{symbol} Test Corp makes $100 widgets. Synthetic profile for testing.",
        "regularMarketPrice": base, "regularMarketPreviousClose": base - 2, "regularMarketChange": 2.0,
        "regularMarketChangePercent": 2 / (base - 2) * 100, "regularMarketOpen": base - 1,
        "regularMarketDayLow": base - 3, "regularMarketDayHigh": base + 1, "fiftyTwoWeekLow": base * 0.7,
        "fiftyTwoWeekHigh": base * 1.1, "regularMarketVolume": 50_000_000, "averageVolume": 55_000_000,
        "bid": base - 0.05, "ask": base + 0.05, "bidSize": 100, "askSize": 200,
        "postMarketPrice": base + 0.5, "postMarketChange": 0.5, "postMarketChangePercent": 0.26, "postMarketTime": now,
        "regularMarketTime": now - 3600, "marketCap": 3.0e12, "enterpriseValue": 3.1e12, "trailingPE": 30.5,
        "forwardPE": 28.1, "trailingPegRatio": 2.1, "priceToSalesTrailing12Months": 7.9, "priceToBook": 45.0,
        "enterpriseToRevenue": 8.0, "enterpriseToEbitda": 22.0, "trailingEps": 6.2, "forwardEps": 7.0,
        "earningsTimestamp": now + 86400 * 30, "dividendRate": 1.0, "dividendYield": 0.5,
        "exDividendDate": now - 86400 * 20, "profitMargins": 0.24, "grossMargins": 0.45, "operatingMargins": 0.3,
        "ebitdaMargins": 0.34, "returnOnAssets": 0.22, "returnOnEquity": 1.5, "totalRevenue": 3.9e11,
        "revenueGrowth": 0.05, "totalCash": 6.0e10, "totalDebt": 1.0e11, "debtToEquity": 150.0,
        "currentRatio": 0.9, "beta": 1.2, "52WeekChange": 0.2, "SandP52WeekChange": 0.15,
        "sharesOutstanding": 1.5e10, "heldPercentInsiders": 0.02, "heldPercentInstitutions": 0.62,
        "shortRatio": 1.5, "lastSplitFactor": "4:1", "lastFiscalYearEnd": now - 86400 * 60,
        "mostRecentQuarter": now - 86400 * 40, "recommendationKey": "buy", "targetMeanPrice": base * 1.1,
        # deliberately missing: quickRatio, shortPercentOfFloat, pegRatio ...
    }


def _history(symbol: str, **kwargs) -> pd.DataFrame:
    interval = kwargs.get("interval", "1d")
    freq = {"1d": "B", "1wk": "W-FRI", "1mo": "MS"}.get(interval, "h")
    end = pd.Timestamp.today().normalize()
    if "start" in kwargs and kwargs["start"] is not None:
        idx = pd.date_range(pd.Timestamp(kwargs["start"]), min(pd.Timestamp(kwargs["end"]), end), freq=freq)
    else:
        years = {"1mo": 1 / 12, "3mo": 0.25, "6mo": 0.5, "ytd": 1, "1y": 1, "2y": 2, "5y": 5, "10y": 10, "max": 12}.get(kwargs.get("period", "1y"), 1)
        idx = pd.date_range(end - pd.Timedelta(days=int(365 * years)), end, freq=freq)
    if len(idx) == 0:
        return pd.DataFrame()
    rng = np.random.default_rng(abs(hash(symbol)) % 2**32)
    drift = 0.0002 if symbol != "^GSPC" else 0.00015
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.015, len(idx))))
    df = pd.DataFrame({"Open": close * 0.995, "High": close * 1.01, "Low": close * 0.99, "Close": close,
                       "Adj Close": close * 0.98, "Volume": rng.integers(1e6, 5e6, len(idx))}, index=idx)
    df.index.name = "Date"
    return df


def _statement(kind: str, freq: str) -> pd.DataFrame:
    n = 4 if freq == "yearly" else 5
    periods = pd.date_range(end="2025-09-30", periods=n, freq="YE-SEP" if freq == "yearly" else "QE-SEP")[::-1]
    g = np.array([1.0, 0.93, 0.88, 0.85, 0.8])[:n]
    if kind == "income":
        rows = {"TotalRevenue": 400e9 * g, "CostOfRevenue": 220e9 * g, "GrossProfit": 180e9 * g,
                "OperatingExpense": 60e9 * g, "ResearchAndDevelopment": 30e9 * g, "SellingGeneralAndAdministration": 27e9 * g,
                "OperatingIncome": 120e9 * g, "PretaxIncome": 121e9 * g, "TaxProvision": 20e9 * g, "NetIncome": 100e9 * g,
                "BasicEPS": 6.5 * g, "DilutedEPS": 6.4 * g, "DilutedAverageShares": 15.5e9 * np.ones(n),
                "EBITDA": 135e9 * g, "SomeObscureItem": 1e9 * g}
    elif kind == "balance":
        rows = {"CashAndCashEquivalents": 30e9 * g, "CurrentAssets": 150e9 * g, "TotalAssets": 360e9 * g,
                "CurrentLiabilities": 170e9 * g, "TotalDebt": 100e9 * g, "StockholdersEquity": 65e9 * g,
                "TotalLiabilitiesNetMinorityInterest": 295e9 * g, "RetainedEarnings": np.full(n, np.nan)}
    else:
        rows = {"OperatingCashFlow": 115e9 * g, "CapitalExpenditure": -10e9 * g, "FreeCashFlow": 105e9 * g,
                "RepurchaseOfCapitalStock": -90e9 * g, "CashDividendsPaid": -15e9 * g, "FinancingCashFlow": -110e9 * g}
    df = pd.DataFrame(rows, index=periods).T
    if freq == "yearly":
        df[pd.Timestamp("2020-09-30")] = np.nan  # an all-empty period, as Yahoo sometimes returns
    return df


class FakeTicker:
    def __init__(self, symbol: str):
        self.ticker = symbol.upper()

    def get_info(self):
        return {"trailingPegRatio": None} if self.ticker == UNKNOWN else _info(self.ticker)

    info = property(get_info)

    def history(self, *args, **kwargs):
        return pd.DataFrame() if self.ticker == UNKNOWN else _history(self.ticker, **kwargs)

    def get_news(self, count=10, tab="news"):
        now = pd.Timestamp.now(tz="UTC")
        if tab == "press releases":
            return [{"id": "pr1", "content": {"title": f"{self.ticker} announces quarterly dividend",
                                                "pubDate": (now - pd.Timedelta(hours=5)).isoformat(),
                                                "provider": {"displayName": "Business Wire"},
                                                "canonicalUrl": {"url": "https://example.com/pr1"}, "contentType": "STORY"}}]
        return [{"id": f"n{i}", "content": {"title": f"Test headline {i} about {self.ticker}",
                                            "summary": "Synthetic summary text for UI testing.",
                                            "pubDate": (now - pd.Timedelta(hours=i * 7)).isoformat(),
                                            "provider": {"displayName": "Test Wire"},
                                            "canonicalUrl": {"url": f"https://example.com/n{i}"},
                                            "finance": {"stockTickers": [{"symbol": self.ticker}]},
                                            "contentType": "VIDEO" if i == 3 else "STORY"}} for i in range(6)]

    def get_income_stmt(self, pretty=False, freq="yearly", as_dict=False):
        return _statement("income", freq)

    def get_balance_sheet(self, pretty=False, freq="yearly", as_dict=False):
        return _statement("balance", freq)

    def get_cash_flow(self, pretty=False, freq="yearly", as_dict=False):
        return _statement("cashflow", freq)

    def get_major_holders(self, as_dict=False):
        return pd.DataFrame({"Value": [0.02, 0.62, 0.63, 6500]},
                            index=["insidersPercentHeld", "institutionsPercentHeld", "institutionsFloatPercentHeld", "institutionsCount"])

    def _holders(self, prefix):
        return pd.DataFrame({"Date Reported": pd.to_datetime(["2025-06-30"] * 5), "Holder": [f"{prefix} {c}" for c in "ABCDE"],
                             "pctHeld": [0.09, 0.07, 0.04, 0.02, 0.01], "Shares": [1.4e9, 1.1e9, 6e8, 3e8, 1.5e8],
                             "Value": [2.7e11, 2.1e11, 1.1e11, 6e10, 3e10], "pctChange": [0.01, -0.02, 0.0, 0.05, None]})

    def get_institutional_holders(self, as_dict=False):
        return self._holders("Institution")

    def get_mutualfund_holders(self, as_dict=False):
        return self._holders("Fund")

    def get_dividends(self, period="max"):
        idx = pd.date_range("2021-02-05", periods=18, freq="QS-FEB")
        return pd.Series(np.linspace(0.2, 0.26, len(idx)), index=idx)

    def get_splits(self, period="max"):
        return pd.Series([7.0, 4.0], index=pd.to_datetime(["2014-06-09", "2020-08-31"]))


class FakeSearch:
    def __init__(self, query, max_results=8, **kwargs):
        q = query.upper()
        universe = [("AAPL", "Apple Inc."), ("MSFT", "Microsoft Corporation"), ("SONY", "Sony Group"), ("DELL", "Dell Technologies")]
        self.quotes = [{"symbol": s, "longname": n, "exchDisp": "NASDAQ", "typeDisp": "Equity", "quoteType": "EQUITY"}
                       for s, n in universe if q in s or q.lower() in n.lower() or "ELECTRONICS" in q][:max_results]


def install() -> None:
    yfinance.Ticker = FakeTicker
    yfinance.Search = FakeSearch
