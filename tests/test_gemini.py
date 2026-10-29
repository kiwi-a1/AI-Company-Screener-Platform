"""Gemini analyst loop with a scripted client, plus provider selection."""
from types import SimpleNamespace as NS

import pytest

import config
from ai import gemini_assistant
from services import cache
from tests import fake_yahoo


@pytest.fixture(autouse=True)
def _fake():
    fake_yahoo.install()
    cache.invalidate()


def _chunk(*parts):
    return NS(candidates=[NS(content=NS(parts=list(parts)))])


def _part(text=None, call=None):
    return NS(text=text, thought=None, function_call=call)


class FakeModels:
    def __init__(self, script):
        self.script = list(script)
        self.searches = []

    def generate_content_stream(self, model, contents, config):
        return iter(self.script.pop(0))

    def generate_content(self, model, contents, config):
        self.searches.append(contents)
        web = NS(uri="https://news.example.com/a", title="Example News", domain="example.com")
        return NS(text="Apple reported record revenue.", candidates=[NS(grounding_metadata=NS(grounding_chunks=[NS(web=web)]))])


def test_gemini_loop_tools_search_and_citations():
    script = [
        [_chunk(_part(call=NS(name="get_company_snapshot", args={"symbol": "AAPL"})),
                _part(call=NS(name="web_search", args={"query": "Apple earnings"})))],
        [_chunk(_part(text="Apple looks "), _part(text="strong."))],
    ]
    client = NS(models=FakeModels(script))
    history = []
    events = list(gemini_assistant.GeminiAnalyst(client=client, model="m").run(history, "How is AAPL?", "ctx"))
    assert "".join(e.text for e in events if e.kind == "text") == "Apple looks strong."
    assert [e.kind for e in events].count("tool_done") == 2
    assert [c.role for c in history] == ["user", "model", "user", "model"]
    src = events[-1].data["sources"]
    assert src["web"][0]["url"] == "https://news.example.com/a" and src["queries"] == ["Apple earnings"]
    assert src["data"][0]["tool"] == "get_company_snapshot"


def test_gemini_error_rolls_back():
    class Boom(FakeModels):
        def generate_content_stream(self, **kw):
            raise RuntimeError("429 RESOURCE_EXHAUSTED")

    history = ["earlier"]
    events = list(gemini_assistant.GeminiAnalyst(client=NS(models=Boom([])), model="m").run(history, "q", "ctx"))
    assert events[0].kind == "error" and "quota" in events[0].text and history == ["earlier"]


def test_declarations_cover_all_tools():
    names = {d["name"] for d in gemini_assistant._declarations()}
    assert names == {t["name"] for t in gemini_assistant.tools.TOOL_DEFINITIONS} | {"web_search"}


def test_provider_selection(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert config.analyst_provider() is None
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert config.analyst_provider() == "gemini"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    assert config.analyst_provider() == "anthropic"
