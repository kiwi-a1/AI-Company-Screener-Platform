"""AI tools (against synthetic Yahoo data), context note, citations and the agent loop (scripted client)."""
import json
from types import SimpleNamespace as NS

import pytest

from ai import assistant, tools
from ai.citations import SourceLog, collect_from_content
from ai.context_manager import build_context_note
from services import cache
from tests import fake_yahoo


@pytest.fixture(autouse=True)
def _fake():
    fake_yahoo.install()
    cache.invalidate()
    yield
    cache.invalidate()


def run(name, **kwargs):
    text, is_error = tools.execute(name, kwargs)
    return json.loads(text), is_error


def test_tool_definitions_are_strict_and_complete():
    names = {t["name"] for t in tools.TOOL_DEFINITIONS}
    assert names == tools.TOOL_NAMES
    for t in tools.TOOL_DEFINITIONS:
        schema = t["input_schema"]
        assert t["strict"] and schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


def test_snapshot_and_statistics():
    out, err = run("get_company_snapshot", symbol="aapl")
    assert not err and out["available"] and out["symbol"] == "AAPL" and out["retrieved_at"]
    out, err = run("get_key_statistics", symbol="AAPL", groups=["Balance Sheet Health"])
    assert not err and list(out["groups"]) == ["Balance Sheet Health"]
    assert out["groups"]["Balance Sheet Health"]["Quick Ratio (mrq)"] is None  # missing stays null


def test_unavailable_symbol_is_explicit():
    out, err = run("get_company_snapshot", symbol=fake_yahoo.UNKNOWN)
    assert not err and out["available"] is False and out["reason"]


def test_history_statement_ratios_holders_news():
    out, _ = run("get_price_history", symbol="AAPL", period="1y", interval="1d")
    assert out["summary"]["available"] and len(out["close_series_unadjusted"]) <= 62
    assert out["returns_vs_benchmark"]["rows"][0]["period"] == "YTD"
    out, _ = run("get_financial_statement", symbol="AAPL", statement="income", frequency="annual", items=["TotalRevenue", "Nope"])
    assert out["requested_but_not_reported"] == ["Nope"] and len(out["periods_newest_first"]) == 4
    out, _ = run("get_financial_ratios", symbol="AAPL", frequency="annual")
    first = next(iter(out["ratios_by_period"].values()))
    assert first["Gross Margin"] == pytest.approx(0.45)
    out, _ = run("get_holders", symbol="AAPL")
    assert out["top_institutional_holders"][0]["date_reported"] == "2025-06-30"
    out, _ = run("get_company_news", symbol="AAPL", limit=3)
    assert len(out["articles"]) == 3 and out["articles"][0]["url"].startswith("https://")


def test_compare_and_calculate_and_validation():
    out, _ = run("compare_companies", symbols=["AAPL", "MSFT", fake_yahoo.UNKNOWN], metrics=["Trailing P/E"])
    assert set(out["metrics"]["Trailing P/E"]) == {"AAPL", "MSFT"} and fake_yahoo.UNKNOWN in out["unavailable_symbols"]
    out, _ = run("calculate", operation="cagr", a=121, b=100, years=2)
    assert out["result"] == pytest.approx(0.1)
    out, _ = run("calculate", operation="ratio", a=1, b=0, years=0)
    assert out["result"] is None and out["defined"] is False
    out, err = run("get_company_snapshot", symbol="AAPL; rm -rf")
    assert err and "Invalid" in out["error"]
    out, err = run("get_price_history", symbol="AAPL", period="7y", interval="1d")
    assert err
    _, err = tools.execute("nope", {})
    assert err


def test_context_note():
    note = build_context_note("AAPL", {"name": "Apple", "price": 1.0},
                              {"section": "Financials", "filters": {"frequency": "annual"}, "visible": {"x": "y" * 9000}})
    assert "Financials" in note and "omitted" in note and len(note) < 5000


def test_citations_collect():
    log = SourceLog()
    content = [
        NS(type="server_tool_use", name="web_search", input={"query": "apple earnings"}),
        NS(type="web_search_tool_result", content=[NS(type="web_search_result", url="https://a.com/x", title="A", page_age="May 1, 2025")]),
        NS(type="web_search_tool_result", content=NS(type="web_search_tool_result_error", error_code="max_uses_exceeded")),
        NS(type="text", text="hi", citations=[NS(url="https://a.com/x", title="A"), NS(url="javascript:x", title="bad")]),
    ]
    collect_from_content(content, log)
    d = log.to_dict()
    assert d["queries"] == ["apple earnings"]
    assert d["web"] == [{"url": "https://a.com/x", "title": "A", "page_age": "May 1, 2025", "cited": True}]


# ---- agent loop with a scripted client ------------------------------------------------


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        for b in self.message.content:
            yield NS(type="content_block_start", content_block=b)
            if b.type == "text":
                yield NS(type="text", text=b.text)

    def get_final_message(self):
        return self.message


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.beta = NS(messages=NS(stream=self._stream))

    def _stream(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return FakeStream(self.script.pop(0))


def test_agent_loop_runs_tools_and_streams_text():
    script = [
        NS(stop_reason="tool_use", content=[
            NS(type="tool_use", id="t1", name="get_company_snapshot", input={"symbol": "AAPL"}),
            NS(type="tool_use", id="t2", name="calculate", input={"operation": "growth", "a": 110, "b": 100, "years": 0}),
        ]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="Revenue grew 10%.", citations=None)]),
    ]
    client = FakeClient(script)
    history = []
    events = list(assistant.Analyst(client=client).run(history, "How is AAPL doing?", "ctx"))
    kinds = [e.kind for e in events]
    assert "".join(e.text for e in events if e.kind == "text") == "Revenue grew 10%."
    assert kinds.count("tool_done") == 2 and kinds[-1] == "done"
    assert [m["role"] for m in history] == ["user", "system", "assistant", "user", "assistant"]
    results = history[3]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"] and not any(r["is_error"] for r in results)
    req = client.requests[0]
    assert req["fallbacks"] == "default" and req["thinking"] == {"type": "adaptive"}
    assert req["tools"][-1]["type"].startswith("web_search")
    sources = events[-1].data["sources"]
    assert sources["data"][0]["tool"] == "get_company_snapshot"


def test_agent_loop_rolls_back_on_api_error():
    import anthropic
    import httpx2

    class Boom(FakeClient):
        def _stream(self, **kwargs):
            raise anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com"))

    history = [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "ok"}]
    events = list(assistant.Analyst(client=Boom([])).run(history, "q", "ctx"))
    assert events[0].kind == "error" and len(history) == 2


def test_agent_loop_refusal_and_pause():
    script = [
        NS(stop_reason="pause_turn", content=[NS(type="server_tool_use", name="web_search", input={"query": "q"})]),
        NS(stop_reason="refusal", content=[], stop_details=NS(category="cyber")),
    ]
    events = list(assistant.Analyst(client=FakeClient(script)).run([], "q", "ctx"))
    assert any(e.kind == "refusal" for e in events)
