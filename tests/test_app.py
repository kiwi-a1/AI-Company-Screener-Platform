"""Smoke-test every section through Streamlit's AppTest with synthetic Yahoo data (no network)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from services import cache
from tests import fake_yahoo

APP = Path(__file__).resolve().parent.parent / "app.py"

SECTIONS = ["Summary", "News", "Statistics", "Historical Data", "Financials", "Holders"]


@pytest.fixture(autouse=True)
def _fake(monkeypatch):
    fake_yahoo.install()
    for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    cache.invalidate()
    yield
    cache.invalidate()


def _run(section="Summary", symbol="AAPL"):
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.query_params["s"] = symbol
    at.query_params["tab"] = section
    at.run()
    return at


@pytest.mark.parametrize("section", SECTIONS)
def test_section_renders_without_errors(section):
    at = _run(section)
    assert not at.exception, at.exception
    assert not [e.value for e in at.error], [e.value for e in at.error]
    html = " ".join(m.value for m in at.markdown)
    assert "AAPL Test Corp" in html  # header present on every section


def test_unknown_symbol_shows_error():
    at = _run("Summary", fake_yahoo.UNKNOWN)
    assert not at.exception
    assert any("No data is available" in e.value for e in at.error)


def test_missing_values_render_as_unavailable():
    at = _run("Statistics")
    html = " ".join(m.value for m in at.markdown)
    assert "Quick Ratio (mrq)" in html and "—" in html


def test_sidebar_without_api_key_shows_setup():
    at = _run("Summary")
    assert any("ANTHROPIC_API_KEY" in i.value for i in at.sidebar.info)
