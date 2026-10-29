"""External research via Claude's server-side web search tool.

Searches run on Anthropic's infrastructure; results come back as `web_search_tool_result` blocks with
URL, title and page age, and answer text carries citations. ai.citations turns both into the
"Sources" list shown under each answer.
"""
from __future__ import annotations

# Dynamic-filtering web search (supported on current Opus/Sonnet models).
WEB_SEARCH_TOOL: dict = {
    "type": "web_search_20260209",
    "name": "web_search",
    "max_uses": 6,
}


def search_status_label(query: str | None) -> str:
    return f"Searching the web: “{query}”" if query else "Searching the web…"
