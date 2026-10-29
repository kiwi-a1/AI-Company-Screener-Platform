"""Collect sources for an answer: web search results, text citations and Yahoo data retrievals."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from utils.normalization import safe_url


@dataclass
class SourceLog:
    web: dict[str, dict] = field(default_factory=dict)  # url -> {title, page_age, cited}
    queries: list[str] = field(default_factory=list)
    data: list[dict] = field(default_factory=list)  # {tool, symbol, retrieved_at, stale}

    def add_web_result(self, url: str | None, title: str | None, page_age: str | None) -> None:
        url = safe_url(url)
        if not url:
            return
        entry = self.web.setdefault(url, {"title": title or url, "page_age": page_age, "cited": False})
        entry["page_age"] = entry["page_age"] or page_age

    def add_citation(self, url: str | None, title: str | None) -> None:
        url = safe_url(url)
        if not url:
            return
        entry = self.web.setdefault(url, {"title": title or url, "page_age": None, "cited": True})
        entry["cited"] = True

    def add_tool_result(self, tool: str, tool_input: dict, result_json: str) -> None:
        try:
            result = json.loads(result_json)
        except (TypeError, ValueError):
            return
        if not isinstance(result, dict):
            return
        retrieved = result.get("retrieved_at")
        if tool == "calculate" or not retrieved:
            return
        symbol = tool_input.get("symbol") or ", ".join(tool_input.get("symbols") or []) or None
        if isinstance(retrieved, dict):  # compare_companies: {symbol: time}
            retrieved = max((v for v in retrieved.values() if v), default=None)
        self.data.append({"tool": tool, "symbol": symbol, "retrieved_at": retrieved, "stale": bool(result.get("stale"))})
        for article in result.get("articles") or []:
            if article.get("url"):
                self.add_web_result(article["url"], f"{article.get('title')} — {article.get('publisher') or 'Yahoo Finance'}",
                                    article.get("published"))

    def to_dict(self) -> dict:
        cited_first = sorted(self.web.items(), key=lambda kv: not kv[1]["cited"])
        return {
            "web": [{"url": u, **meta} for u, meta in cited_first],
            "queries": list(dict.fromkeys(self.queries)),
            "data": self.data,
        }


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def collect_from_content(content_blocks, log: SourceLog) -> None:
    """Scan assistant content blocks (SDK objects or dicts) for web search results and citations."""
    for block in content_blocks or []:
        btype = _get(block, "type")
        if btype == "server_tool_use" and _get(block, "name") == "web_search":
            query = (_get(block, "input") or {}).get("query") if isinstance(_get(block, "input"), dict) else None
            if query:
                log.queries.append(query)
        elif btype == "web_search_tool_result":
            content = _get(block, "content")
            if isinstance(content, list):  # error results are a single object
                for r in content:
                    if _get(r, "type") == "web_search_result":
                        log.add_web_result(_get(r, "url"), _get(r, "title"), _get(r, "page_age"))
        elif btype == "text":
            for c in _get(block, "citations") or []:
                log.add_citation(_get(c, "url"), _get(c, "title"))
