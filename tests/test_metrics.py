from datetime import date

import numpy as np
import pandas as pd
import pytest

from services import metrics
from utils.normalization import normalize_statement


def test_safe_div_handles_zero_and_missing():
    assert metrics.safe_div(10, 2) == 5
    assert metrics.safe_div(10, 0) is None
    assert metrics.safe_div(None, 2) is None
    assert metrics.safe_div(10, float("nan")) is None
    assert metrics.safe_div("Infinity", 2) is None


def test_pct_change_and_negative_base():
    assert metrics.pct_change(110, 100) == pytest.approx(0.10)
    assert metrics.pct_change(-50, -100) == pytest.approx(0.5)  # loss narrowed -> positive growth
    assert metrics.pct_change(5, 0) is None
    assert metrics.pct_change(None, 3) is None


def test_cagr():
    assert metrics.cagr(121, 100, 2) == pytest.approx(0.10)
    assert metrics.cagr(100, -5, 2) is None
    assert metrics.cagr(100, 50, 0) is None


def test_margin_requires_positive_revenue():
    assert metrics.margin(25, 100) == 0.25
    assert metrics.margin(25, 0) is None
    assert metrics.margin(25, -100) is None
    assert metrics.margin(None, 100) is None


def _history(start, periods, values=None):
    idx = pd.bdate_range(start, periods=periods)
    values = values if values is not None else np.linspace(100, 200, periods)
    return pd.DataFrame({"Close": values, "Adj Close": values}, index=idx)


def test_period_return_and_coverage():
    h = _history("2024-01-01", 260)
    r = metrics.period_return(h, date(2024, 1, 1), h.index[-1].date())
    assert r == pytest.approx(1.0, rel=1e-6)
    # Requesting a start long before history begins -> None, not a partial answer.
    assert metrics.period_return(h, date(2020, 1, 1)) is None


def test_performance_table_vs_benchmark():
    # 900 business days ~= 3.45 calendar years: 3Y is computable, 5Y is not.
    h = _history("2020-01-01", 900)
    b = _history("2020-01-01", 900, np.linspace(100, 150, 900))
    rows = {r["period"]: r for r in metrics.performance_table(h, b)}
    assert set(rows) == {"YTD", "1Y", "3Y", "5Y"}
    assert rows["1Y"]["stock_return"] is not None
    assert rows["1Y"]["excess_return"] == pytest.approx(rows["1Y"]["stock_return"] - rows["1Y"]["benchmark_return"])
    assert rows["3Y"]["stock_return"] is not None
    assert rows["5Y"]["stock_return"] is None and rows["5Y"]["excess_return"] is None


def test_price_summary_empty():
    assert metrics.price_summary(pd.DataFrame()) == {"available": False}


def _income():
    cols = pd.to_datetime(["2024-12-31", "2023-12-31"])
    df = pd.DataFrame(
        {
            cols[0]: [1000.0, 400.0, 200.0, 150.0, 180.0, 30.0, np.nan],
            cols[1]: [800.0, 300.0, 120.0, 90.0, 110.0, 20.0, np.nan],
        },
        index=["TotalRevenue", "GrossProfit", "OperatingIncome", "NetIncome", "PretaxIncome", "TaxProvision", "EBITDA"],
    )
    return normalize_statement(df, "income", "annual")


def test_statement_ratios_and_growth():
    inc = _income()
    bal = normalize_statement(
        pd.DataFrame({pd.Timestamp("2024-12-31"): [3000.0, 1000.0, 500.0, 400.0, 200.0]},
                     index=["TotalAssets", "StockholdersEquity", "TotalDebt", "CurrentAssets", "CurrentLiabilities"]),
        "balance", "annual",
    )
    ratios = metrics.statement_ratios(inc, bal)
    latest = ratios[pd.Timestamp("2024-12-31")]
    assert latest["Gross Margin"] == pytest.approx(0.4)
    assert latest["Net Margin"] == pytest.approx(0.15)
    assert pd.isna(latest["EBITDA Margin"])  # missing input stays missing
    assert latest["ROE (period-end equity)"] == pytest.approx(0.15)
    assert latest["Current Ratio"] == pytest.approx(2.0)
    # 2023 has no matching balance-sheet period -> balance ratios absent, not mixed.
    assert pd.isna(ratios[pd.Timestamp("2023-12-31")].get("ROE (period-end equity)"))
    growth = metrics.statement_growth(inc, "TotalRevenue")
    assert growth.iloc[0] == pytest.approx(0.25)
    assert pd.isna(growth.iloc[-1])


def test_free_cash_flow_fallback():
    cf = normalize_statement(
        pd.DataFrame({pd.Timestamp("2024-12-31"): [500.0, -120.0]}, index=["OperatingCashFlow", "CapitalExpenditure"]),
        "cashflow", "annual",
    )
    assert metrics.free_cash_flow(cf) == 380.0


def test_compare_keeps_missing_as_none():
    df = metrics.compare({"AAA": {"trailingPE": 20.0}, "BBB": {"trailingPE": None}}, ["Trailing P/E"])
    assert df.at["Trailing P/E", "AAA"] == 20.0
    assert pd.isna(df.at["Trailing P/E", "BBB"])
