from datetime import date

import numpy as np
import pandas as pd
import pytest

from utils import formatting as f
from utils.normalization import (
    camel_to_title,
    clean_number,
    normalize_holder_table,
    normalize_info,
    normalize_major_holders,
    normalize_news,
    normalize_statement,
    safe_url,
)
from utils.validation import is_valid_symbol, preset_range, validate_history_request


def test_clean_number():
    assert clean_number("12.5") == 12.5
    assert clean_number({"raw": 3, "fmt": "3"}) == 3
    for bad in (None, "Infinity", float("nan"), "", "abc", True):
        assert clean_number(bad) is None


def test_normalize_info_derives_change():
    info = normalize_info({"symbol": "abc", "longName": "ABC Corp", "regularMarketPrice": 110,
                           "regularMarketPreviousClose": 100, "trailingPE": "Infinity", "exDividendDate": 1700000000})
    assert info["symbol"] == "ABC"
    assert info["change"] == 10 and info["change_pct"] == pytest.approx(10)
    assert info["trailingPE"] is None
    assert info["exDividendDate"].year == 2023


def test_news_new_and_legacy_schema():
    new = {"id": "1", "content": {"title": "Big news", "pubDate": "2025-05-01T12:00:00Z",
                                  "provider": {"displayName": "Reuters"},
                                  "canonicalUrl": {"url": "https://example.com/a"},
                                  "thumbnail": {"resolutions": [{"url": "https://img/x.jpg", "width": 140}]},
                                  "contentType": "STORY"}}
    legacy = {"uuid": "2", "title": "Old news", "publisher": "AP", "link": "https://example.com/b",
              "providerPublishTime": 1700000000, "relatedTickers": ["AAPL"]}
    bad = {"content": {"title": "XSS", "canonicalUrl": {"url": "javascript:alert(1)"}}}
    items = normalize_news([new, legacy, bad, {"no": "title"}])
    assert [i["title"] for i in items] == ["Big news", "Old news", "XSS"]
    assert items[0]["publisher"] == "Reuters" and items[0]["thumbnail"] == "https://img/x.jpg"
    assert items[1]["tickers"] == ["AAPL"] and items[1]["published"].year == 2023
    assert items[2]["url"] is None  # unsafe scheme dropped


def test_safe_url():
    assert safe_url("https://a.b") == "https://a.b"
    assert safe_url("data:text/html,x") is None


def test_normalize_statement_orders_and_drops_empty_periods():
    cols = pd.to_datetime(["2022-12-31", "2024-12-31", "2023-12-31", "2021-12-31"])
    df = pd.DataFrame(
        [[1, 3, 2, np.nan], [10, 30, 20, np.nan], [5, 6, 7, np.nan]],
        index=["NetIncome", "TotalRevenue", "SomeWeirdItem"], columns=cols,
    )
    st = normalize_statement(df, "income", "annual")
    assert list(st.values.index) == ["TotalRevenue", "NetIncome", "SomeWeirdItem"]
    assert st.periods == list(pd.to_datetime(["2024-12-31", "2023-12-31", "2022-12-31"]))
    assert st.labels["SomeWeirdItem"] == "Some Weird Item"
    assert st.get("TotalRevenue") == 30
    assert st.get("Missing") is None
    assert normalize_statement(pd.DataFrame(), "income", "annual").empty


def test_holders():
    major = pd.DataFrame({"Value": [0.02, 0.6, 0.61, 6000]},
                         index=["insidersPercentHeld", "institutionsPercentHeld", "institutionsFloatPercentHeld", "institutionsCount"])
    assert normalize_major_holders(major)["institutionsCount"] == 6000
    assert normalize_major_holders(None)["insidersPercentHeld"] is None
    inst = pd.DataFrame({"Date Reported": ["2025-06-30", "2025-06-30"], "Holder": ["A", "B"],
                         "pctHeld": [0.05, 0.08], "Shares": [100, 200], "Value": [1e6, 2e6]})
    t = normalize_holder_table(inst)
    assert list(t.columns) == ["Holder", "Shares", "Date Reported", "% Out", "Value", "% Change"]
    assert t.iloc[0]["Holder"] == "B"
    assert normalize_holder_table(None).empty


def test_formatting_unavailable_not_zero():
    assert f.fmt_large(None) == f.UNAVAILABLE
    assert f.fmt_large(0) == "0.00"
    assert f.fmt_large(1_234_567_890) == "1.23B"
    assert f.fmt_large(-2_500_000) == "-2.50M"
    assert f.fmt_pct(0.1234) == "12.34%"
    assert f.fmt_pct(np.nan) == f.UNAVAILABLE
    assert f.fmt_change(1.5, 0.75) == "+1.50 (+0.75%)"
    assert camel_to_title("NetPPE") == "Net PPE"


def test_symbol_validation():
    for ok in ("AAPL", "brk-b", "RELIANCE.NS", "^GSPC", "EURUSD=X"):
        assert is_valid_symbol(ok)
    for bad in ("", "AAPL; DROP", "a b", "X" * 30):
        assert not is_valid_symbol(bad)


def test_history_request_limits():
    today = date(2025, 6, 30)
    r = validate_history_request(date(2025, 1, 1), date(2025, 6, 30), "1m", today=today)
    assert r.start == date(2025, 6, 23) and r.warning
    r = validate_history_request(date(2025, 6, 30), date(2025, 1, 1), "1d", today=today)
    assert r.start < r.end and r.warning
    with pytest.raises(ValueError):
        validate_history_request(date(2025, 1, 1), date(2025, 2, 1), "7m", today=today)
    assert preset_range("YTD", today) == (date(2025, 1, 1), today)
    assert preset_range("Max", today)[0] is None
