"""Builds the per-turn operator context note: selected company, active section, filters, visible figures.

Pages publish what they show via `publish(...)`; the chat panel reads it with `build_context_note(...)`.
The note is sent as a mid-conversation system message so the cached prefix (tools + system prompt)
never changes when the user navigates.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

MAX_CONTEXT_CHARS = 4000


def publish(state: dict, section: str, filters: dict | None = None, visible: dict | None = None) -> None:
    """Record what the active section is showing (call from each page's render)."""
    state["page_context"] = {"section": section, "filters": filters or {}, "visible": visible or {}}


def build_context_note(symbol: str, info: dict | None, page_context: dict | None, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    info = info or {}
    page_context = page_context or {}
    company = {
        "symbol": symbol,
        "name": info.get("name"),
        "exchange": info.get("fullExchangeName") or info.get("exchange"),
        "currency": info.get("currency"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "last_price": info.get("price"),
        "change_pct_today": info.get("change_pct"),
    }
    payload = {
        "current_utc_time": now.strftime("%Y-%m-%d %H:%M UTC"),
        "selected_company": {k: v for k, v in company.items() if v is not None},
        "active_section": page_context.get("section"),
        "filters": page_context.get("filters") or {},
        "visible_on_screen": page_context.get("visible") or {},
    }
    text = json.dumps(payload, default=str, ensure_ascii=False)
    if len(text) > MAX_CONTEXT_CHARS:
        payload["visible_on_screen"] = {"note": "omitted (too large); use tools to fetch details"}
        text = json.dumps(payload, default=str, ensure_ascii=False)
    return (
        "Application context for the next user message (from the app, not the user). "
        "Use it to resolve references like 'this company' or 'these numbers'; fetch data with tools as needed.\n"
        + text
    )


def summarize_for_context(values: dict[str, Any], limit: int = 25) -> dict[str, Any]:
    """Trim a dict of visible figures to a manageable size."""
    out = {}
    for i, (k, v) in enumerate(values.items()):
        if i >= limit:
            break
        out[k] = v
    return out
